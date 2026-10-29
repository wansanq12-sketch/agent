(function(root){
'use strict';
function composing(event,active,endedAt=0,now=Date.now()){
 // Safari may report compositionend immediately before the keydown that confirmed a word.
 return !!(active||event?.isComposing||event?.keyCode===229||now-endedAt<80);
}
class DraftQueue{
 constructor(save){this.save=save;this.tail=Promise.resolve()}
 write(text){const task=this.tail.catch(()=>{}).then(()=>this.save(text));this.tail=task;return task}
}
const api={composing,DraftQueue};if(typeof module!=='undefined'&&module.exports)module.exports=api;else root.YeliInput=api;
})(typeof window!=='undefined'?window:globalThis);
