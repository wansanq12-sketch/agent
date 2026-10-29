"""Bounded local JSON snapshots. Stored API credentials and drafts are excluded."""
import hashlib
import json
import os
from pathlib import Path
import re
import secrets
import sqlite3
import tempfile
import threading
import time
from datetime import datetime, timezone

NAME = re.compile(r'yeli-backup-\d{8}T\d{12}Z-[0-9a-f]{8}\.json\Z')

class BackupManager:
    def __init__(self, folder, database, config):
        self.folder = Path(folder) / 'backups'
        self.database = Path(database)
        self.config = config
        self.lock = threading.RLock()
        self.error = ''

    def files(self):
        if not self.folder.exists():
            return []
        return sorted((p for p in self.folder.iterdir() if NAME.fullmatch(p.name) and p.is_file() and not p.is_symlink()), key=lambda p:p.name, reverse=True)

    def status(self):
        with self.lock:
            return dict(error=self.error, path=str(self.folder), files=[dict(name=p.name,size=p.stat().st_size,time=p.stat().st_mtime) for p in self.files()])

    def _snapshot(self):
        with sqlite3.connect(self.database) as db:
            db.execute('BEGIN')
            messages=[dict(role=r[0],content=r[1],time=r[2]) for r in db.execute('SELECT role,content,time FROM messages ORDER BY id')]
            memories=[dict(content=r[0]) for r in db.execute('SELECT content FROM memories ORDER BY id')]
            row=db.execute('SELECT value FROM settings WHERE id=1').fetchone()
            settings=json.loads(row[0]) if row else {}
        settings.pop('api_key',None)
        return dict(version=1,created_at=datetime.now(timezone.utc).isoformat(),messages=messages,memories=memories,settings=settings,runtime=self.config.snapshot())

    def create(self, prune=True):
        with self.lock:
            self.folder.mkdir(parents=True,exist_ok=True,mode=0o700)
            os.chmod(self.folder,0o700)
            name='yeli-backup-'+datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')+'-'+secrets.token_hex(4)+'.json'
            fd, temporary=tempfile.mkstemp(prefix='.snapshot-',dir=self.folder)
            try:
                payload=self._snapshot()
                with os.fdopen(fd,'w',encoding='utf-8') as stream:
                    json.dump(payload,stream,ensure_ascii=False);stream.flush();os.fsync(stream.fileno())
                if Path(temporary).stat().st_size>100*1024*1024:
                    raise ValueError('备份超过 100 MB，未发布新文件，已有备份保持不变。')
                # Read back before publishing or removing any older snapshots.
                self.validate(json.loads(Path(temporary).read_text(encoding='utf-8')))
                os.replace(temporary,self.folder/name)
                if prune:
                    keep=self.config.snapshot()['backup_keep']
                    for older in self.files()[keep:]:
                        older.unlink()
                self.error=''
                return name
            finally:
                if os.path.exists(temporary):os.unlink(temporary)

    @staticmethod
    def validate(payload):
        if not isinstance(payload,dict) or type(payload.get('version')) is not int or payload['version']!=1:
            raise ValueError('不支持的备份格式')
        messages,memories=payload.get('messages'),payload.get('memories')
        if not isinstance(messages,list) or not isinstance(memories,list):raise ValueError('备份缺少聊天或记忆数据')
        if len(messages)>200000 or len(memories)>100000:raise ValueError('备份条目过多')
        for row in messages:
            if not isinstance(row,dict) or row.get('role') not in ('user','assistant') or not isinstance(row.get('content'),str) or len(row['content'])>200000:
                raise ValueError('备份中存在无效聊天记录')
            if 'time' in row and not isinstance(row['time'],str):raise ValueError('备份中的时间格式无效')
        for row in memories:
            if not isinstance(row,dict) or not isinstance(row.get('content'),str) or not row['content'].strip() or len(row['content'])>2000:
                raise ValueError('备份中存在无效记忆')
        return payload

    def _read(self, name):
        if not isinstance(name,str) or not NAME.fullmatch(name):raise ValueError('无效备份名称')
        path=self.folder/name
        if path.is_symlink() or not path.is_file():raise ValueError('找不到这份备份')
        if path.stat().st_size>100*1024*1024:raise ValueError('备份超过 100 MB，暂不支持从界面恢复')
        try:
            raw=path.read_bytes();payload=self.validate(json.loads(raw))
        except (OSError,UnicodeError,ValueError) as exc:
            raise ValueError('无法读取备份：'+str(exc))
        return payload,hashlib.sha256(raw).hexdigest()

    def preview(self,name):
        with self.lock:
            payload,digest=self._read(name)
            return dict(name=name,digest=digest,messages=len(payload['messages']),memories=len(payload['memories']),created_at=payload.get('created_at',''))

    def restore(self,name,digest):
        with self.lock:
            payload,actual=self._read(name)
            if not isinstance(digest,str) or not secrets.compare_digest(actual,digest):raise ValueError('备份已变化，请重新预览后恢复')
            # Keep this recovery snapshot outside normal retention pruning until a successful restore.
            recovery=self.create(prune=False)
            with sqlite3.connect(self.database) as db:
                db.execute('BEGIN IMMEDIATE')
                db.execute('DELETE FROM messages');db.execute('DELETE FROM memories')
                db.executemany('INSERT INTO messages(role,content,time) VALUES (?,?,?)',[(r['role'],r['content'],r.get('time') or datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S')) for r in payload['messages']])
                db.executemany('INSERT INTO memories(content) VALUES (?)',[(r['content'],) for r in payload['memories']])
            try:
                for older in self.files()[self.config.snapshot()['backup_keep']:]:older.unlink()
            except OSError:
                self.error='数据已恢复，但旧备份暂时无法清理。'
            return dict(ok=True,recovery=recovery,messages=len(payload['messages']),memories=len(payload['memories']))

    def maybe_create(self, now=None):
        with self.lock:
            config=self.config.snapshot()
            if not config['backup_enabled']:return None
            now=time.time() if now is None else now
            files=self.files()
            latest=max((p.stat().st_mtime for p in files if p.stat().st_mtime<=now+60),default=0)
            if files and now-latest<config['backup_interval_hours']*3600:return None
            return self.create()

    def run(self, stop):
        while not stop.is_set():
            try:self.maybe_create()
            except ValueError as exc:
                self.error=str(exc)
            except Exception:
                self.error='自动备份未完成，请检查数据目录的可用空间与写入权限。'
            stop.wait(60)
