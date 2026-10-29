"""Decision-screen observer; no game memory access, input injection or script execution."""
import base64
import hashlib
import io
import json
import os
import re
import threading
import time
from pathlib import Path

DEFAULTS = dict(interval=2, cooldown=20, hourly_limit=60, champion='', version='')

def validate_settings(data):
    result = dict(DEFAULTS)
    for key, low, high in [('interval',1,10),('cooldown',10,300),('hourly_limit',1,120)]:
        value=data.get(key,result[key])
        if isinstance(value,bool) or not isinstance(value,int) or not low<=value<=high:
            raise ValueError(f'{key} 应在 {low} 至 {high} 之间')
        result[key]=value
    for key in ('champion','version'):
        result[key]=str(data.get(key,''))[:100]
    return result

def decision_stage(text, profile):
    compact=re.sub(r'\s+','',text).lower()
    for stage, groups in profile['triggers'].items():
        if any(all(word.lower() in compact for word in group) for group in groups):return stage
    return None

def signature(stage, text):
    # Numbers and whitespace (timers/gold) must not trigger another identical recommendation.
    clean=re.sub(r'[\d\s]+','',text).lower()
    return hashlib.sha256((stage+clean).encode()).hexdigest()

def load_profile(skill):
    encoded=skill['files'].get('game-watch.json')
    if not encoded:raise ValueError('此技能没有 game-watch.json 陪玩配置')
    try:profile=json.loads(base64.b64decode(encoded).decode('utf-8'))
    except (ValueError,UnicodeError):raise ValueError('陪玩配置无法读取')
    process=profile.get('process','')
    if not isinstance(process,str) or not process.lower().endswith('.exe') or '/' in process or '\\' in process:
        raise ValueError('陪玩配置需要填写游戏进程文件名')
    crop=profile.get('crop',[.1,.12,.9,.88])
    if not isinstance(crop,list) or len(crop)!=4 or any(isinstance(v,bool) or not isinstance(v,(int,float)) or not 0<=v<=1 for v in crop) or crop[0]>=crop[2] or crop[1]>=crop[3]:
        raise ValueError('观察区域应为 0 至 1 的左、上、右、下坐标')
    triggers=profile.get('triggers',{})
    if not isinstance(triggers,dict) or not triggers or len(triggers)>5:raise ValueError('技能缺少决策界面识别词')
    for stage, groups in triggers.items():
        if stage not in ('augment','shop','champion') or not isinstance(groups,list) or not groups or len(groups)>10:raise ValueError('界面识别词格式错误')
        for group in groups:
            if not isinstance(group,list) or not 1<=len(group)<=5 or any(not isinstance(w,str) or not w.strip() or len(w)>40 for w in group):raise ValueError('界面识别词格式错误')
    return dict(process=process,crop=crop,triggers=triggers)

class WindowsCapture:
    def __init__(self):
        if os.name!='nt':raise ValueError('游戏观察目前需要在 Windows 电脑运行')
        import ctypes
        from ctypes import wintypes
        self.ctypes=ctypes;self.wintypes=wintypes;self.user=ctypes.WinDLL('user32',use_last_error=True)
        self.user.GetForegroundWindow.restype=wintypes.HWND
        self.user.GetWindowThreadProcessId.argtypes=[wintypes.HWND,ctypes.POINTER(wintypes.DWORD)]
        self.user.IsWindowVisible.argtypes=[wintypes.HWND];self.user.IsIconic.argtypes=[wintypes.HWND]
        from rapidocr_onnxruntime import RapidOCR
        self.ocr=RapidOCR()
    def read(self, profile):
        import psutil
        import numpy as np
        from PIL import ImageGrab, ImageStat
        hwnd=self.user.GetForegroundWindow()
        if not hwnd or not self.user.IsWindowVisible(hwnd) or self.user.IsIconic(hwnd):return None
        pid=self.wintypes.DWORD();self.user.GetWindowThreadProcessId(hwnd,self.ctypes.byref(pid))
        try:name=psutil.Process(pid.value).name()
        except (psutil.Error,OSError):return None
        if name.lower()!=profile['process'].lower():return None
        image=ImageGrab.grab(window=int(hwnd)).convert('RGB')
        if image.width<320 or image.height<240 or max(ImageStat.Stat(image.resize((32,32))).stddev)<2:raise ValueError('游戏画面为空或黑屏，请使用无边框窗口模式')
        image.thumbnail((1600,1000))
        x0,y0,x1,y1=profile['crop'];crop=image.crop((int(x0*image.width),int(y0*image.height),int(x1*image.width),int(y1*image.height)))
        result,_=self.ocr(np.asarray(crop)[:,:,::-1])
        text='\n'.join(str(row[1]) for row in (result or []))[:12000]
        return dict(identity=str(pid.value)+':'+str(hwnd),image=image,text=text)

