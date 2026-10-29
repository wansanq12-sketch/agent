(function(root){
'use strict';
function invitationDue({settings,now,hour,last,lastWave,attempts,blocked}){
 if(blocked||!settings?.proactive||!settings.has_key||!settings.model||attempts>=(settings.max_attempts??2))return false;
 const a=+settings.quiet_start,b=+settings.quiet_end;
 const quiet=a===b?false:a<b?hour>=a&&hour<b:hour>=a||hour<b;
 if(quiet)return false;
 return attempts===0?now-last>=settings.interval*60000:now-lastWave>=Math.max(120,settings.retry_interval??Math.max(120,settings.interval*2))*60000;
}
const priorities={held:100,fall:90,land:80,talk:70,think:60,wave:50,hair:40,gentle:40,magic:40,sleep:20,read:10,music:10,game:10,stretch:10,idle:0};
function canTransition(current,next,{reason='event',typing=false,busy=false}={}){
 if(current===next||next==='held')return true;
 if(current==='held')return next==='fall'||next==='land';
 if(current==='fall')return next==='land';
 if(current==='land')return reason==='complete';
 if(reason==='complete'||(reason==='wake'&&current==='sleep'))return true;
 if((typing||busy)&&!['talk','think','fall','land'].includes(next))return false;
 if(reason==='interaction')return true;
 return (priorities[next]??0)>=(priorities[current]??0);
}
const api={invitationDue,canTransition,priorities};if(typeof module!=='undefined'&&module.exports)module.exports=api;else root.YeliBehavior=api;
})(typeof window!=='undefined'?window:globalThis);
