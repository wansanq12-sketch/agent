"""Release identity and non-destructive, versioned user-data upgrade checkpoints."""
import json
import os
from pathlib import Path
import re
import shutil
import sqlite3
import tempfile
from datetime import datetime, timezone

APP_VERSION = (Path(__file__).resolve().parent / 'VERSION').read_text(encoding='ascii').strip()
if not re.fullmatch(r'\d+\.\d+\.\d+', APP_VERSION):
    raise ValueError('VERSION must contain major.minor.patch')
DATA_VERSION = 1

def prepare_user_data(folder, version=APP_VERSION):
    """Run under the application's instance lock, before any database/config writes.

    Legacy EXE releases already use this directory. Keep every existing value and
    checkpoint the original DB/config before registering a new application version.
    Future schema changes must increment DATA_VERSION and add an explicit migration.
    """
    folder = Path(folder)
    folder.mkdir(parents=True, exist_ok=True)
    marker = folder / 'installed-version.json'
    previous = {}
    if marker.exists():
        try:
            previous = json.loads(marker.read_text(encoding='utf-8'))
            if not isinstance(previous, dict):
                raise ValueError('invalid version record')
        except (ValueError, OSError) as exc:
            raise ValueError('版本记录无法读取，请保留数据目录并查看启动日志') from exc
    if type(previous.get('data_version', 0)) is not int:
        raise ValueError('数据版本记录无效，请保留数据目录并查看启动日志')
    if previous.get('data_version', 0) > DATA_VERSION:
        raise ValueError('此数据由更新版本创建，请安装相同或更新的软件版本')
    if previous.get('app_version') == version:
        return previous
    names = ['companion.db', 'runtime.json', 'runtime.last-good.json', 'game-watch.json']
    sources = [folder / name for name in names if (folder / name).is_file()]
    backup = None
    if sources:
        backups = folder / 'upgrade-backups'
        backups.mkdir(exist_ok=True)
        backup = Path(tempfile.mkdtemp(prefix='before-' + version + '-', dir=str(backups)))
        os.chmod(backup, 0o700)
        for source in sources:
            destination = backup / source.name
            if source.name == 'companion.db':
                # Include committed WAL content without changing the original DB.
                original = sqlite3.connect(source.resolve().as_uri() + '?mode=ro', uri=True)
                try:
                    target = sqlite3.connect(destination)
                    try:
                        original.backup(target)
                    finally:
                        target.close()
                finally:
                    original.close()
            else:
                shutil.copy2(source, destination)
            os.chmod(destination, 0o600)
        if marker.exists():
            shutil.copy2(marker, backup / marker.name)
    record = dict(app_version=version, data_version=DATA_VERSION,
                  previous_version=previous.get('app_version', 'legacy' if sources else None),
                  updated_at=datetime.now(timezone.utc).isoformat(),
                  backup=str(backup) if backup else None)
    fd, temporary = tempfile.mkstemp(prefix='.version-', dir=str(folder))
    try:
        with os.fdopen(fd, 'w', encoding='utf-8') as stream:
            json.dump(record, stream, ensure_ascii=False, indent=2)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, marker)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)
    return record
