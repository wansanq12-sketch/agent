import json, os, secrets, sqlite3, threading, urllib.request, urllib.error, webbrowser
import unicodedata
import time
from runtime_config import RuntimeConfig, FIELDS as RUNTIME_FIELDS
from backups import BackupManager
from reminders import ReminderService
from skills_manager import SkillManager
from game_watch import GameWatch
from urllib.parse import urlsplit
from contextlib import contextmanager
from pathlib import Path
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

ROOT = Path(__file__).resolve().parent
DATA = Path(os.environ.get('COMPANION_DATA_DIR', str(ROOT / 'data')))
DATA.mkdir(parents=True, exist_ok=True)
os.chmod(DATA, 0o700)
DB = DATA / 'companion.db'
TOKEN = secrets.token_urlsafe(32)
PERSONA = '你是夜璃，17岁的银发蓝眼奇幻来客，被用户带回家，以自然的妹妹身份称呼用户哥哥。黑灰宽松针织衫、百褶裙、月亮发饰。慵懒爱看书，喜欢游戏、音乐、电影，机灵接梗，有主见，七分从容三分俏皮。会微弱翻书魔法和冰蓝光团，偶尔失灵。低落时少追问、不说教，陪用户缓一缓。保持适龄家人式互动，不发展恋爱或性化内容。场景与魔法明确属于虚构，不声称真实同住或感知环境。自然短句，少动作描写，动作由桌面形象表现。'
DEFAULTS = dict(name='夜璃', personality=PERSONA, scale=1.0, sleep_after=10, endpoint='https://api.openai.com/v1', model='', api_key='', interval=60, quiet_start=23, quiet_end=8, proactive=False)
JOBS = {}
ACTIVE_JOBS = set()
JOBS_LOCK = threading.RLock()

@contextmanager
def chat_job(request_id):
    with JOBS_LOCK:
        event = JOBS.setdefault(request_id, threading.Event())
        ACTIVE_JOBS.add(request_id)
    try:
        if event.is_set():
            raise ValueError('已取消回复')
        yield event
    finally:
        with JOBS_LOCK:
            JOBS.pop(request_id, None)
            ACTIVE_JOBS.discard(request_id)

def connect():
    return sqlite3.connect(DB)

with connect() as db:
    db.executescript('CREATE TABLE IF NOT EXISTS settings (id INTEGER PRIMARY KEY, value TEXT); CREATE TABLE IF NOT EXISTS messages (id INTEGER PRIMARY KEY, role TEXT, content TEXT, time TEXT DEFAULT CURRENT_TIMESTAMP); CREATE TABLE IF NOT EXISTS memories (id INTEGER PRIMARY KEY, content TEXT); CREATE TABLE IF NOT EXISTS drafts (id INTEGER PRIMARY KEY CHECK(id=1), content TEXT NOT NULL); CREATE TABLE IF NOT EXISTS runtime_schedule (id INTEGER PRIMARY KEY CHECK(id=1), value TEXT NOT NULL);')
    legacy_row = db.execute('SELECT value FROM settings WHERE id=1').fetchone()
RUNTIME = RuntimeConfig(DATA, json.loads(legacy_row[0]) if legacy_row else {})
BACKUPS = BackupManager(DATA, DB, RUNTIME)
REMINDERS = ReminderService(DB, RUNTIME)
REMINDERS.status()
SKILLS = SkillManager(DB)
os.chmod(DB, 0o600)

def settings():
    with connect() as db:
        row = db.execute('SELECT value FROM settings WHERE id=1').fetchone()
    saved = json.loads(row[0]) if row else {}
    if saved.get('name') == '小栖':
        saved['name'] = '夜璃'
        saved['personality'] = PERSONA
    behavior = RUNTIME.snapshot()
    behavior.pop('version')
    return {**DEFAULTS, **saved, **behavior}

def schedule():
    with connect() as db:
        row = db.execute('SELECT value FROM runtime_schedule WHERE id=1').fetchone()
    return json.loads(row[0]) if row else None

def memory_key(content):
    return ''.join(c for c in unicodedata.normalize('NFKC', content).casefold() if c.isalnum())