class GameWatch:
    def __init__(self, data, skills, complete, capture_factory=WindowsCapture):
        self.path=Path(data)/'game-watch.json';self.skills=skills;self.complete=complete;self.capture_factory=capture_factory
        self.lock=threading.RLock();self.stop=threading.Event();self.thread=None;self.generation=0;self.requests=[];self.latest=None
        try:self.config=validate_settings(json.loads(self.path.read_text(encoding='utf-8')))
        except (OSError,ValueError):self.config=dict(DEFAULTS)
        self.state=dict(enabled=False,status='未开启',requests_hour=0,error='',skill_id=None)
    def status(self):
        with self.lock:
            self.requests=[t for t in self.requests if time.monotonic()-t<3600]
            return dict(**self.state,config=dict(self.config),requests_hour_count=len(self.requests),latest=self.latest)
    def configure(self, data):
        config=validate_settings(data)
        with self.lock:
            self.config=config
            temp=self.path.with_suffix('.tmp');temp.write_text(json.dumps(config,ensure_ascii=False),encoding='utf-8');temp.replace(self.path)
        return self.status()
    def start(self, skill_id):
        skill=next((s for s in self.skills() if s['id']==skill_id and s['enabled']),None)
        if not skill:raise ValueError('请先导入并启用游戏陪玩技能')
        profile=load_profile(skill)
        with self.lock:
            if self.state['enabled'] and self.thread and self.thread.is_alive():raise ValueError('请先停止当前观察，再重新开启')
            # Construct on Windows before reporting enabled; missing OCR dependencies fail visibly.
            try:
                capture=self.capture_factory()
            except ImportError:
                raise ValueError('观察组件缺失，请运行“安装或更新-Windows.cmd”后重试')
            self.stop=threading.Event();self.generation+=1;generation=self.generation
            self.state.update(enabled=True,status='等待游戏进入前台',error='',skill_id=skill_id);self.latest=None
            self.thread=threading.Thread(target=self._run,args=(skill,profile,capture,generation,self.stop),daemon=True);self.thread.start()
        return self.status()
    def halt(self):
        with self.lock:
            self.generation+=1;self.stop.set();self.state.update(enabled=False,status='已停止',error='')
        return self.status()
    def _run(self, skill, profile, capture, generation, stop):
        last_sent=0;seen=set();identity=None;context={};last_attempt=0;failures=0
        while not stop.is_set():
            try:
                with self.lock:
                    if generation!=self.generation:return
                    config=dict(self.config)
                current=next((s for s in self.skills() if s['id']==skill['id'] and s['enabled']),None)
                if not current:raise ValueError('陪玩技能已停用或删除，请重新选择技能')
                if current['content']!=skill['content'] or current['files']!=skill['files']:raise ValueError('技能已修改，请停止后重新开启观察')
                frame=capture.read(profile)
                if not frame:
                    with self.lock:
                        if generation==self.generation:self.state.update(status='等待游戏进入前台',error='')
                    stop.wait(config['interval']);continue
                if frame['identity']!=identity:identity=frame['identity'];seen.clear();context={}
                stage=decision_stage(frame['text'],profile)
                key=signature(stage or '',frame['text'])
                now=time.monotonic()
                with self.lock:
                    if generation!=self.generation or stop.is_set():return
                    self.requests=[t for t in self.requests if now-t<3600]
                    self.state.update(status='观察中 · '+({'augment':'强化选择','shop':'商店','champion':'英雄选择'}.get(stage,'等待决策画面')),error='')
                    allowed=stage and key not in seen and now-last_sent>=config['cooldown'] and now-last_attempt>=config['cooldown'] and len(self.requests)<config['hourly_limit']
                    if len(self.requests)>=config['hourly_limit']:self.state['status']='已达每小时请求上限，继续本地观察'
                if allowed and not stop.is_set():
                    from skills_manager import SkillManager
                    image=frame['image'];out=io.BytesIO();image.save(out,format='JPEG',quality=80)
                    url='data:image/jpeg;base64,'+base64.b64encode(out.getvalue()).decode()
                    system='你是夜璃的海克斯大乱斗建议助手。只分析画面中可见信息，不猜测隐藏信息，不声称执行了操作。只输出 JSON：{"decision":true或false,"stage":"augment或shop或champion","champion":"可识别的英雄","reply":"不超过180字的建议","known_augments":[],"known_items":[]}。非决策画面 decision=false。无法识别的名称明确说不确定。缺少本版本数据时只提供机制推理，不编造胜率、数值或最强结论。\n'+SkillManager.context_for(current)
                    prompt='已识别文字：'+frame['text']+'\n用户指定英雄：'+config['champion']+'；版本：'+(config['version'] or '未知')+'\n本局近期信息（可能过时，以画面为准）：'+json.dumps(context,ensure_ascii=False)
                    with self.lock:
                        if generation!=self.generation:return
                        self.requests.append(now);last_attempt=now;self.state['status']='正在分析决策画面'
                    answer=self.complete([dict(role='system',content=system),dict(role='user',content=[dict(type='text',text=prompt),dict(type='image_url',image_url={'url':url})])])
                    parsed=json.loads(answer.strip().removeprefix('```json').removesuffix('```').strip())
                    if not isinstance(parsed,dict) or not isinstance(parsed.get('decision'),bool):raise ValueError('视觉模型返回格式不正确，请确认接口支持图片输入')
                    with self.lock:
                        if generation!=self.generation or stop.is_set():return
                        seen.add(key);last_sent=now;failures=0
                        if parsed['decision'] and isinstance(parsed.get('reply'),str) and parsed['reply'].strip():
                            self.latest=dict(id=time.time_ns(),reply=parsed['reply'][:1000],stage=stage,time=time.time())
                            context={k:parsed[k] for k in ('champion','known_augments','known_items') if k in parsed}
                            self.state['status']='建议已更新'
            except Exception as exc:
                with self.lock:
                    if generation!=self.generation:return
                    failures+=1;self.state.update(error=str(exc)[:300],status='观察遇到问题')
                    if failures>=3:
                        self.state.update(enabled=False,status='连续失败，已停止');stop.set()
            stop.wait(config['interval'])
