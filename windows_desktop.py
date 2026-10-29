"""Windows transparent desktop host. Shares the same local server and web UI."""
import base64
import ctypes
from ctypes import wintypes
import json
import os
import sys
import time
from pathlib import Path
from urllib.parse import urlsplit
from PySide6.QtCore import QFile, QIODevice, QObject, QPoint, Qt, QTimer, QUrl, Slot
from PySide6.QtGui import QAction, QColor, QCursor, QIcon, QPainter, QPixmap
from PySide6.QtWidgets import QApplication, QFileDialog, QMenu, QSystemTrayIcon, QVBoxLayout, QWidget
from PySide6.QtWebChannel import QWebChannel
from PySide6.QtWebEngineCore import QWebEnginePage, QWebEngineProfile, QWebEngineScript
from PySide6.QtWebEngineWidgets import QWebEngineView

ROOT = Path(__file__).resolve().parent
DATA = Path(os.environ.get('COMPANION_DATA_DIR', str(ROOT / 'data')))

class LocalPage(QWebEnginePage):
    def __init__(self, profile, parent, origin):
        super().__init__(profile, parent)
        self.origin = origin
    def acceptNavigationRequest(self, url, kind, main):
        # Never expose the desktop bridge to external pages.
        return url.toString().rstrip('/') == self.origin.rstrip('/')

class Bridge(QObject):
    def __init__(self, host):
        super().__init__(host); self.host = host
    @Slot(str)
    def postMessage(self, value):
        try:self.host.handle(json.loads(value))
        except (ValueError, TypeError, KeyError):pass