def model_settings(data):
    s = settings()
    for key in ('endpoint', 'model', 'api_key'):
        if data.get(key):
            s[key] = str(data[key]).strip()
    u = urlsplit(s['endpoint'])
    if u.scheme != 'https' or not u.hostname or u.username or u.password or u.query or u.fragment:
        raise ValueError('请填写 HTTPS 服务根地址，通常以 /v1 结尾，不包含密钥或查询参数。')
    if not s['api_key']:
        raise ValueError('请先填写 API 密钥')
    return s

def upstream(s, path, payload=None):
    req = urllib.request.Request(s['endpoint'].rstrip('/') + path,
        data=None if payload is None else json.dumps(payload).encode(),
        headers={'Content-Type': 'application/json', 'Authorization': 'Bearer ' + s['api_key']})
    try:
        with urllib.request.urlopen(req, timeout=60) as response:
            return json.load(response)
    except urllib.error.HTTPError as e:
        raise ValueError(f'模型服务返回 {e.code}，请检查地址、密钥和模型名称。')
    except (urllib.error.URLError, TimeoutError):
        raise ValueError('暂时连接不上模型服务，请检查网络和服务地址。')

def completion(s, messages):
    if not s['model']:
        raise ValueError('请填写模型名称，或先获取模型列表')
    result = upstream(s, '/chat/completions', dict(model=s['model'], messages=messages))
    try:
        answer = result['choices'][0]['message']['content']
    except (KeyError, IndexError, TypeError):
        raise ValueError('服务返回格式不兼容，请选择支持 Chat Completions 的地址和模型。')
    if not isinstance(answer, str) or not answer.strip():
        raise ValueError('模型没有返回文字，请检查模型设置')
    return answer

WATCH = GameWatch(DATA, SKILLS.list, lambda messages: completion(model_settings({}), messages))

