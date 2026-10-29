let voiceSpeaking=false,voiceStatusText='使用系统中文声音',voiceSequence=0;
function voiceStatus(available,message){voiceStatusText=message||(available?'声音已就绪':'系统语音不可用');const label=document.querySelector('#voice-status');if(label)label.textContent=voiceStatusText;if(!available)voiceFinished()}
function voiceFinished(){voiceSpeaking=false;if(typeof finishSpeechMotion==='function')finishSpeechMotion(typeof replyEmotion==='undefined'?'idle':replyEmotion)}
function stopVoice(){voiceSequence++;voiceSpeaking=false;if(window.webkit?.messageHandlers?.desktop)native('stopSpeech');else window.speechSynthesis?.cancel();voiceFinished()}
function playVoice(text,force=false){
 if(!text)return false;
 const sequence=++voiceSequence,settings=typeof state==='undefined'?{}:state?.settings||{};voiceSpeaking=true;
 const rate=settings.voice_rate??100,volume=settings.voice_volume??80;
 if(window.webkit?.messageHandlers?.desktop){native('speak',{text:String(text),rate,volume});return true}
 if(window.speechSynthesis&&typeof SpeechSynthesisUtterance!=='undefined'){
  window.speechSynthesis.cancel();const speech=new SpeechSynthesisUtterance(String(text));speech.lang='zh-CN';speech.rate=rate/100;speech.volume=volume/100;
  const chinese=window.speechSynthesis.getVoices().find(v=>v.lang?.toLowerCase().startsWith('zh'));if(chinese)speech.voice=chinese;
  speech.onend=()=>{if(sequence===voiceSequence)voiceFinished()};speech.onerror=()=>{if(sequence===voiceSequence)voiceStatus(false,'语音播放失败，请检查系统中文声音')};window.speechSynthesis.speak(speech);return true;
 }
 voiceStatus(false,'此环境没有可用的系统语音，请在桌面版试听');return false;
}