class PetWindow(QWidget):
    def __init__(self, url):
        super().__init__()
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.Tool | Qt.WindowType.WindowStaysOnTopHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
        self.resize(440,700)
        self.dock='';self.rects=[];self.mask=None;self.dragging=False;self.peek=None;self.game_mode=False
        self.profile=QWebEngineProfile(self)
        self.view=QWebEngineView(self)
        self.page=LocalPage(self.profile,self.view,url);self.page.setBackgroundColor(QColor(0,0,0,0));self.view.setPage(self.page)
        self.view.setStyleSheet('background:transparent');self.view.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        layout=QVBoxLayout(self);layout.setContentsMargins(0,0,0,0);layout.addWidget(self.view)
        self.channel=QWebChannel(self.page);self.bridge=Bridge(self);self.channel.registerObject('desktop',self.bridge);self.page.setWebChannel(self.channel)
        source=QFile(':/qtwebchannel/qwebchannel.js');source.open(QIODevice.OpenModeFlag.ReadOnly)
        channel_js=bytes(source.readAll()).decode();source.close()
        script=QWebEngineScript();script.setName('yeli-desktop');script.setInjectionPoint(QWebEngineScript.InjectionPoint.DocumentCreation);script.setWorldId(QWebEngineScript.ScriptWorldId.MainWorld)
        script.setSourceCode("""window.__nativeQueue=[];window.webkit={messageHandlers:{desktop:{postMessage:function(v){if(window.__desktop)window.__desktop.postMessage(JSON.stringify(v));else window.__nativeQueue.push(v)}}}};
"""+channel_js+"""\nnew QWebChannel(qt.webChannelTransport,function(c){window.__desktop=c.objects.desktop;for(const v of window.__nativeQueue)window.__desktop.postMessage(JSON.stringify(v));window.__nativeQueue=[];});""")
        self.page.scripts().insert(script)
        self.fall=QTimer(self);self.fall.setInterval(16);self.fall.timeout.connect(self.fall_tick)
        self.poll=QTimer(self);self.poll.setInterval(500);self.poll.timeout.connect(self.poll_events);self.poll.start()
        self.hit_timer=QTimer(self);self.hit_timer.setInterval(30);self.hit_timer.timeout.connect(self.update_passthrough);self.hit_timer.start()
        self.passthrough=None
        self.restore()
        self.page.loadFinished.connect(lambda ok:self.js('setDock('+json.dumps(self.dock)+');regions()') if ok else None)
        self.view.load(QUrl(url))
        icon=QPixmap(32,32);icon.fill(Qt.GlobalColor.transparent);p=QPainter(icon);p.setPen(QColor('#bedbff'));p.setFont(self.font());p.drawText(icon.rect(),Qt.AlignmentFlag.AlignCenter,'☾');p.end()
        self.tray=QSystemTrayIcon(QIcon(icon),self);self.tray.setToolTip('夜璃')
        menu=QMenu();menu.addAction('显示夜璃',self.reveal);menu.addAction('游戏陪玩',lambda:self.js("openPanel('gamewatch')"));menu.addAction('游戏置顶模式',lambda:self.js('void toggleGameMode()'));menu.addAction('退出',lambda:self.js('void quitPet()'));self.tray.setContextMenu(menu);self.tray.activated.connect(lambda reason:self.reveal() if reason==QSystemTrayIcon.ActivationReason.Trigger else None);self.tray.show()
        QApplication.instance().screenAdded.connect(lambda _:self.recover());QApplication.instance().screenRemoved.connect(lambda _:QTimer.singleShot(100,self.recover))
    def js(self, text):self.page.runJavaScript(text)
    def screen_area(self):return (QApplication.screenAt(self.frameGeometry().center()) or QApplication.primaryScreen()).availableGeometry()
    def bottom(self):return self.screen_area().bottom()+1-self.height()-8
    def save(self):
        (DATA/'windows-placement.json').write_text(json.dumps({'x':self.x(),'dock':self.dock}),encoding='utf-8')
    def restore(self):
        area=QApplication.primaryScreen().availableGeometry();self.resize(440,min(700,area.height()-16))
        try:config=json.loads((DATA/'windows-placement.json').read_text());x=int(config['x']);self.dock=config.get('dock','')
        except (OSError,ValueError,KeyError):x=area.right()-self.width()-10
        self.move(max(area.left(),min(x,area.right()-self.width())),area.bottom()+1-self.height()-8)
        if self.dock not in ('left','right'):self.dock=''
        self.snap()
    def snap(self):
        area=self.screen_area();x=self.x()
        if self.dock=='left':x=area.left()-350
        elif self.dock=='right':x=area.right()-89
        self.move(x,self.bottom())
    def recover(self):
        self.fall.stop();self.restore();self.js('handleDisplayChange('+json.dumps(self.dock)+')')
    def reveal(self):
        self.fall.stop();self.peek=None;area=self.screen_area();self.dock='';self.move(max(area.left(),min(self.x(),area.right()-self.width())),self.bottom());self.show();self.raise_();self.js("setDock('')");self.save()
    def handle(self, d):
        action=d.get('action')
        if action=='regions':
            self.rects=d.get('rects',[]);self.mask=d.get('pet')
            if self.mask:
                try:self.mask['decoded']=base64.b64decode(self.mask.get('bits',''))
                except ValueError:self.mask=None
        elif action=='dragStart':
            self.fall.stop();self.dragging=True;self.start=QCursor.pos();self.origin=self.pos();self.peek=None
        elif action=='drag' and self.dragging:self.move(self.origin+QCursor.pos()-self.start)
        elif action=='dragEnd' and self.dragging:
            self.dragging=False;area=(QApplication.screenAt(QCursor.pos()) or QApplication.primaryScreen()).availableGeometry();self.resize(440,min(700,area.height()-16))
            center=self.x()+(100 if self.dock=='right' else 340 if self.dock=='left' else 310)
            self.dock='left' if center<area.left()+80 else 'right' if center>area.right()-80 else ''
            x=area.left()-350 if self.dock=='left' else area.right()-89 if self.dock=='right' else max(area.left(),min(center-310,area.right()-self.width()))
            self.move(x,self.y());self.fall_origin=self.y();self.fall_target=area.bottom()+1-self.height()-8;self.fall_started=time.monotonic();self.js('setDock('+json.dumps(self.dock)+");petMotion('fall',1500)");self.fall.start()
        elif action=='reveal':self.reveal()
        elif action=='peek' and self.dock and self.peek is None:self.peek=self.pos();self.move(self.x()+(35 if self.dock=='left' else -35),self.y())
        elif action=='endPeek' and self.peek is not None:self.move(self.peek);self.peek=None
        elif action=='gameMode':self.game_mode=bool(d.get('enabled'));self.raise_()
        elif action=='quit':QApplication.quit()
        elif action=='export':
            filename,_=QFileDialog.getSaveFileName(self,'保存备份','夜璃备份.json','JSON (*.json)')
            if filename:Path(filename).write_text(str(d.get('content','')),encoding='utf-8')
    def fall_tick(self):
        t=min(1,(time.monotonic()-self.fall_started)/1.5);self.move(self.x(),round(self.fall_origin+(self.fall_target-self.fall_origin)*t*t))
        if t>=1:self.fall.stop();self.save();self.js("petMotion('land')")
    def poll_events(self):
        request=DATA/'show-request'
        if request.exists():request.unlink(missing_ok=True);self.reveal()
        if self.game_mode:
            # HWND_TOPMOST, SWP_NOSIZE | SWP_NOMOVE | SWP_NOACTIVATE
            user32=ctypes.WinDLL('user32',use_last_error=True);user32.SetWindowPos.argtypes=[wintypes.HWND,wintypes.HWND,ctypes.c_int,ctypes.c_int,ctypes.c_int,ctypes.c_int,wintypes.UINT]
            user32.SetWindowPos(int(self.winId()),-1,0,0,0,0,0x0013)
    def contains_interactive(self, point):
        x,y=point.x(),point.y()
        for r in self.rects:
            if r['x']<=x<r['x']+r['w'] and r['y']<=y<r['y']+r['h']:return True
        m=self.mask
        if m and m['x']<=x<m['x']+m['w'] and m['y']<=y<m['y']+m['h']*m.get('clip',1):
            col=int((x-m['x'])/m['w']*m['cols']);row=int((y-m['y'])/m['h']*m['rows']);index=row*m['cols']+col;bits=m.get('decoded',b'')
            return index//8<len(bits) and bool(bits[index//8] & (1 << (index%8)))
        return False
    def update_passthrough(self):
        transparent=not self.dragging and not self.contains_interactive(self.mapFromGlobal(QCursor.pos()))
        if transparent==self.passthrough:return
        user=ctypes.WinDLL('user32',use_last_error=True)
        get=user.GetWindowLongPtrW;get.argtypes=[wintypes.HWND,ctypes.c_int];get.restype=ctypes.c_ssize_t
        put=user.SetWindowLongPtrW;put.argtypes=[wintypes.HWND,ctypes.c_int,ctypes.c_ssize_t];put.restype=ctypes.c_ssize_t
        hwnd=int(self.winId());style=get(hwnd,-20)
        put(hwnd,-20,(style|0x80000|0x20) if transparent else (style & ~0x20))
        self.passthrough=transparent
    def nativeEvent(self, event_type, message):
        msg=wintypes.MSG.from_address(int(message))
        if msg.message==0x0084 and not self.dragging: # WM_NCHITTEST
            if not self.contains_interactive(self.mapFromGlobal(QCursor.pos())):return True,-1 # HTTRANSPARENT
        return super().nativeEvent(event_type,message)

def run(url):
    if sys.platform!='win32':raise SystemExit('此桌面入口仅供 Windows 使用')
    parsed=urlsplit(url)
    if parsed.scheme!='http' or parsed.hostname!='127.0.0.1':raise SystemExit('仅允许本机服务')
    app=QApplication(sys.argv);app.setQuitOnLastWindowClosed(False);window=PetWindow(url);window.show();return app.exec()

if __name__=='__main__':
    sys.exit(run(sys.argv[1]))