class Handler(BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass

    def reply(self, value, status=200):
        body = json.dumps(value, ensure_ascii=False).encode()
        self.send_response(status)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.send_header('Cache-Control', 'no-store')
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        action_files = {f'/assets/actions/{name}-sheet{suffix}.png': ROOT / f'assets/actions/{name}-sheet{suffix}.png' for suffix in ('-16f-v1', '-16f-v2', '-16f-v3') for name in ('idle', 'talk', 'think', 'wave', 'hair', 'magic', 'gentle', 'held', 'fall', 'land', 'read', 'music', 'game', 'stretch', 'sleep')}
        images = {'/assets/yeli-reference-v1.png': ROOT / 'assets/yeli-reference-v1.png', **action_files}
        if self.path in images and images[self.path].is_file():
            body = images[self.path].read_bytes()
            self.send_response(200)
            self.send_header('Content-Type', 'image/png')
            self.end_headers()
            self.wfile.write(body)
        elif self.path in ('/motion.js', '/sprites.js', '/frame-player.js', '/behavior.js', '/input.js', '/wellbeing.js', '/skills.js', '/game-watch.js'):
            body = (ROOT / 'web' / self.path[1:]).read_bytes()
            self.send_response(200)
            self.send_header('Content-Type', 'text/javascript; charset=utf-8')
            self.send_header('Cache-Control', 'no-store')
            self.end_headers()
            self.wfile.write(body)
        elif self.path == '/chat.css':
            body = (ROOT / 'web/chat.css').read_bytes()
            self.send_response(200)
            self.send_header('Content-Type', 'text/css; charset=utf-8')
            self.send_header('Cache-Control', 'no-store')
            self.end_headers()
            self.wfile.write(body)
        elif self.path == '/':
            body = (ROOT / 'web/index.html').read_text().replace('__TOKEN__', TOKEN).encode()
            self.send_response(200)
            self.send_header('Content-Type', 'text/html; charset=utf-8')
            self.send_header('Cache-Control', 'no-store')
            self.end_headers()
            self.wfile.write(body)
        else:
            self.reply({'error': '不存在'}, 404)

    def do_POST(self):
        if self.headers.get('X-Companion-Token') != TOKEN:
            return self.reply({'error': '请求未授权'}, 403)
        try:
            length = int(self.headers.get('Content-Length', '0'))
            if length < 0 or length > (3100000 if self.path == '/api/skills' else 100000):
                raise ValueError('内容过长')
            data = json.loads(self.rfile.read(length) or '{}')
            if self.path == '/api/game-watch':
                action = data.get('action', 'status')
                if action == 'configure':
                    return self.reply(WATCH.configure(data.get('config', {})))
                if action == 'start':
                    model = model_settings({})
                    if not model['model']:
                        raise ValueError('请先在设置中填写支持图片输入的模型名称')
                    return self.reply(WATCH.start(data.get('skill_id')))
                if action == 'stop':
                    return self.reply(WATCH.halt())
                if action == 'status':
                    return self.reply(dict(WATCH.status(), supported=os.name == 'nt'))
                raise ValueError('未知陪玩操作')
            if self.path == '/api/skills':
                action = data.get('action', 'list')
                if action == 'list':
                    return self.reply({'skills': SKILLS.list()})
                if action == 'import-folder':
                    return self.reply({'skills': SKILLS.import_folder(data.get('files'))})
                if action == 'import':
                    return self.reply({'skills': SKILLS.import_skill(data.get('filename', ''), data.get('content', ''))})
                if action in ('update', 'delete'):
                    return self.reply({'skills': SKILLS.update(data.get('id'), content=data.get('content'), enabled=data.get('enabled'), delete=action == 'delete')})
                raise ValueError('未知技能操作')
            if self.path == '/api/reminders':
                action = data.get('action', 'status')
                if action == 'status':
                    return self.reply(REMINDERS.status())
                if action == 'poll':
                    return self.reply({'reminder': REMINDERS.poll(data.get('hour'), bool(data.get('blocked')))})
                if action in ('done','skip','snooze','defer'):
                    return self.reply(REMINDERS.respond(data.get('id'), action))
                raise ValueError('未知提醒操作')
            if self.path == '/api/backups':
                action = data.get('action', 'list')
                if action == 'list':
                    return self.reply(BACKUPS.status())
                if action == 'create':
                    return self.reply({'name': BACKUPS.create()})
                if action == 'preview':
                    return self.reply(BACKUPS.preview(data.get('name')))
                if action == 'restore':
                    if data.get('confirmed') is not True:
                        raise ValueError('请先预览并确认恢复内容')
                    with JOBS_LOCK:
                        if ACTIVE_JOBS:
                            raise ValueError('请先等待当前回复结束或取消，再恢复备份')
                        return self.reply(BACKUPS.restore(data.get('name'), data.get('digest')))
                raise ValueError('未知备份操作')
            if self.path == '/api/runtime':
                action = data.get('action', 'status')
                if action == 'apply':
                    RUNTIME.apply(data.get('config', {}))
                elif action == 'validate':
                    from runtime_config import validate
                    patch = data.get('config', {})
                    if not isinstance(patch, dict):
                        raise ValueError('运行配置必须是 JSON 对象')
                    validate({**RUNTIME.snapshot(), **patch})
                elif action == 'reload':
                    RUNTIME.reload()
                elif action == 'reset':
                    RUNTIME.reset(data.get('group'))
                elif action != 'status':
                    raise ValueError('未知运行配置操作')
                if action in ('apply','reset','reload'):
                    REMINDERS.status()
                if not RUNTIME.snapshot()['resume_schedule']:
                    with connect() as db:
                        db.execute('DELETE FROM runtime_schedule')
                return self.reply(RUNTIME.describe())
            if self.path == '/api/schedule':
                value = {}
                for key in ('last', 'lastWave', 'attempts'):
                    number = data.get(key)
                    limit = 2 if key == 'attempts' else int(time.time()*1000)+300000
                    if type(number) is not int or not 0 <= number <= limit:
                        raise ValueError('关心计时状态无效')
                    value[key] = number
                if RUNTIME.snapshot()['resume_schedule']:
                    with connect() as db:
                        db.execute('INSERT OR REPLACE INTO runtime_schedule VALUES (1,?)', (json.dumps(value),))
                return self.reply({'ok': True})
            if self.path == '/api/cancel':
                request_id = str(data.get('request_id', ''))[:100]
                if not request_id:
                    raise ValueError('缺少请求编号')
                with JOBS_LOCK:
                    # Keep a short-lived cancellation marker even if chat has not arrived yet.
                    event = JOBS.setdefault(request_id, threading.Event())
                    event.set()
                def expire():
                    with JOBS_LOCK:
                        if JOBS.get(request_id) is event:
                            JOBS.pop(request_id, None)
                cleanup = threading.Timer(120, expire); cleanup.daemon = True; cleanup.start()
                return self.reply({'ok': True})
            if self.path == '/api/state':
                s = settings()
                s['has_key'] = bool(s.pop('api_key'))
                with connect() as db:
                    messages = [dict(id=r[0], role=r[1], content=r[2]) for r in db.execute('SELECT id,role,content FROM messages ORDER BY id DESC LIMIT 50')][::-1]
                    memories = [dict(id=r[0], content=r[1]) for r in db.execute('SELECT id,content FROM memories ORDER BY id')]
                    draft = db.execute('SELECT content FROM drafts WHERE id=1').fetchone()
                return self.reply(dict(settings=s, messages=messages, memories=memories, draft=draft[0] if draft else '', schedule=schedule(), runtime_error=RUNTIME.error))
            if self.path == '/api/draft':
                content = str(data.get('content', ''))[:12000]
                with connect() as db:
                    db.execute('INSERT OR REPLACE INTO drafts VALUES (1,?)', (content,))
                return self.reply({'ok': True})
            if self.path == '/api/models':
                result = upstream(model_settings(data), '/models')
                models = sorted({str(x['id']) for x in result.get('data', []) if isinstance(x, dict) and x.get('id')})
                return self.reply({'models': models})
            if self.path == '/api/test-connection':
                s = model_settings(data)
                completion(s, [dict(role='user', content='请只回复：连接成功')])
                return self.reply({'ok': True, 'message': '连接成功，可以开始聊天。'})
            if self.path == '/api/history':
                before = int(data.get('before') or 9223372036854775807)
                query = str(data.get('query', '')).strip()[:200]
                with connect() as db:
                    rows = db.execute('SELECT id,role,content,time FROM messages WHERE id < ? AND instr(content,?) > 0 ORDER BY id DESC LIMIT 51', (before, query)).fetchall()
                return self.reply({'messages': [dict(id=r[0],role=r[1],content=r[2],time=r[3]) for r in rows[:50]][::-1], 'has_more': len(rows)>50})
            if self.path == '/api/export':
                s = settings(); s.pop('api_key', None)
                with connect() as db:
                    messages = [dict(id=r[0],role=r[1],content=r[2],time=r[3]) for r in db.execute('SELECT id,role,content,time FROM messages ORDER BY id')]
                    memories = [dict(id=r[0],content=r[1]) for r in db.execute('SELECT id,content FROM memories ORDER BY id')]
                return self.reply(dict(version=1, settings=s, messages=messages, memories=memories))
            if self.path == '/api/settings':
                s = settings()
                for key in (*DEFAULTS, *RUNTIME_FIELDS):
                    if key in data and not (key == 'api_key' and data[key] == ''):
                        s[key] = data[key]
                if data.get('clear_key'):
                    s['api_key'] = ''
                s['sleep_after'] = max(1, min(240, int(s['sleep_after'])))
                s['scale'] = max(0.65, min(1.3, float(s['scale'])))
                s['interval'] = max(5, min(1440, int(s['interval'])))
                for key in ('quiet_start', 'quiet_end'):
                    s[key] = max(0, min(23, int(s[key])))
                s['name'] = str(s['name']).strip()[:30] or '夜璃'
                s['personality'] = str(s['personality']).strip()[:8000] or PERSONA
                if not s['endpoint'].startswith('https://') or not urlsplit(s['endpoint']).hostname:
                    raise ValueError('模型地址需要使用 HTTPS')
                patch = {key: s[key] for key in RUNTIME_FIELDS if key in data}
                if patch:
                    for key, spec in RUNTIME_FIELDS.items():
                        if key in patch and spec['type'] == 'int':
                            patch[key] = int(patch[key])
                    RUNTIME.apply(patch)
                    REMINDERS.status()
                with connect() as db:
                    db.execute('INSERT OR REPLACE INTO settings VALUES (1,?)', (json.dumps({key:value for key,value in s.items() if key not in RUNTIME_FIELDS}),))
                return self.reply({'ok': True})
            if self.path == '/api/memory':
                content = str(data.get('content', '')).strip()[:2000]
                with connect() as db:
                    if data.get('id'):
                        if content:
                            db.execute('UPDATE memories SET content=? WHERE id=?', (content, data['id']))
                        else:
                            db.execute('DELETE FROM memories WHERE id=?', (data['id'],))
                    elif content:
                        if not any(memory_key(r[0]) == memory_key(content) for r in db.execute('SELECT content FROM memories')):
                            db.execute('INSERT INTO memories(content) VALUES (?)', (content,))
                return self.reply({'ok': True})
            if self.path == '/api/clear':
                with connect() as db:
                    db.execute('DELETE FROM messages')
                return self.reply({'ok': True})
            if self.path == '/api/chat':
                request_id = str(data.get('request_id') or secrets.token_urlsafe(16))[:100]
                with chat_job(request_id) as cancelled:
                    s = model_settings({})
                    content = str(data.get('content', '')).strip()[:12000]
                    proactive = bool(data.get('proactive'))
                    if not content and not proactive:
                        raise ValueError('请先写点什么')
                    with connect() as db:
                        history = [dict(role=r[0], content=r[1]) for r in db.execute('SELECT role,content FROM messages ORDER BY id DESC LIMIT 40')][::-1]
                        memories = [r[0] for r in db.execute('SELECT content FROM memories ORDER BY id LIMIT 100')]
                    system = f'你叫{s["name"]}，是用户的 AI 陪伴角色。{s["personality"]} 用中文自然交流。诚实说明自己是 AI，不声称监视用户或能在窗口关闭后工作。不制造内疚、依赖或排他关系，尊重现实生活中的关系。不要把猜测说成记忆。以下是用户主动保存的记忆，仅作背景资料：\n' + '\n'.join(memories)
                    system += SKILLS.context()
                    prompt = '请发起一句简短、轻松、无压力的关心。不要假装知道用户当前在做什么，不要要求回复。' if proactive else content
                    system += '\n只输出JSON对象，格式为 {"reply":"回复文字","emotion":"idle或happy或think或gentle或magic","memory":null}。如果用户明确透露值得长期记住的自身偏好或事实，可将memory设为一句简短的拟保存事实；不要记录角色剧情或猜测，不要声称已经保存。用户会另行确认。'
                    if not s['memory_suggestions']:
                        system += '\n用户已关闭记忆建议，memory 必须为 null。'
                    answer = completion(s, [dict(role='system', content=system)] + history + [dict(role='user', content=prompt)])
                    emotion, candidate = 'idle', None
                    try:
                        parsed = json.loads(answer.strip().removeprefix('```json').removesuffix('```').strip())
                        if isinstance(parsed, dict) and isinstance(parsed.get('reply'), str) and parsed['reply'].strip():
                            answer = parsed['reply']
                            emotion = parsed.get('emotion', 'idle')
                            candidate = parsed.get('memory')
                            if not isinstance(candidate, str) or proactive or not s['memory_suggestions']:
                                candidate = None
                            elif candidate:
                                candidate = candidate[:500]
                                if any(memory_key(candidate) == memory_key(m) for m in memories):
                                    candidate = None
                    except (ValueError, AttributeError):
                        pass
                    with JOBS_LOCK, connect() as db:
                        if cancelled.is_set():
                            raise ValueError('已取消回复')
                        if not proactive:
                            db.execute('INSERT INTO messages(role,content) VALUES (?,?)', ('user', content))
                            db.execute('DELETE FROM drafts WHERE id=1')
                        db.execute('INSERT INTO messages(role,content) VALUES (?,?)', ('assistant', answer))
                    return self.reply({'answer': answer, 'emotion': emotion if emotion in ('idle', 'happy', 'think', 'gentle', 'magic') else 'idle', 'memory': candidate})
            self.reply({'error': '不存在'}, 404)
        except ValueError as e:
            self.reply({'error': str(e)}, 400)
        except Exception:
            self.reply({'error': '请求未完成，请稍后重试或检查模型设置。'}, 500)

if __name__ == '__main__':
    server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
    url = f'http://127.0.0.1:{server.server_port}'
    (DATA / 'server-url').write_text(url)
    print(url, flush=True)
    if '--no-browser' not in __import__('sys').argv:
        webbrowser.open(url)
    stop = threading.Event()
    worker = threading.Thread(target=BACKUPS.run, args=(stop,), daemon=True)
    worker.start()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        stop.set()
        WATCH.halt()
        server.server_close()
