let watchLatestId=null,watchPolling=false;
function showOverlayStatus(message){const label=document.querySelector('#overlay-status');if(label)label.textContent=message}
async function pollGameWatch(){
 if(watchPolling)return;watchPolling=true;
 try{const status=await api('game-watch');
  const label=document.querySelector('#watch-status');if(label)label.textContent=status.status+' · 本小时 '+status.requests_hour_count+' 次请求'+(status.error?'\n'+status.error:'');
  if(status.enabled&&status.latest&&status.latest.id!==watchLatestId&&!busy&&!typing&&!(typeof voiceSpeaking!=='undefined'&&voiceSpeaking)&&!down&&!waiting&&!activeReminder&&$('#panel').hidden&&$('#compose').hidden&&$('#menu').hidden){watchLatestId=status.latest.id;if(dock){native('reveal');setDock('')}speak(status.latest.reply,'gentle')}
 }catch{}finally{watchPolling=false}
}
setInterval(pollGameWatch,3000);
async function renderGameWatch(panel,error){
 const initial=await api('game-watch');
 panel.append(el('small','英雄联盟请在 Esc → 视频中选择「无边框」，再开启游戏模式。普通悬浮窗不保证覆盖独占全屏。'));
 const overlay=el('small',window.yeliOverlayError||'');overlay.id='overlay-status';overlay.setAttribute('role','status');panel.append(overlay);
 const gameToggle=el('input');gameToggle.type='checkbox';gameToggle.checked=!!state.settings.game_mode;gameToggle.onchange=async()=>{try{await toggleGameMode()}finally{gameToggle.checked=!!state.settings.game_mode}};panel.append(el('label','游戏模式：无边框窗口下置顶，语音回复，不显示气泡'),gameToggle);
 panel.append(el('small','Windows 游戏陪玩：开启后等待指定游戏进入前台，本地识别决策界面；只有触发建议时才发送游戏画面、识别文字和所选技能给你配置的 AI。切换到其他软件或最小化游戏会暂停采集。请使用支持图片输入的模型；画面不写入磁盘。'));
 const label=el('small');label.id='watch-status';label.style.whiteSpace='pre-wrap';label.textContent=initial.status+(initial.error?'\n'+initial.error:'');panel.append(label);
 if(!initial.supported)panel.append(el('small','当前电脑不是 Windows。可以先配置和导入技能，屏幕观察需要在 Windows 运行。'));
 const skills=(await api('skills')).skills.filter(s=>s.enabled&&s.files['game-watch.json']);
 const select=el('select');select.setAttribute('aria-label','陪玩技能');for(const skill of skills){const option=el('option',skill.name);option.value=skill.id;select.append(option)}
 panel.append(el('label','已启用的陪玩技能'),select);if(!skills.length)panel.append(el('small','先到“技能”导入并启用海克斯大乱斗技能包，然后返回这里。'));
 const fields={};for(const [key,title]of [['champion','当前英雄（可留空，由画面识别）'],['version','游戏版本（建议填写，避免旧资料误用）'],['interval','本地观察间隔（秒，1—10）'],['cooldown','两次 AI 分析最短间隔（秒，10—300）'],['hourly_limit','每小时最多 AI 请求次数（1—120）']]){const input=el('input');input.type=['champion','version'].includes(key)?'text':'number';input.value=initial.config[key];input.setAttribute('aria-label',title);fields[key]=input;panel.append(el('label',title),input)}
 const save=el('button','保存配置'),start=el('button','开启自动陪玩'),stop=el('button','停止观察');start.disabled=!initial.supported||!skills.length||initial.enabled;
 async function persist(){const config={};for(const [key,input]of Object.entries(fields))config[key]=input.type==='number'?Number(input.value):input.value;await api('game-watch',{action:'configure',config})}
 save.onclick=async()=>{save.disabled=true;try{await persist();error.textContent='配置已保存'}catch(e){error.textContent=e.message}finally{save.disabled=false}};
 start.onclick=async()=>{start.disabled=true;try{await persist();await api('game-watch',{action:'start',skill_id:Number(select.value)});error.textContent='已开启。关闭面板后，建议会显示在夜璃头顶。';await pollGameWatch()}catch(e){error.textContent=e.message;start.disabled=false}};
 stop.onclick=async()=>{try{await api('game-watch',{action:'stop'});await openPanel('gamewatch')}catch(e){error.textContent=e.message}};
 panel.append(save,start,stop,el('small','开启只在本次运行生效，重启后默认关闭。界面识别词和观察区域可在技能包 game-watch.json 中调整。首次识别和模型回复可能有延迟；Windows 全屏游戏捕获尚需实测，优先使用无边框窗口。'));
 if(initial.latest)panel.append(el('h3','最近建议'),el('div',initial.latest.reply));
 regions();
}
