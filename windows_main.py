"""Single-process EXE entry point: embedded server + Qt, never spawn this EXE as Python."""
import multiprocessing
multiprocessing.freeze_support()
import json
import io
import os
from pathlib import Path
import sys
import tempfile
import threading
import traceback
from app_paths import data_directory
from app_version import APP_VERSION, prepare_user_data

ROOT=Path(__file__).resolve().parent

def self_test(output):
    """Run on Windows build workers, report native libraries and real bundled resources."""
    report={'version':APP_VERSION,'ok':False,'frozen':bool(getattr(sys,'frozen',False)),'platform':sys.platform}
    captured=io.StringIO()
    previous_stderr=sys.stderr
    sys.stderr=captured
    try:
        if sys.platform!='win32':raise RuntimeError('EXE self-test requires Windows')
        from PySide6.QtWebEngineWidgets import QWebEngineView
        from PySide6.QtTextToSpeech import QTextToSpeech
        report['speech_module']='QtTextToSpeech imported'
        from PIL import Image
        import psutil
        import numpy as np
        from rapidocr_onnxruntime import RapidOCR
        engine=RapidOCR();engine(np.zeros((64,128,3),dtype=np.uint8))
        report['ocr']='native inference passed'
        for name in ['web/index.html','web/sprites.js','web/game-watch.js','assets/yeli-reference-v1.png','skills/hex-aram/SKILL.md']:
            if not (ROOT/name).is_file():raise RuntimeError('Missing bundled resource: '+name)
        manifest=json.loads((ROOT/'assets/actions/manifest.json').read_text(encoding='utf-8'))
        for action in manifest['actions'].values():
            with Image.open(ROOT/'assets/actions'/action['file']) as image:image.verify()
        with tempfile.TemporaryDirectory(prefix='yeli-exe-test-') as directory:
            os.environ['COMPANION_DATA_DIR']=directory
            import server
            http=server.ThreadingHTTPServer(('127.0.0.1',0),server.Handler)
            worker=threading.Thread(target=http.serve_forever,daemon=True);worker.start()
            try:
                import urllib.request
                opener=urllib.request.build_opener(urllib.request.ProxyHandler({}))
                req=urllib.request.Request('http://127.0.0.1:'+str(http.server_port)+'/api/state',data=b'{}',headers={'X-Companion-Token':server.TOKEN})
                with opener.open(req,timeout=10) as response:state=json.load(response)
                if 'settings' not in state:raise RuntimeError('Local API failed')
                with opener.open('http://127.0.0.1:'+str(http.server_port)+'/',timeout=10) as response:
                    if b'__TOKEN__' in response.read():raise RuntimeError('Web token was not injected')
            finally:
                http.shutdown();http.server_close();worker.join(2)
        report.update(ok=True,assets=len(manifest['actions']),api='passed')
    except Exception:report['error']=traceback.format_exc()
    finally:
        sys.stderr=previous_stderr
        if captured.getvalue():report['runtime_log']=captured.getvalue()[-12000:]
    Path(output).write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    return 0 if report['ok'] else 1

def main():
    if '--self-test' in sys.argv:
        return self_test(sys.argv[sys.argv.index('--self-test')+1])
    if sys.platform!='win32':raise RuntimeError('This entry point is for Windows')
    data=data_directory(ROOT);data.mkdir(parents=True,exist_ok=True)
    os.environ['COMPANION_DATA_DIR']=str(data)
    # In a windowed frozen build stdout/stderr are None; give libraries a real log.
    log=(data/'launch.log').open('a',encoding='utf-8',buffering=1)
    sys.stdout=sys.stderr=log
    import msvcrt
    lock=(data/'instance.lock').open('a+')
    try:
        lock.seek(0)
        if not lock.read(1):lock.write('0');lock.flush()
        lock.seek(0);msvcrt.locking(lock.fileno(),msvcrt.LK_NBLCK,1)
    except OSError:
        (data/'show-request').write_text('show',encoding='utf-8');lock.close();return 0
    http=None;stop=threading.Event()
    try:
        prepare_user_data(data)
        import server
        from windows_desktop import run
        http=server.ThreadingHTTPServer(('127.0.0.1',0),server.Handler)
        threading.Thread(target=http.serve_forever,daemon=True).start()
        threading.Thread(target=server.BACKUPS.run,args=(stop,),daemon=True).start()
        url='http://127.0.0.1:'+str(http.server_port)
        code=run(url)
        return code
    finally:
        stop.set()
        if http:
            server.WATCH.halt();http.shutdown();http.server_close()
        lock.close()

if __name__=='__main__':
    try:sys.exit(main())
    except Exception:
        data=data_directory(ROOT);data.mkdir(parents=True,exist_ok=True)
        error=traceback.format_exc()
        with (data/'startup-error.log').open('a',encoding='utf-8') as stream:stream.write(error+'\n')
        if sys.platform=='win32':
            import ctypes
            ctypes.windll.user32.MessageBoxW(None,'夜璃启动失败。错误信息已保存到：\n'+str(data/'startup-error.log'),'夜璃',0x10)
        sys.exit(1)
