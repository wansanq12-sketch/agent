let reminderPolling=false,reminderReturnDot=false;
function reminderBlocked(){
 return document.hidden||busy||waiting||pending||typing||down||!$('#panel').hidden||!$('#menu').hidden||!$('#compose').hidden||!$('#bubble').hidden||['held','fall','land'].includes(currentMotion);
}
function hideReminder(){clearTimeout(reminderTimer);activeReminder=null;$('#reminder').hidden=true;if(reminderReturnDot&&$('#bubble').hidden)$('#dot').hidden=false;reminderReturnDot=false;regions()}
function interruptReminder(){const reminder=activeReminder;if(!reminder)return;hideReminder();if(!reminder.preview)api('reminders',{action:'snooze',id:reminder.id}).catch(()=>{})}
function showReminder(reminder){
 if(activeReminder)return false;
 if(reminder.expires_at<=Date.now())return false;
 activeReminder=reminder;reminderReturnDot=!$('#dot').hidden;$('#dot').hidden=true;
 const water=reminder.kind==='water';
 $('#reminder-kind').textContent=water?'喝水提醒':'活动提醒';
 $('#reminder-text').textContent=water?'哥哥，停一小会儿，喝两口水吧。':'哥哥，起来走走、活动一下吧，陪你歇一会儿。';
 $('#reminder-done').textContent=water?'喝过了':'活动过了';$('#reminder-error').textContent='';
 if(dock){native('reveal');setDock('')}
 $('#reminder').hidden=false;
 if(typeof petMotion==='function')petMotion(water?'gentle':'stretch',null,'interaction');
 reminderTimer=setTimeout(hideReminder,Math.max(0,reminder.expires_at-Date.now()));regions();return true;
}
async function reminderRespond(action){
 const reminder=activeReminder;if(!reminder)return;
 for(const id of ['#reminder-done','#reminder-snooze','#reminder-skip'])$(id).disabled=true;
 try{
  if(!reminder.preview)await api('reminders',{action,id:reminder.id});
  if(activeReminder?.id===reminder.id){hideReminder();interacted()}
 }catch(e){if(activeReminder?.id===reminder.id)$('#reminder-error').textContent=e.message}
 finally{for(const id of ['#reminder-done','#reminder-snooze','#reminder-skip'])$(id).disabled=false}
}
$('#reminder-done').onclick=()=>reminderRespond('done');$('#reminder-snooze').onclick=()=>reminderRespond('snooze');$('#reminder-skip').onclick=()=>reminderRespond('skip');
async function checkReminders(){
 if(!state||reminderPolling||activeReminder||reminderBlocked())return;
 reminderPolling=true;
 try{const result=await api('reminders',{action:'poll',hour:new Date().getHours()});if(result.reminder){if(reminderBlocked())await api('reminders',{action:'defer',id:result.reminder.id});else showReminder(result.reminder)}}catch(e){/* Keep timers on the server; a later check retries without showing duplicates. */}finally{reminderPolling=false}
}
function previewReminder(kind){
 if(activeReminder||busy||pending||typing||down)return false;
 $('#panel').hidden=true;panelGeneration++;$('#compose').hidden=true;
 return showReminder({id:'preview-'+Date.now(),kind,expires_at:Date.now()+30000,preview:true});
}
function reconcileReminders(){
 if(activeReminder&&!activeReminder.preview&&state?.settings?.[activeReminder.kind==='water'?'water_reminder_enabled':'move_reminder_enabled']===false)hideReminder();
}
setInterval(checkReminders,10000);
