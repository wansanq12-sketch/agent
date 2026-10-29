let voiceSpeaking=false,voiceStatusText='推荐温柔自然女声 · 晓晓',voiceSequence=0,voiceAudio=null;
function voiceStatus(available,message){voiceStatusText=message||(available?'声音已就绪':'系统语音不可用');const label=document.querySelector('#voice-status');if(label)label.textContent=voiceStatusText;if(!available)voiceFinished()}
function voiceFinished(){voiceSpeaking=false;if(typeof finishSpeechMotion==='function')finishSpeechMotion(typeof replyEmotion==='undefined'?'idle':replyEmotion)}
function stopVoice(finish=true){voiceSequence++;if(voiceAudio){voiceAudio.pause();voiceAudio.removeAttribute('src');voiceAudio.load();voiceAudio=null}voiceSpeaking=false;if(window.webkit?.messageHandlers?.desktop)native('stopSpeech');else window.speechSynthesis?.cancel();if(finish)voiceFinished()}
function playVoice(text,force=false,previewSettings=null){
 if(!text)return false;
 stopVoice(false);const sequence=++voiceSequence,settings=previewSettings||(typeof state==='undefined'?{}:state?.settings||{});voiceSpeaking=true;
 const rate=settings.voice_rate??100,volume=settings.voice_volume??80;
 if(settings.voice_neural!==false){
  if(!settings.voice_online_consent){voiceStatus(false,'请在声音设置中勾选微软在线语音授权，保存后试听');return false}
  voiceStatus(true,'正在生成所选声音…');
  api('speech',settings.preview?{preview:true,consent:settings.voice_online_consent,voice:settings.voice_choice,rate,}:{text:String(text)}).then(result=>{
   if(sequence!==voiceSequence)return;
   const audio=new Audio('data:'+result.mime+';base64,'+result.audio);voiceAudio=audio;audio.volume=volume/100;
   audio.onended=()=>{if(sequence===voiceSequence){voiceAudio=null;voiceStatus(true,'播放完成，可试听其他声音');voiceFinished()}};
   audio.onerror=()=>{if(sequence===voiceSequence)voiceStatus(false,'音频播放失败，请检查声音输出设备')};
   return audio.play();
  }).catch(error=>{if(sequence===voiceSequence)voiceStatus(false,error.message||'自然语音播放失败，请重试')});return true;
 }

 if(window.webkit?.messageHandlers?.desktop){native('speak',{text:String(text),rate,volume});return true}
 if(window.speechSynthesis&&typeof SpeechSynthesisUtterance!=='undefined'){
  window.speechSynthesis.cancel();const speech=new SpeechSynthesisUtterance(String(text));speech.lang='zh-CN';speech.rate=rate/100;speech.volume=volume/100;
  const chinese=window.speechSynthesis.getVoices().find(v=>v.lang?.toLowerCase().startsWith('zh'));if(chinese)speech.voice=chinese;
  speech.onend=()=>{if(sequence===voiceSequence)voiceFinished()};speech.onerror=()=>{if(sequence===voiceSequence)voiceStatus(false,'语音播放失败，请检查系统中文声音')};window.speechSynthesis.speak(speech);return true;
 }
 voiceStatus(false,'此环境没有可用的系统语音，请在桌面版试听');return false;
}
