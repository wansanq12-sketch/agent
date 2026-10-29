async function renderSkills(panel,error){
 panel.append(el('small','导入技能文件夹、SKILL.md 或单个技能 ZIP 包（最多 2 MB）。新增技能默认停用，检查后再启用。启用的说明与文本附件会随聊天发送给你配置的 AI。脚本和图片可随包保存，当前不会执行脚本或接入外部工具。'));
 const picker=el('input');picker.type='file';picker.accept='.md,.zip';picker.setAttribute('aria-label','选择技能文件');
 const importButton=el('button','导入技能');
 importButton.onclick=async()=>{const file=picker.files?.[0];if(!file){error.textContent='请先选择 SKILL.md 或 ZIP 技能包';return}if(file.size>2*1024*1024){error.textContent='技能文件最多 2 MB';return}importButton.disabled=true;try{const bytes=new Uint8Array(await file.arrayBuffer());let binary='';for(let i=0;i<bytes.length;i+=8192)binary+=String.fromCharCode(...bytes.subarray(i,i+8192));await api('skills',{action:'import',filename:file.name,content:btoa(binary)});await openPanel('skills')}catch(e){error.textContent=e.message}finally{importButton.disabled=false}};
 panel.append(picker,importButton);
 const folder=el('input');folder.type='file';folder.multiple=true;folder.setAttribute('webkitdirectory','');folder.setAttribute('directory','');folder.setAttribute('aria-label','选择技能文件夹');
 const folderButton=el('button','导入技能文件夹');
 folderButton.onclick=async()=>{
  const files=Array.from(folder.files||[]).filter(f=>!f.webkitRelativePath.split('/').some(p=>p.startsWith('.')||p==='__MACOSX'));
  if(!files.length){error.textContent='请先选择包含 SKILL.md 的文件夹';return}
  if(files.length>64||files.reduce((n,f)=>n+f.size,0)>2*1024*1024){error.textContent='技能文件夹最多 64 个文件，合计最多 2 MB';return}
  folderButton.disabled=true;
  try{const entries=[];for(const file of files){const bytes=new Uint8Array(await file.arrayBuffer());let binary='';for(let i=0;i<bytes.length;i+=8192)binary+=String.fromCharCode(...bytes.subarray(i,i+8192));entries.push({path:file.webkitRelativePath||file.name,content:btoa(binary)})}await api('skills',{action:'import-folder',files:entries});await openPanel('skills')}catch(e){error.textContent=e.message}finally{folderButton.disabled=false}
 };
 panel.append(el('label','或选择整个技能文件夹'),folder,folderButton,el('small','选择单个技能目录，里面应有一个 SKILL.md；子目录和附件一起保存。隐藏文件自动忽略。导入为本地副本，原文件夹后续修改需重新导入。'));
 const list=el('div');panel.append(list);
 const response=await api('skills');
 if(!response.skills.length)list.append(el('small','还没有技能。直接导入已经写好的技能即可，无需在这里搭建流程。'));
 for(const skill of response.skills){
  const card=el('section');card.style.cssText='margin-top:16px;padding:12px;border:1px solid #55617a;border-radius:12px';
  card.append(el('h3',skill.name),el('small',skill.enabled?'已启用 · 对相关对话生效':'已停用'),el('small',skill.description||'未填写简介'));
  const toggle=el('button',skill.enabled?'停用':'启用'),edit=el('button','查看 / 编辑'),remove=el('button','删除');
  toggle.onclick=async()=>{toggle.disabled=true;try{await api('skills',{action:'update',id:skill.id,enabled:!skill.enabled});await openPanel('skills')}catch(e){error.textContent=e.message;toggle.disabled=false}};
  const editor=el('div');editor.hidden=true;
  const text=el('textarea');text.value=skill.content;text.rows=12;text.setAttribute('aria-label',skill.name+' 的 SKILL.md');
  const save=el('button','保存修改');save.onclick=async()=>{save.disabled=true;try{await api('skills',{action:'update',id:skill.id,content:text.value});await openPanel('skills')}catch(e){error.textContent=e.message;save.disabled=false}};
  editor.append(el('small','直接编辑 SKILL.md 原文。名称和简介取自开头的 name / description，或一级标题。'),text,save);
  const paths=Object.keys(skill.files);editor.append(el('small',paths.length?'随包附件：'+paths.join('、'):'无随包附件'));
  for(const path of paths){if(!/\.(md|txt|json|ya?ml)$/i.test(path))continue;const details=el('details'),summary=el('summary',path),pre=el('pre');pre.style.cssText='white-space:pre-wrap;overflow-wrap:anywhere';try{pre.textContent=new TextDecoder().decode(Uint8Array.from(atob(skill.files[path]),c=>c.charCodeAt(0)))}catch{pre.textContent='无法显示附件'}details.append(summary,pre);editor.append(details)}
  edit.onclick=()=>{editor.hidden=!editor.hidden;regions()};
  const confirm=el('div');confirm.hidden=true;confirm.append(el('small','删除“'+skill.name+'”及随包附件？'));
  const yes=el('button','确认删除'),no=el('button','取消');yes.onclick=async()=>{yes.disabled=true;try{await api('skills',{action:'delete',id:skill.id});await openPanel('skills')}catch(e){error.textContent=e.message;yes.disabled=false}};no.onclick=()=>{confirm.hidden=true;regions()};confirm.append(yes,no);remove.onclick=()=>{confirm.hidden=false;regions()};
  card.append(toggle,edit,remove,confirm,editor);list.append(card);
 }
 regions();
}
