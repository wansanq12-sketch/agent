"""Keep one companion instance per project; a second launch reveals the first."""
import os
if os.name == 'nt':
    import msvcrt
else:
    import fcntl
from pathlib import Path
import signal
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / 'data'
DATA.mkdir(exist_ok=True, mode=0o700)
lock = (DATA / 'instance.lock').open('a')
try:
    if os.name == 'nt':
        lock.seek(0)
        lock.write('0')
        lock.flush()
        lock.seek(0)
        msvcrt.locking(lock.fileno(), msvcrt.LK_NBLCK, 1)
    else:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
except (BlockingIOError, OSError):
    (DATA / 'show-request').write_text(str(time.time()))
    print('夜璃已在运行，已请求显示她。')
    sys.exit(0)

server = desktop = None

def interrupt(signum, frame):
    raise KeyboardInterrupt

signal.signal(signal.SIGTERM, interrupt)
signal.signal(signal.SIGINT, interrupt)
try:
    with (DATA / 'launch.log').open('w') as log:
        server = subprocess.Popen([sys.executable, str(ROOT / 'server.py'), '--no-browser'], cwd=ROOT, stdout=log, stderr=log)
        url = ''
        for _ in range(100):
            if server.poll() is not None:
                raise RuntimeError('启动失败，请查看 data/launch.log')
            lines = (DATA / 'launch.log').read_text().splitlines()
            if lines and lines[0].startswith('http://127.0.0.1:'):
                url = lines[0]
                break
            time.sleep(.1)
        if not url:
            raise RuntimeError('服务启动超时，请查看 data/launch.log')
        if os.name == 'nt':
            desktop = subprocess.Popen([sys.executable, str(ROOT / 'windows_desktop.py'), url], cwd=ROOT)
        else:
            binary = DATA / 'companion-desktop'
            source = ROOT / 'Desktop.swift'
            if not binary.exists() or source.stat().st_mtime > binary.stat().st_mtime:
                print('正在准备桌面窗口…', flush=True)
                subprocess.run(['swiftc','-module-cache-path','/private/tmp/companion-swift-cache',str(source),'-o',str(binary)], check=True)
            desktop = subprocess.Popen([str(binary),url], cwd=ROOT)
        code = desktop.wait()
        if code:
            raise RuntimeError('Desktop failed to start; check platform dependencies and launch.log.')
except KeyboardInterrupt:
    pass
except (RuntimeError, OSError, subprocess.CalledProcessError) as exc:
    print(str(exc), file=sys.stderr)
finally:
    for process in (desktop,server):
        if process and process.poll() is None:
            process.terminate()
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait()
