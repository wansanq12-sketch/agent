(function(root){
'use strict';
function correctedChannel(value,color){return Math.min(255,Math.max(0,color.brightness*(color.contrast*(value-127.5)+127.5)))}
function frameAt(action,elapsed,durationOverride){
 const duration=Math.max(1,durationOverride||action.durationMs);
 const phase=action.loop?Math.max(0,elapsed)%duration:Math.min(Math.max(0,elapsed),duration-0.001);
 if(action.frameDurationsMs&&action.frameDurationsMs.length===action.frames.length){
  const sourceDuration=action.frameDurationsMs.reduce((sum,value)=>sum+value,0);
  const time=phase/duration*sourceDuration;let end=0;
  for(let i=0;i<action.frames.length;i++){end+=action.frameDurationsMs[i];if(time<end)return i}
  return action.frames.length-1;
 }
 return Math.min(action.frames.length-1,Math.floor(phase/duration*action.frames.length));
}
function isolate(image,frame){
 const out=document.createElement('canvas');out.width=frame.w;out.height=frame.h;
 const context=out.getContext('2d');
 const nativeFilter='filter' in context;
 if(frame.color&&nativeFilter)context.filter='contrast('+frame.color.contrast+') brightness('+frame.color.brightness+')';
 context.drawImage(image,frame.x,frame.y,frame.w,frame.h,0,0,frame.w,frame.h);
 if(frame.color&&!nativeFilter){
  const pixels=context.getImageData(0,0,out.width,out.height);
  for(let i=0;i<pixels.data.length;i+=4){if(!pixels.data[i+3])continue;for(let channel=0;channel<3;channel++)pixels.data[i+channel]=correctedChannel(pixels.data[i+channel],frame.color)}
  context.putImageData(pixels,0,0);
 }
 context.filter='none';
 const mask=document.createElement('canvas');mask.width=frame.w;mask.height=frame.h;
 const m=mask.getContext('2d');m.fillStyle='#fff';
 for(const [y,x,length] of frame.runs)m.fillRect(x,y,length,1);
 context.globalCompositeOperation='destination-in';context.drawImage(mask,0,0);context.globalCompositeOperation='source-over';
 return out;
}
function nextFrameDelay(action,elapsed,durationOverride){
 const duration=Math.max(1,durationOverride||action.durationMs);
 if(!action.loop&&elapsed>=duration)return Infinity;
 const phase=action.loop?Math.max(0,elapsed)%duration:Math.max(0,elapsed);
 const weights=action.frameDurationsMs||action.frames.map(()=>1),total=weights.reduce((a,b)=>a+b,0);
 let end=0;for(const weight of weights){end+=weight/total*duration;if(end>phase+.001)return Math.max(4,end-phase)}
 return action.loop?4:Infinity;
}
// A compact footprint in canvas coordinates, shared with native mouse hit testing.
function footprint(meta,scale,width,height){
 const cols=100,rows=140,bits=new Uint8Array(Math.ceil(cols*rows/8));
 const left=width/2-(meta.anchorX||meta.w/2)*scale,top=height-5-meta.h*scale;
 for(const [y,x,length] of meta.runs){
  const x0=Math.max(0,Math.floor((left+x*scale)/width*cols)),x1=Math.min(cols,Math.ceil((left+(x+length)*scale)/width*cols));
  const y0=Math.max(0,Math.floor((top+y*scale)/height*rows)),y1=Math.min(rows,Math.ceil((top+(y+1)*scale)/height*rows));
  for(let yy=y0;yy<y1;yy++)for(let xx=x0;xx<x1;xx++){const index=yy*cols+xx;bits[index>>3]|=1<<(index&7)}
 }
 return {cols,rows,bits};
}
class SpritePlayer{
 constructor(canvas,manifest,base){this.canvas=canvas;this.manifest=manifest;this.base=base;this.cache={};this.loading={};this.lastDraw=null;this.clock=0;this.changed=false}
 load(name){
  if(this.loading[name])return this.loading[name];
  const action=this.manifest.actions[name];
  this.loading[name]=new Promise((resolve,reject)=>{const im=new Image();im.onload=()=>{try{
   const unique=new Map();const frames=action.frames.map(f=>{const key=JSON.stringify([f.x,f.y,f.w,f.h,f.color]);if(!unique.has(key))unique.set(key,isolate(im,f));return unique.get(key)});
   const left=Math.max(...action.frames.map(f=>f.anchorX||f.w/2)),right=Math.max(...action.frames.map(f=>f.w-(f.anchorX||f.w/2)));
   this.cache[name]={frames,masks:{},used:++this.clock,scale:Math.min(390/(left+right),540/Math.max(...action.frames.map(f=>f.h)))};
   // Keep at most four decoded actions; always retain the one currently displayed.
   const candidates=Object.keys(this.cache).filter(key=>key!==name&&key!==this.lastDraw?.name).sort((a,b)=>this.cache[a].used-this.cache[b].used);
   while(Object.keys(this.cache).length>4&&candidates.length){const key=candidates.shift();delete this.cache[key];delete this.loading[key]}
   resolve(this.cache[name]);
  }catch(e){reject(e)}};im.onerror=()=>reject(Error('Cannot load '+name));im.src=this.base+action.file});
  this.loading[name]=this.loading[name].catch(error=>{delete this.loading[name];throw error});
  return this.loading[name];
 }
 draw(name,elapsed,durationOverride,forcedFrame){
  this.changed=false;
  const action=this.manifest.actions[name],entry=this.cache[name];if(!action||!entry)return false;
  const index=Number.isInteger(forcedFrame)?Math.max(0,Math.min(action.frames.length-1,forcedFrame)):frameAt(action,elapsed,durationOverride),meta=action.frames[index],frame=entry.frames[index],s=entry.scale,ctx=this.canvas.getContext('2d');
  entry.used=++this.clock;
  if(this.lastDraw?.name===name&&this.lastDraw.index===index&&this.lastDraw.width===this.canvas.width&&this.lastDraw.height===this.canvas.height)return true;
  ctx.clearRect(0,0,this.canvas.width,this.canvas.height);
  // Anchor the face horizontally and the character baseline vertically. No sway or rotation.
  ctx.drawImage(frame,this.canvas.width/2-(meta.anchorX||meta.w/2)*s,this.canvas.height-5-meta.h*s,meta.w*s,meta.h*s);
  this.lastDraw={name,index,width:this.canvas.width,height:this.canvas.height};this.changed=true;
  return true;
 }
 hitMask(){
  if(!this.lastDraw)return null;
  const {name,index}=this.lastDraw,entry=this.cache[name];if(!entry)return null;
  if(!entry.masks[index]){
   const mask=footprint(this.manifest.actions[name].frames[index],entry.scale,this.canvas.width,this.canvas.height);
   entry.masks[index]={cols:mask.cols,rows:mask.rows,bits:btoa(String.fromCharCode(...mask.bits))};
  }
  return entry.masks[index];
 }
}
const api={frameAt,nextFrameDelay,footprint,isolate,SpritePlayer,correctedChannel};if(typeof module!=='undefined'&&module.exports)module.exports=api;else root.YeliFramePlayer=api;
})(typeof window!=='undefined'?window:globalThis);
