const motionCanvas=document.createElement('canvas');motionCanvas.id='motion-canvas';motionCanvas.width=400;motionCanvas.height=560;
motionCanvas.style.cssText='position:absolute;inset:0;width:100%;height:100%;pointer-events:none';pet.append(motionCanvas);
const manifest=window.YeliSprites,motionNames=Object.keys(manifest.actions),FRAME_COUNT=Math.max(...Object.values(manifest.actions).map(a=>a.frames.length));
const player=new YeliFramePlayer.SpritePlayer(motionCanvas,manifest,'/assets/actions/');
let currentMotion='idle',motionFrame=0,motionStarted=0,motionReturn=null,motionDuration=null,lastPetActivity=Date.now(),motionGeneration=0,deferredEmotion=null,lastDailyAction=Date.now();
let renderTimer=null;const pendingLoads=new Set();
function ensureMotion(name){
 if(player.cache?.[name]||pendingLoads.has(name))return;
 pendingLoads.add(name);
 player.load(name).then(()=>{pendingLoads.delete(name);if(currentMotion===name){$('#reload-motion').hidden=true;renderMotion(performance.now())}}).catch(()=>{pendingLoads.delete(name);if(currentMotion===name){$('#reload-motion').hidden=false;if(typeof regions==='function')regions()}});
}
$('#reload-motion').onclick=()=>{ensureMotion(currentMotion)};
function currentPetMask(){return motionCanvas.hidden?null:player.hitMask()}

function frameAt(name,elapsed){return YeliFramePlayer.frameAt(manifest.actions[name],elapsed,motionDuration)}
function petMotion(name,durationOverride,reason='event'){
 const config=state?.settings||{};
 if(name==='sleep'&&config.sleep_enabled===false)return false;
 if(['read','music','game','stretch'].includes(name)&&config.daily_actions_enabled===false)return false;
 if(!YeliBehavior.canTransition(currentMotion,name,{reason,typing:!!typing,busy:!!busy}))return false;
 if(!motionNames.includes(name))name='idle';
 if(currentMotion===name&&['held','fall','sleep'].includes(name))return;
 clearTimeout(motionReturn);const generation=++motionGeneration;currentMotion=name;motionStarted=performance.now();motionDuration=Number.isFinite(durationOverride)&&durationOverride>0?durationOverride:null;
 $('#reload-motion').hidden=true;ensureMotion(name);renderMotion(performance.now());
 if(!['idle','held','fall','sleep','talk'].includes(name)){
  const duration=['read','music','game'].includes(name)?12000:(motionDuration||manifest.actions[name].durationMs);
  motionReturn=setTimeout(()=>{if(generation===motionGeneration)resumeMotion()},duration);
 }
}
function beginSpeechMotion(){deferredEmotion=null;petMotion('talk')}
function finishSpeechMotion(emotion){if(['held','fall','land'].includes(currentMotion)){deferredEmotion=emotion;return}act(emotion,'complete')}
function resumeMotion(){
 if(typing){petMotion('talk',null,'complete');return}
 if(deferredEmotion){const emotion=deferredEmotion;deferredEmotion=null;act(emotion,'complete');return}
 petMotion(busy?'think':'idle',null,'complete');
}
function reconcileRuntime(){
 if(state?.settings?.sleep_enabled===false&&currentMotion==='sleep')petMotion('idle',null,'wake');
 if(state?.settings?.daily_actions_enabled===false&&['read','music','game','stretch'].includes(currentMotion))petMotion('idle',null,'complete');
}
function wakePet(){lastPetActivity=Date.now();if(currentMotion==='sleep')petMotion('idle',null,'wake')}

function sleepAfterMs(){return Math.max(1,Number(state?.settings?.sleep_after||10))*60000}
function maySleep(){return !(typeof activeReminder!=='undefined'&&activeReminder)&&!busy&&!waiting&&!pending&&!down&&$('#panel').hidden&&$('#compose').hidden&&!typing}
function renderMotion(now){
 clearTimeout(renderTimer);if(document.hidden)return;
 const elapsed=Math.max(0,now-motionStarted);motionFrame=frameAt(currentMotion,elapsed);
 const drawn=player.draw(currentMotion,elapsed,motionDuration);
 motionCanvas.hidden=!drawn;$('#portrait').hidden=drawn;
 if(typeof regions==='function')regions();
 const delay=YeliFramePlayer.nextFrameDelay(manifest.actions[currentMotion],elapsed,motionDuration);
 if(Number.isFinite(delay))renderTimer=setTimeout(()=>renderMotion(performance.now()),Math.ceil(delay));
}
document.addEventListener('visibilitychange',()=>{if(document.hidden)clearTimeout(renderTimer);else renderMotion(performance.now())});
ensureMotion('idle');renderMotion(performance.now());
const baseAct=act;act=function(kind,reason='event'){baseAct(kind);if(['held','fall'].includes(currentMotion))return;petMotion({'happy':'wave','touch-head':'hair','touch-body':'gentle','think':'think','magic':'magic','gentle':'gentle','idle':'idle','talk':'talk'}[kind]||'idle',null,kind.startsWith('touch-')?'interaction':reason)};
const previousDown=pet.onpointerdown;pet.onpointerdown=e=>{wakePet();previousDown(e)};
const previousMove=pet.onpointermove;pet.onpointermove=e=>{previousMove(e);if(down&&moved){if(!down.interactedDrag){down.interactedDrag=true;if(typeof interacted==='function')interacted()}wakePet();petMotion('held')}};
const previousUp=pet.onpointerup;pet.onpointerup=e=>{const dragged=!!down&&moved;wakePet();previousUp(e);if(dragged&&!window.webkit?.messageHandlers?.desktop)petMotion('land')};
pet.onpointercancel=()=>{const dragged=!!down&&moved;down=null;wakePet();if(dragged){native('dragEnd');if(!window.webkit?.messageHandlers?.desktop)petMotion('land')}};
document.addEventListener('keydown',wakePet);$('#input').addEventListener('input',wakePet);
setInterval(()=>{
 const config=state?.settings||{},now=Date.now();
 if(config.daily_actions_enabled!==false&&now-lastDailyAction>=(config.daily_action_interval||90)*1000&&maySleep()&&!dock&&currentMotion==='idle'&&now-lastPetActivity<sleepAfterMs()){
  lastDailyAction=now;petMotion(['read','music','game','stretch'][Math.floor(Math.random()*4)]);
 }
 if(config.sleep_enabled!==false&&maySleep()&&!['held','fall','land','sleep'].includes(currentMotion)&&now-lastPetActivity>=sleepAfterMs())petMotion('sleep');
},1000);

