"""Validated application behavior config. Credentials and appearance stay in settings DB."""
import json
import os
from pathlib import Path
import tempfile
import threading

FIELDS = {
    'proactive': dict(type='bool', default=False, group='proactive', label='开启主动关心'),
    'interval': dict(type='int', default=60, min=5, max=1440, group='proactive', label='首次关心前闲置分钟数'),
    'retry_interval': dict(type='int', default=120, min=120, max=1440, group='proactive', label='无回应后再次尝试的间隔（分钟）'),
    'max_attempts': dict(type='int', default=2, min=1, max=2, group='proactive', label='连续无回应最多尝试次数'),
    'invitation_seconds': dict(type='int', default=15, min=5, max=60, group='proactive', label='挥手邀请保留秒数'),
    'quiet_start': dict(type='int', default=23, min=0, max=23, group='proactive', label='安静时段开始（小时）'),
    'quiet_end': dict(type='int', default=8, min=0, max=23, group='proactive', label='安静时段结束（小时）'),
    'resume_schedule': dict(type='bool', default=True, group='proactive', label='重启后延续关心计时与尝试次数'),
    'invite_wakes_sleep': dict(type='bool', default=True, group='proactive', label='允许睡着后短暂醒来挥手'),
    'sleep_enabled': dict(type='bool', default=True, group='sleep', label='开启闲置睡觉'),
    'sleep_after': dict(type='int', default=10, min=1, max=240, group='sleep', label='闲置多少分钟后睡觉'),
    'daily_actions_enabled': dict(type='bool', default=True, group='daily', label='开启日常行为'),
    'daily_action_interval': dict(type='int', default=90, min=10, max=3600, group='daily', label='日常行为最短间隔（秒）'),
    'memory_suggestions': dict(type='bool', default=True, group='memory', label='允许提出待确认记忆'),
    'water_reminder_enabled': dict(type='bool', default=True, group='reminders', label='开启喝水提醒'),
    'water_reminder_interval': dict(type='int', default=45, min=5, max=240, group='reminders', label='喝水提醒间隔（分钟）'),
    'move_reminder_enabled': dict(type='bool', default=True, group='reminders', label='开启活动提醒'),
    'move_reminder_interval': dict(type='int', default=60, min=10, max=240, group='reminders', label='活动提醒间隔（分钟）'),
    'game_mode': dict(type='bool', default=False, group='gaming', label='开启游戏模式（高层置顶）'),
    'backup_enabled': dict(type='bool', default=True, group='backup', label='开启自动备份'),
    'backup_interval_hours': dict(type='int', default=24, min=1, max=168, group='backup', label='自动备份间隔（小时）'),
    'backup_keep': dict(type='int', default=7, min=2, max=90, group='backup', label='保留备份份数'),
}
DEFAULTS = {'version': 1, **{key: spec['default'] for key, spec in FIELDS.items()}}
GROUPS = dict(proactive='主动关心', sleep='睡眠', daily='日常行为', memory='记忆建议', reminders='喝水与活动', gaming='游戏模式', backup='数据备份')

def validate(document):
    if not isinstance(document, dict):
        raise ValueError('运行配置必须是 JSON 对象')
    if type(document.get('version')) is not int or document['version'] != 1:
        raise ValueError('不支持的运行配置版本，当前仅支持 version: 1')
    unknown = set(document) - set(DEFAULTS)
    if unknown:
        raise ValueError('未知运行配置项：' + ', '.join(sorted(unknown)))
    result = dict(DEFAULTS)
    for key, value in document.items():
        if key == 'version':
            continue
        spec = FIELDS[key]
        if spec['type'] == 'bool':
            if type(value) is not bool:
                raise ValueError(spec['label'] + '必须是 true 或 false')
        elif type(value) is not int or not spec['min'] <= value <= spec['max']:
            raise ValueError(f"{spec['label']}需要是 {spec['min']}–{spec['max']} 之间的整数")
        result[key] = value
    return result

class RuntimeConfig:
    def __init__(self, folder, legacy=None):
        self.folder = Path(folder)
        self.path = self.folder / 'runtime.json'
        self.good_path = self.folder / 'runtime.last-good.json'
        self.lock = threading.RLock()
        self.error = ''
        self.value = dict(DEFAULTS)
        if not self.path.exists():
            migrated = dict(DEFAULTS)
            for key in FIELDS:
                if key in (legacy or {}):
                    try:
                        migrated = validate({**migrated, key: legacy[key]})
                    except ValueError:
                        pass
            self.apply(migrated)
        else:
            try:
                self.reload()
            except ValueError as exc:
                self.error = str(exc)
                try:
                    self.value = validate(json.loads(self.good_path.read_text(encoding='utf-8')))
                except (OSError, ValueError):
                    self.value = dict(DEFAULTS)

    def _write(self, path, value):
        self.folder.mkdir(parents=True, exist_ok=True)
        fd, temporary = tempfile.mkstemp(prefix='.runtime-', dir=str(self.folder))
        try:
            with os.fdopen(fd, 'w', encoding='utf-8') as stream:
                json.dump(value, stream, ensure_ascii=False, indent=2)
                stream.write('\n'); stream.flush(); os.fsync(stream.fileno())
            os.replace(temporary, path)
        finally:
            if os.path.exists(temporary):
                os.unlink(temporary)

    def snapshot(self):
        with self.lock:
            return dict(self.value)

    def describe(self):
        with self.lock:
            return dict(config=dict(self.value), fields=FIELDS, groups=GROUPS, error=self.error,
                        path=str(self.path), effect='保存或重新载入后生效，无需重启。')

    def apply(self, patch):
        with self.lock:
            if not isinstance(patch, dict):
                raise ValueError('运行配置必须是 JSON 对象')
            candidate = validate({**self.value, **patch})
            self._write(self.path, candidate)
            self._write(self.good_path, candidate)
            self.value = candidate; self.error = ''
            return dict(candidate)

    def reload(self):
        with self.lock:
            try:
                candidate = validate(json.loads(self.path.read_text(encoding='utf-8')))
            except (ValueError, OSError) as exc:
                self.error = '运行配置未载入：' + str(exc)
                raise ValueError(self.error)
            self._write(self.good_path, candidate)
            self.value = candidate; self.error = ''
            return dict(candidate)

    def reset(self, group):
        if group not in GROUPS:
            raise ValueError('请选择要重置的运行配置分组')
        return self.apply({key: spec['default'] for key, spec in FIELDS.items() if spec['group'] == group})
