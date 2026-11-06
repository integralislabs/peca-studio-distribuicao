import {initIntegralisUI,ensureIntegralisAccess} from './integralis-ui.js';
import {initHTMLDocumentUI,prepareHTMLPiece,htmlExport,htmlRequest} from './html-document-ui.js';
import {saveYouTubeSource} from './youtube-source.js';
import {containsLayer} from './geometry.js';
import {initArtUI} from './art-ui.js';
import {initMediaUI} from './media-ui.js';
import {initPublishingUI} from './publishing-ui.js';
import {initDesktopUI} from './desktop-ui.js';
import {moveToTrash} from './trash.js';
import {initTrashUI} from './trash-ui.js';
import {uid,clone,FONTS,FORMATS,STATUSES,newPiece,newSlide,textLayer,imageLayer,assertHTMLSize,assertBackupSize,duplicatePiece,duplicateSlide,filterPieces,validateState,makeZip} from './model.js';
import {drawSlide,layerHeight,pngBlob,readImage,loadImage} from './render.js';
import {demoState} from './seed.js';
import {openStore,writeStore} from './storage.js';
import {loadFonts,fontNames,fontKey} from './fonts.js';
import {initFontsUI} from './font-ui.js';
import {initPrintUI} from './print-export.js';
import {initImageConversion,verifyImageQA} from './image-conversion-ui.js';
import {initWorkspaceUI} from './workspace-ui.js';
import {initImageReview} from './image-review.js';
import {importPackage} from './packages.js';
import {initAI} from './ai-ui.js';
import {saveTemplate,useTemplate,validateTemplate} from './templates.js';
import {initTemplatesUI} from './templates-ui.js';
import {initSourcesUI} from './sources-ui.js';
import {formatTime,sourceLink} from './sources.js';
import {initBrandUI} from './brand-ui.js';
import {createVariation} from './library.js';
import {initLibraryUI,copyID} from './library-ui.js';
import {initPackageUI} from './package-ui.js';
import {initStyleUI} from './style-ui.js';

const $=s=>document.querySelector(s),$$=s=>[...document.querySelectorAll(s)];
const esc=s=>String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
let htmlUI,libraryUI,styleUI,filesUI,workspaceUI,imageReviewUI,artUI;
function collectionFonts(library=state){const entries=[...(library?.fonts||[]),...(library?.pieces||[]).flatMap(p=>p.fonts||[]),...(library?.templates||[]).flatMap(t=>t.snapshot?.fonts||[])],map=new Map();for(const f of entries){const key=fontKey(f.name);if(map.has(key)&&map.get(key).data!==f.data)throw Error('Há duas fontes diferentes com o mesmo nome. Renomeie uma antes de importar.');map.set(key,f);}return [...map.values()];}
function portablePiece(p){if(!p)return p;const used=new Set(p.slides.flatMap(s=>s.layers.filter(l=>l.type==='text').map(l=>fontKey(l.font)))),fonts=collectionFonts().filter(f=>used.has(fontKey(f.name)));return fonts.length?{...p,fonts}:p;}
async function refreshFonts(library=state){const names=await loadFonts(collectionFonts(library));FONTS.splice(0,FONTS.length,...names);}
async function replaceLibrary(incoming){const next=validateState(incoming);for(const p of next.pieces)if(p.htmlDocument)p.htmlDocument=await htmlRequest('validate',{document:p.htmlDocument});await refreshFonts(next);state=next;clearTimeout(saveTimer);dirty=saved=0;saveFailed=false;undo=[];redo=[];filters={};page=0;if(activeId&&!state.pieces.some(p=>p.id===activeId)){activeId=null;$('#editor').hidden=true;$('#library').hidden=false;}renderProjects();renderLibrary();if(piece()){slideIndex=Math.min(slideIndex,piece().slides.length-1);selected=null;renderEditor();}saveStatus('Tudo salvo');}
async function importNewPiece(p){if(p.htmlDocument)p.htmlDocument=await htmlRequest('validate',{document:p.htmlDocument});const incomingFonts=p.fonts||[],known=collectionFonts();for(const f of incomingFonts){const old=known.find(x=>fontKey(x.name)===fontKey(f.name));if(old&&old.data!==f.data)throw Error('Já existe outra fonte com este nome: '+f.name);}validateState({...state,pieces:[p,...state.pieces]});await loadFonts([...known,...incomingFonts.filter(f=>!known.some(x=>fontKey(x.name)===fontKey(f.name)))]);state.pieces.unshift(p);await refreshFonts();changed();renderProjects();openEditor(p.id);toast('Criação adicionada com camadas editáveis.');}
let state,view='grid',filters={},page=0,activeId=null,slideIndex=0,selected=null,tab='text',zoom=35;
let undo=[],redo=[],saveTimer,toastTimer,dirty=0,saved=0,saving=false,saveFailed=false,observer,imageAction,confirmAction,projectEditing=null;
const piece=()=>state?.pieces.find(p=>p.id===activeId),slide=()=>piece()?.slides[slideIndex],layer=()=>slide()?.layers.find(l=>l.id===selected);
const projectById=id=>state.projects.find(p=>p.id===id);
const displayLayer=l=>l.type==='text'&&l.name==='Texto'?(l.text.split('\n')[0].slice(0,34)||'Texto vazio'):l.name;
function toast(message,error=false){$('#toast').textContent=message;$('#toast').classList.toggle('error',error);$('#toast').hidden=false;clearTimeout(toastTimer);toastTimer=setTimeout(()=>$('#toast').hidden=true,error?8500:3600);}
function error(err){console.error(err);toast(err.message||'Não foi possível concluir esta ação.',true);}
function on(target,event,fn){(typeof target==='string'?$(target):target).addEventListener(event,e=>{try{const r=fn(e);if(r?.catch)r.catch(error);}catch(err){error(err);}});}
function saveStatus(text,failed=false){$('#save-status').classList.toggle('error',failed);$('.topbar').classList.toggle('has-save-error',failed);$('#retry-save').hidden=!failed||dirty===saved||!state;$('#save-status').innerHTML=`<span class="local-dot"${failed?' style="background:#ff9f9f"':''}></span>${esc(text)}`;}
function changed(){dirty++;clearTimeout(saveTimer);if(saveFailed){saveStatus('Não salvo · faça backup',true);return;}saveStatus('Salvando…');saveTimer=setTimeout(flushSave,350);}
function retrySave(){saveFailed=false;saveStatus('Salvando…');return flushSave();}
on('#retry-save','click',retrySave);
async function flushSave(){
  if(saving||saved===dirty||saveFailed)return;
  saving=true;const version=dirty,snapshot=clone(state);
  try{await writeStore(snapshot);saved=version;if(saved===dirty)saveStatus('Tudo salvo');}
  catch(err){saveFailed=true;saveStatus('Não salvo · faça backup',true);error(err);}
  finally{saving=false;if(!saveFailed&&saved!==dirty)flushSave();}
}
function record(){if(!piece())return;undo.push(clone(piece()));if(undo.length>30)undo.shift();redo=[];updateUndo();}
function updateUndo(){$('#undo').disabled=!undo.length;$('#redo').disabled=!redo.length;}
function edited(){imageReviewUI?.refresh();piece().updatedAt=new Date().toISOString();piece().demo=false;changed();refreshCanvas();refreshSlideThumb();}
function mutate(fn,{rebuild=false}={}){if(piece()?.htmlDocument){const before=JSON.stringify(piece().slides);const snapshot=clone(piece());fn();if(JSON.stringify(piece().slides)!==before){state.pieces[state.pieces.findIndex(p=>p.id===activeId)]=snapshot;throw Error('Use Editar HTML preservado para manter documento e prévia sincronizados.');}undo.push(snapshot);redo=[];updateUndo();edited();if(rebuild){renderProperties();renderSlides();}return;}record();fn();edited();if(rebuild){renderProperties();renderSlides();}}
function history(direction){const from=direction==='undo'?undo:redo,to=direction==='undo'?redo:undo;if(!from.length)return;to.push(clone(piece()));state.pieces[state.pieces.findIndex(p=>p.id===activeId)]=from.pop();slideIndex=Math.min(slideIndex,piece().slides.length-1);selected=null;changed();renderEditor();}
function download(blob,name){if(!/biblioteca|backup/i.test(name)){ensureIntegralisAccess().then(()=>deliver(blob,name)).catch(error);return;}deliver(blob,name);}
function deliver(blob,name){const url=URL.createObjectURL(blob),a=document.createElement('a');a.href=url;a.download=name;a.click();setTimeout(()=>URL.revokeObjectURL(url),60000);}
const slug=t=>(t.normalize('NFD').replace(/[\u0300-\u036f]/g,'').replace(/[^a-z0-9_-]+/ig,'-').replace(/^-|-$/g,'').slice(0,75)||'peca');
function options(items,value){return items.map(([id,name])=>`<option value="${esc(id)}" ${id===value?'selected':''}>${esc(name)}</option>`).join('');}
function openDialog(id){$(id).showModal();setTimeout(()=>$(id).querySelector('input:not([type=file]),textarea,button')?.focus(),30);}
function confirm(title,message,action,{input=null,button='Confirmar'}={}){
  $('#confirm-title').textContent=title;$('#confirm-message').textContent=message;$('#confirm-submit').textContent=button;$('#confirm-input-label').hidden=input===null;$('#confirm-input').required=input!==null;$('#confirm-input').value=input||'';confirmAction=action;openDialog('#confirm-dialog');if(input!==null)$('#confirm-input').focus();
}
on('#confirm-form','submit',e=>{e.preventDefault();const value=$('#confirm-input').value.trim();if(!$('#confirm-input-label').hidden&&!value)return;$('#confirm-dialog').close();const action=confirmAction;confirmAction=null;return action?.(value);});
$$('[data-close]').forEach(b=>on(b,'click',()=>b.closest('dialog').close()));
$$('dialog').forEach(d=>on(d,'click',e=>{if(e.target===d){const r=d.getBoundingClientRect();if(e.clientX<r.left||e.clientX>r.right||e.clientY<r.top||e.clientY>r.bottom)d.close();}}));

function renderProjects(){
  $('#total-count').textContent=state.pieces.length;
  $('#all-content').classList.toggle('active',!filters.project);
  $('#projects').innerHTML=state.projects.map(p=>`<div class="project-row ${filters.project===p.id&&!filters.folder?'active':''}"><button class="project-select" data-project="${p.id}"><span class="project-dot" style="background:${p.color}"></span><span class="project-name">${esc(p.name)}</span><span class="project-count">${state.pieces.filter(x=>x.projectId===p.id).length}</span></button><button class="icon-btn project-more" data-project-menu="${p.id}" aria-label="Opções de ${esc(p.name)}">⋯</button></div>${filters.project===p.id?p.folders.map(f=>`<div class="project-row"><button class="nav-item folder-row ${filters.folder===f.id?'active':''}" data-folder="${f.id}" data-owner="${p.id}">▱ ${esc(f.name)}<span class="project-count">${state.pieces.filter(x=>x.folderId===f.id).length}</span></button><button class="icon-btn project-more" data-folder-menu="${f.id}" data-owner="${p.id}" aria-label="Opções da pasta ${esc(f.name)}">⋯</button></div>`).join(''):''}`).join('');
  $('#filter-project').innerHTML='<option value="">Todos os projetos</option>'+options(state.projects.map(p=>[p.id,p.name]),filters.project);
}
function setProject(id,folder=null){filters.project=id||'';filters.folder=folder||'';page=0;if(activeId)closeEditor();renderLibrary();}
on('#all-content','click',()=>setProject(''));
on('.brand','click',e=>{e.preventDefault();setProject('');});
on('#projects','click',e=>{
  const p=e.target.closest('[data-project]'),f=e.target.closest('[data-folder]'),menu=e.target.closest('[data-project-menu]'),fm=e.target.closest('[data-folder-menu]');
  if(p)setProject(p.dataset.project);if(f)setProject(f.dataset.owner,f.dataset.folder);
  if(menu)projectMenu(menu.dataset.projectMenu);if(fm)folderMenu(fm.dataset.owner,fm.dataset.folderMenu);
});
function menuDialog(title,items){
  let dialog=$('#menu-dialog');if(!dialog){dialog=document.createElement('dialog');dialog.id='menu-dialog';document.body.append(dialog);}
  dialog.innerHTML=`<div class="dialog-heading"><h2>${esc(title)}</h2><button class="icon-btn" aria-label="Fechar">×</button></div>`;
  dialog.querySelector('button').onclick=()=>dialog.close();
  for(const [label,fn]of items){const button=document.createElement('button');button.className='export-option';button.textContent=label;button.onclick=()=>{dialog.close();try{const r=fn();if(r?.catch)r.catch(error);}catch(e){error(e);}};dialog.append(button);}dialog.showModal();
}
function projectMenu(id){const p=projectById(id);menuDialog(p.name,[['+ Nova pasta',()=>confirm('Nova pasta',`Organize as peças de ${p.name}.`,name=>{p.folders.push({id:uid(),name});changed();setProject(p.id);},{input:'',button:'Criar pasta'})],['Renomear projeto / alterar cor',()=>showProject(p)],['Excluir projeto',()=>confirm('Excluir projeto?',`O projeto “${p.name}” e suas ${state.pieces.filter(x=>x.projectId===id).length} peças serão removidos. Você pode restaurá-los pela lixeira.`,()=>{state=moveToTrash(state,'project',id);changed();setProject('');},{button:'Excluir projeto'})]]);}
function folderMenu(pid,fid){const p=projectById(pid),f=p.folders.find(x=>x.id===fid);menuDialog(f.name,[['Renomear pasta',()=>confirm('Renomear pasta','Escolha um novo nome.',name=>{f.name=name;changed();renderLibrary();},{input:f.name,button:'Salvar'})],['Remover pasta (manter peças)',()=>confirm('Remover pasta?', 'As peças continuarão no projeto, sem pasta.',()=>{p.folders=p.folders.filter(x=>x.id!==fid);state.pieces.filter(x=>x.folderId===fid).forEach(x=>x.folderId=null);filters.folder='';changed();renderLibrary();},{button:'Remover pasta'})]]);}
function showProject(p=null){projectEditing=p?.id||null;$('#project-dialog-title').textContent=p?'Editar projeto':'Novo projeto';$('#project-form').elements.name.value=p?.name||'';$('#project-form').elements.color.value=p?.color||'#9b75ff';openDialog('#project-dialog');}
on('#new-project','click',()=>showProject());on('#sidebar-add-project','click',()=>showProject());
on('#project-form','submit',e=>{e.preventDefault();const f=e.target.elements,name=f.name.value.trim();if(!name)return;let p=projectById(projectEditing);if(p){p.name=name;p.color=f.color.value;}else{p={id:uid(),name,color:f.color.value,folders:[]};state.projects.push(p);}changed();$('#project-dialog').close();setProject(p.id);toast('Projeto salvo.');});
function showNewPiece(){if(!state.projects.length){toast('Crie um projeto para organizar sua primeira peça.');showProject();return;}const form=$('#piece-form');form.reset();form.elements.project.innerHTML=options(state.projects.map(p=>[p.id,p.name]),filters.project||state.projects[0].id);openDialog('#piece-dialog');}
on('#new-piece','click',showNewPiece);on('#empty-create','click',showNewPiece);
on('#piece-form','submit',e=>{e.preventDefault();const f=e.target.elements,title=f.title.value.trim();if(!title)return;const p=newPiece(f.project.value,title,f.format.value,Number(f.count.value));p.channel=f.channel.value;if(filters.project===p.projectId)p.folderId=filters.folder||null;state.pieces.unshift(p);changed();$('#piece-dialog').close();renderProjects();openEditor(p.id);toast('Peça criada. Vamos dar forma à sua ideia.');});

function cardHTML(p){const project=projectById(p.projectId);return `<article class="piece-card" data-id="${p.id}" ${view==='kanban'?'draggable="true"':''}><div class="card-controls"><button data-duplicate="${p.id}" aria-label="Duplicar ${esc(p.title)}" title="Duplicar peça">⧉</button><button data-delete="${p.id}" aria-label="Excluir ${esc(p.title)}" title="Excluir peça">×</button></div>${p.slides.length>1?`<span class="slide-count">▱ ${p.slides.length} slides</span>`:''}<button class="piece-art-button" data-select-piece="${p.id}" aria-pressed="false" aria-label="Selecionar ${esc(p.title)}"><canvas data-preview="${p.id}" width="300" height="375"></canvas></button><div class="card-info"><button class="card-title" data-open="${p.id}">${esc(p.title)}</button><div class="card-project"><span class="project-dot" style="background:${project.color}"></span>${esc(project.name)}</div><div class="card-meta">${view==='kanban'?`<select class="card-status-select" data-card-status="${p.id}" aria-label="Estado de ${esc(p.title)}">${options(STATUSES.map(x=>[x,x]),p.status)}</select>`:`<span class="status ${p.status==='Pronto'?'ready':''}">${esc(p.status)}</span>`}<span>${p.format==='feed'?'Feed':p.format==='story'?'Story':'1:1'}</span><time>${new Date(p.updatedAt).toLocaleDateString('pt-BR',{day:'2-digit',month:'short'})}</time></div></div></article>`;}
function renderLibrary(){
  renderProjects();const project=projectById(filters.project),folder=project?.folders.find(f=>f.id===filters.folder);
  $('#library-title').textContent=folder?.name||project?.name||'Peças';if(!project)$('#library-title').insertAdjacentHTML('beforeend','<span class="title-dot">.</span>');
  $('#library-description').textContent=folder?`Pasta de ${project.name}`:project?'Todas as ideias deste projeto, em um só lugar.':'Ideias organizadas. Designs prontos para ganhar o mundo.';
  $('#breadcrumb').textContent=project?.name||'Biblioteca';$('#demo-note').hidden=state.demoNotice===false||!state.pieces.some(p=>p.demo);
  const list=filterPieces(state.pieces,filters).sort((a,b)=>new Date(b.updatedAt)-new Date(a.updatedAt));
  const totalPages=Math.max(1,Math.ceil(list.length/24));page=Math.max(0,Math.min(page,totalPages-1));const visible=list.slice(page*24,page*24+24);
  $('#results-count').textContent=`${list.length} de ${state.pieces.length} peças`;
  $('#clear-filters').hidden=!Object.values(filters).some(Boolean);$('#empty-state').hidden=list.length>0;
  const hasFilters=Object.values(filters).some(Boolean);$('#empty-title').textContent=hasFilters?'Nenhuma peça por aqui.':'Um espaço para a próxima ideia.';$('#empty-description').textContent=hasFilters?'Experimente mudar os filtros ou crie uma peça neste projeto.':'Crie uma peça ou importe um design para começar.';
  const root=$('#pieces');root.className=view==='grid'?'pieces-grid':view==='list'?'pieces-list':'kanban-board';
  if(view==='kanban'&&visible.length){root.innerHTML=STATUSES.map(status=>`<section class="kanban-column" data-status="${status}"><div class="kanban-heading"><span class="local-dot" style="background:${status==='Pronto'?'#7cd5ad':'#a780ff'}"></span>${status}<b>${visible.filter(p=>p.status===status).length}</b></div>${visible.filter(p=>p.status===status).map(cardHTML).join('')}<small>Arraste uma peça para esta coluna</small></section>`).join('');}
  else root.innerHTML=visible.map(cardHTML).join('');
  $('#library-summary').textContent=list.length?`Mostrando ${page*24+1}–${page*24+visible.length} de ${list.length} peças`:'Sua biblioteca está pronta para criar.';
  $('#pagination').innerHTML=totalPages>1?`<button class="button" data-page="-1" ${page===0?'disabled':''}>←</button><span>${page+1} / ${totalPages}</span><button class="button" data-page="1" ${page===totalPages-1?'disabled':''}>→</button>`:'';
  observer?.disconnect();observer=new IntersectionObserver(entries=>{for(const e of entries)if(e.isIntersecting){observer.unobserve(e.target);const p=state.pieces.find(p=>p.id===e.target.dataset.preview);if(p)drawSlide(e.target,p.slides[0],{width:300}).catch(error);}},{rootMargin:'200px'});
  $$('[data-preview]').forEach(c=>observer.observe(c));libraryUI?.render();
}
on('#pieces','click',e=>{const open=e.target.closest('[data-open]'),dup=e.target.closest('[data-duplicate]'),del=e.target.closest('[data-delete]');const detail=e.target.closest('[data-select-piece]');if(detail)libraryUI.select(detail.dataset.selectPiece);if(open)openEditor(open.dataset.open);if(dup){const copy=duplicatePiece(state.pieces.find(p=>p.id===dup.dataset.duplicate));state.pieces.unshift(copy);changed();renderLibrary();toast('Cópia independente criada.');}if(del){const p=state.pieces.find(x=>x.id===del.dataset.delete);confirm('Excluir peça?',`“${p.title}” e todos os seus slides serão removidos.`,()=>{state=moveToTrash(state,'piece',p.id);changed();renderLibrary();toast('Peça removida.');},{button:'Excluir peça'});}});
function movePiece(id,status){const p=state.pieces.find(x=>x.id===id);if(!p||!STATUSES.includes(status)||p.status===status)return;p.status=status;p.demo=false;p.updatedAt=new Date().toISOString();changed();renderLibrary();toast(`Peça movida para ${p.status.toLowerCase()}.`);}
on('#pieces','change',e=>{if(e.target.dataset.cardStatus)movePiece(e.target.dataset.cardStatus,e.target.value);});
on('#pieces','dragstart',e=>{if(e.target.closest('select')){e.preventDefault();return;}const card=e.target.closest('.piece-card');if(card&&view==='kanban'){e.dataTransfer.setData('text/plain',card.dataset.id);e.dataTransfer.effectAllowed='move';}});
on('#pieces','dragover',e=>{const c=e.target.closest('.kanban-column');if(c){e.preventDefault();c.classList.add('drag-over');}});
on('#pieces','dragleave',e=>e.target.closest('.kanban-column')?.classList.remove('drag-over'));
on('#pieces','drop',e=>{const c=e.target.closest('.kanban-column');if(!c)return;e.preventDefault();movePiece(e.dataTransfer.getData('text/plain'),c.dataset.status);});
on('#pagination','click',e=>{const b=e.target.closest('[data-page]');if(b){page+=Number(b.dataset.page);renderLibrary();window.scrollTo({top:0,behavior:'smooth'});}});
$$('[data-view]').forEach(b=>on(b,'click',()=>{view=b.dataset.view;$$('[data-view]').forEach(x=>{x.classList.toggle('selected',x===b);x.setAttribute('aria-selected',x===b);});renderLibrary();}));
on('#search','input',e=>{filters.query=e.target.value;page=0;renderLibrary();});
for(const key of ['project','channel','format'])on('#filter-'+key,'change',e=>{filters[key]=e.target.value;if(key==='project')filters.folder='';page=0;renderLibrary();});
on('#clear-filters','click',()=>{filters={};$('#search').value='';$('#filter-channel').value='';$('#filter-format').value='';page=0;renderLibrary();});
on('#card-size','input',e=>$('#pieces').style.setProperty('--card-size',e.target.value+'px'));
on('#dismiss-demo','click',()=>{state.demoNotice=false;changed();$('#demo-note').hidden=true;});

async function openEditor(id){try{await ensureIntegralisAccess();}catch(e){error(e);return;}activeId=id;slideIndex=0;selected=null;tab='text';undo=[];redo=[];$('#library').hidden=true;$('#editor').hidden=false;$('#breadcrumb').textContent='Editor de design';renderEditor();requestAnimationFrame(fitCanvas);}
function closeEditor(){activeId=null;selected=null;$('#editor').hidden=true;$('#library').hidden=false;renderLibrary();flushSave();}
on('#back-library','click',closeEditor);
on('#piece-source','click',()=>{const source=piece().source;if(!source)return;$('#piece-source-title').textContent=source.title;$('#piece-source-times').textContent=formatTime(source.start)+' a '+formatTime(source.end);$('#piece-source-text').textContent=source.text;const url=sourceLink(source);$('#piece-source-link').hidden=!url;if(url)$('#piece-source-link').href=url;openDialog('#piece-source-dialog');});
on('#piece-caption','click',()=>{$('#caption-dialog h2').textContent=piece().contentKind==='short'?'Roteiro do Short':'Legenda da publicação';$('#caption-text').value=piece().caption||'';openDialog('#caption-dialog');});
on('#caption-form','submit',e=>{e.preventDefault();mutate(()=>{piece().caption=$('#caption-text').value;});$('#caption-dialog').close();toast('Legenda salva na peça.');});
function renderEditor(){htmlUI?.refresh();imageReviewUI?.refresh();artUI?.render();const p=piece();$('#piece-source').hidden=!p.source;$('#piece-caption').textContent=p.contentKind==='short'?'Roteiro':'Legenda';$('#piece-title').value=p.title;$('#piece-status').value=p.status;$('#breadcrumb').textContent='Editor de design';$('#slide-counter').textContent=`${slideIndex+1} / ${p.slides.length}`;$('#dimensions').textContent=`${slide().width} × ${slide().height} px`;$('#previous-slide').disabled=slideIndex===0;$('#next-slide').disabled=slideIndex===p.slides.length-1;$('#add-slide').disabled=p.slides.length>=30;updateUndo();renderSlides();renderProperties();refreshCanvas();}
function refreshCanvas(){if(!slide())return;const c=$('#artboard');c.style.width=slide().width*zoom/100+'px';c.style.height=slide().height*zoom/100+'px';$('#canvas-holder').style.width=c.style.width;$('#canvas-holder').style.height=c.style.height;drawSlide(c,slide(),{selection:selected}).catch(error);$('#selection-info').textContent=layer()?`${layer().type==='text'?'Texto':'Imagem'} · ${layer().name}`:'Nenhum elemento selecionado';}
function setZoom(value){zoom=Math.max(10,Math.min(100,Math.round(value)));$('#zoom').value=zoom;$('#zoom-value').value=zoom+'%';refreshCanvas();}
function fitCanvas(){if(!slide())return;const box=$('#canvas-scroll');setZoom(Math.min((box.clientWidth-64)/slide().width,(box.clientHeight-56)/slide().height)*100);}
function renderSlides(){const p=piece();$('#slides').innerHTML=p.slides.map((s,i)=>`<button class="slide-thumbnail ${i===slideIndex?'active':''}" data-slide="${i}" aria-label="Editar slide ${i+1}" aria-pressed="${i===slideIndex}"><canvas data-slide-preview="${i}"></canvas><span>${String(i+1).padStart(2,'0')}</span></button>`).join('');p.slides.forEach((s,i)=>drawSlide($(`[data-slide-preview="${i}"]`),s,{width:80}).catch(error));}
function refreshSlideThumb(){const c=$(`[data-slide-preview="${slideIndex}"]`);if(c)drawSlide(c,slide(),{width:80}).catch(error);}
function goSlide(i){if(i<0||i>=piece().slides.length)return;slideIndex=i;selected=null;renderEditor();}
on('#slides','click',e=>{const b=e.target.closest('[data-slide]');if(b)goSlide(Number(b.dataset.slide));});
on('#previous-slide','click',()=>goSlide(slideIndex-1));on('#next-slide','click',()=>goSlide(slideIndex+1));
on('#add-slide','click',()=>{if(piece().slides.length>=30)return;mutate(()=>{const s=newSlide(piece().format);s.bg=slide().bg;piece().slides.push(s);slideIndex=piece().slides.length-1;selected=null;});renderEditor();});
on('#zoom','input',e=>setZoom(Number(e.target.value)));on('#fit-canvas','click',fitCanvas);
on('#undo','click',()=>history('undo'));on('#redo','click',()=>history('redo'));
on('#piece-title','focus',record);on('#piece-title','input',e=>{const title=e.target.value.trim();if(title){piece().title=title;edited();}});on('#piece-title','blur',()=>$('#piece-title').value=piece().title);
on('#piece-status','change',e=>mutate(()=>piece().status=e.target.value));
$('#piece-caption').insertAdjacentHTML('beforebegin','<button id="piece-identifiers" class="button">IDs</button>');
document.body.insertAdjacentHTML('beforeend','<dialog id="identifiers-dialog" class="studio-dialog"><div class="dialog-heading"><h2>IDs da criação</h2><button id="identifiers-close" class="icon-btn" aria-label="Fechar identificadores">×</button></div><div id="identifiers-fields"></div><p id="identifiers-status" role="status"></p></dialog>');
on('#piece-identifiers','click',()=>{const p=piece();$('#identifiers-fields').innerHTML=[['Projeto',p.projectId],['Coleção / pasta',p.folderId],['Peça',p.id],['Família / variação',p.variationGroupId||p.id]].map(([name,id])=>`<label>${name}<input readonly aria-label="ID ${name}" value="${esc(id||'Sem pasta')}"></label><button class="button" data-identifier="${esc(id||'')}" ${id?'':'disabled'}>Copiar ID ${name}</button>`).join('');$('#identifiers-status').textContent='';$('#identifiers-dialog').showModal();});
on('#identifiers-close','click',()=>$('#identifiers-dialog').close());
on('#identifiers-fields','click',async e=>{const b=e.target.closest('[data-identifier]');if(!b)return;try{await copyID(b.dataset.identifier);$('#identifiers-status').textContent='ID copiado.';}catch(error){$('#identifiers-status').textContent=error.message;}});
$$('[data-tab]').forEach(b=>on(b,'click',()=>{tab=b.dataset.tab;const first=slide().layers.find(l=>l.type===tab);selected=first?.id||null;renderProperties();refreshCanvas();}));
const field=(key,title,value,{min,max,step=1}={})=>`<label>${title}<input data-field="${key}" type="number" value="${value}" min="${min}" max="${max}" step="${step}" aria-label="${title}"></label>`;
const colorField=(key,value)=>`<input data-field="${key}" type="color" value="${esc(value)}" aria-label="Cor"><input data-color="${key}" value="${esc(value)}" maxlength="7" aria-label="Código da cor" style="width:90px;padding:8px;font-size:11px">`;
function fineFields(l){return `<details class="fine-adjust"><summary>Ajuste fino e controles rápidos</summary>${['x','y',...(l.type==='text'?['size']:[])].map(key=>`<label class="property-label">${{x:'Posição X',y:'Posição Y',size:'Tamanho'}[key]} · <output data-value="${key}">${Math.round(l[key])}</output><input type="range" data-field="${key}" aria-label="Ajuste rápido ${key}" min="${key==='size'?8:-Math.max(slide().width,slide().height,Math.abs(l[key]))}" max="${key==='size'?400:Math.max(slide().width,slide().height,Math.abs(l[key]))}" value="${l[key]}" step="1"></label>`).join('')}${l.type==='text'?'<div class="studio-card-actions"><button class="button" data-size-step="-2">A−</button><button class="button" data-size-step="2">A+</button></div>':''}<label class="property-label">Opacidade<input data-field="opacity" aria-label="Opacidade" type="range" min="0" max="1" step="0.05" value="${l.opacity??1}"></label><div class="studio-card-actions">${[['left','Esquerda'],['center','Centro X'],['right','Direita'],['top','Topo'],['middle','Centro Y'],['bottom','Base']].map(([a,label])=>`<button class="button" data-position-align="${a}">${label}</button>`).join('')}</div>${l.type==='image'?`<label class="property-label">Arredondar cantos<input type="range" data-field="radius" aria-label="Raio dos cantos" min="0" max="${Math.min(l.w,l.h)/2}" step="0.5" value="${Math.min(l.radius||0,Math.min(l.w,l.h)/2)}"></label><button class="button" data-circle-avatar>Avatar circular</button>`:''}</details>`;}
function textFields(l){return `<div class="layer-fields"><div class="formatting"><button data-toggle="bold" class="${l.bold?'on':''}" aria-label="Negrito" aria-pressed="${l.bold}"><b>B</b></button><button data-toggle="italic" class="${l.italic?'on':''}" aria-label="Itálico" aria-pressed="${l.italic}"><i>I</i></button><button data-toggle="underline" class="${l.underline?'on':''}" aria-label="Sublinhado" aria-pressed="${l.underline}"><u>U</u></button><button data-align="left" class="${l.align==='left'?'on':''}" aria-label="Alinhar à esquerda">☰</button><button data-align="center" class="${l.align==='center'?'on':''}" aria-label="Centralizar">≡</button><button data-align="right" class="${l.align==='right'?'on':''}" aria-label="Alinhar à direita">☷</button></div><label class="property-label" for="text-content">Conteúdo do texto</label><textarea id="text-content" data-field="text" maxlength="10000" rows="4">${esc(l.text)}</textarea><div class="property-inline">${colorField('color',l.color)}</div><label class="property-label">Fonte<select aria-label="Fonte" data-field="font" style="width:100%;margin-top:7px">${options(FONTS.map(x=>[x,x]),l.font)}</select></label><div class="field-grid">${field('size','Tamanho (px)',l.size,{min:8,max:400})}${field('w','Largura (px)',l.w,{min:1,max:8192})}${field('lineHeight','Entrelinhas',l.lineHeight,{min:.6,max:3,step:.05})}${field('letterSpacing','Entre letras (px)',l.letterSpacing,{min:-10,max:60,step:.1})}${field('x','Posição X',Math.round(l.x),{min:-8192,max:8192})}${field('y','Posição Y',Math.round(l.y),{min:-8192,max:8192})}</div><button data-punctuation class="text-btn">Remover ponto final deste texto</button>${fineFields(l)}${orderButtons()}</div>`;}
function orderButtons(){return '<div class="layer-order"><button data-order="up">↑ Trazer à frente</button><button data-order="down">↓ Enviar para trás</button></div>';}
function imageFields(l){return `<div class="layer-fields"><img class="image-preview" src="${l.src}" alt="Imagem selecionada"><button class="button property-add" data-replace-image>Trocar imagem</button><div class="field-grid">${field('w','Largura (px)',l.w,{min:1,max:8192})}${field('h','Altura (px)',l.h,{min:1,max:8192})}${field('x','Posição X',Math.round(l.x),{min:-8192,max:8192})}${field('y','Posição Y',Math.round(l.y),{min:-8192,max:8192})}${field('zoom','Zoom da imagem',l.zoom,{min:.2,max:5,step:.1})}${field('offsetX','Enquadramento X',l.offsetX,{min:-4096,max:4096})}${field('offsetY','Enquadramento Y',l.offsetY,{min:-4096,max:4096})}</div><button data-toggle="flip" class="button property-add" aria-pressed="${l.flip}" style="margin-top:12px">↔ ${l.flip?'Desfazer espelhamento':'Espelhar imagem'}</button>${fineFields(l)}${orderButtons()}</div>`;}
function slideActions(){return `<div class="slide-actions"><button class="button" data-duplicate-slide>⧉ Duplicar slide</button><button class="button danger" data-delete-slide ${piece().slides.length===1?'disabled':''}>Excluir slide</button></div>`;}
function renderProperties(){
  $$('[data-tab]').forEach(b=>{b.classList.toggle('selected',b.dataset.tab===tab);b.setAttribute('aria-selected',b.dataset.tab===tab);});
  const root=$('#properties');
  if(tab==='shape'||tab==='vector'){root.innerHTML='<p>Edite este elemento no painel Formas e vetores abaixo.</p>'+slideActions();return;}
  if(tab==='background'){
    const s=slide(),p=piece(),pr=projectById(p.projectId);
    root.innerHTML=`<span class="eyebrow">FUNDO DO SLIDE ${String(slideIndex+1).padStart(2,'0')}</span><label class="property-label">Cor de fundo</label><div class="property-inline">${colorField('bg',s.bg)}</div><p class="help">A cor aparece quando não há foto de fundo.</p>${s.bgImage?`<img class="image-preview" src="${s.bgImage}" alt="Foto de fundo">`:''}<button class="button primary property-add" data-bg-image>▧ ${s.bgImage?'Trocar foto de fundo':'Escolher foto de fundo'}</button>${s.bgImage?'<button class="button property-add" data-bg-remove>Usar somente cor</button>':''}<label class="property-label">Dimensões deste slide</label><div class="field-grid">${field('width','Largura (px)',s.width,{min:100,max:4096})}${field('height','Altura (px)',s.height,{min:100,max:4096})}</div><p class="help">Alterar as dimensões mantém a posição dos elementos. Ajuste o enquadramento se necessário.</p><label class="property-label">Projeto<select id="organize-project" style="width:100%;margin-top:7px">${options(state.projects.map(x=>[x.id,x.name]),p.projectId)}</select></label><label class="property-label">Pasta<select id="organize-folder" style="width:100%;margin-top:7px"><option value="">Sem pasta</option>${options(pr.folders.map(f=>[f.id,f.name]),p.folderId)}</select></label><label class="property-label">Canal<select data-piece-channel style="width:100%;margin-top:7px">${options(['Instagram','YouTube','LinkedIn','Outro'].map(x=>[x,x]),p.channel)}</select></label>${slideActions()}`;
  }else{
    const layers=slide().layers.filter(l=>l.type===tab);
    root.innerHTML=`<button class="button primary property-add" ${tab==='text'?'data-add-text':'data-add-image'}>+ Adicionar ${tab==='text'?'texto':'imagem'}</button>${tab==='text'?'<button class="text-btn property-add" data-all-punctuation>Remover pontos finais de todos os slides</button>':''}${!layers.length?`<div class="inspector-empty">${tab==='text'?'Nenhum texto neste slide.':'Nenhuma imagem neste slide.'}<br>Use o botão acima para adicionar.</div>`:layers.map(l=>`<section class="layer-item ${l.id===selected?'active':''}" data-layer="${l.id}"><div class="layer-title"><button class="layer-name" data-select="${l.id}">${esc(displayLayer(l))}</button><button class="icon-btn" data-visible="${l.id}" aria-label="${l.visible?'Ocultar':'Mostrar'} ${esc(displayLayer(l))}" title="${l.visible?'Ocultar':'Mostrar'}">${l.visible?'◉':'○'}</button><button class="icon-btn" data-remove="${l.id}" aria-label="Remover ${esc(displayLayer(l))}" title="Remover elemento">×</button></div>${l.id===selected?(tab==='text'?textFields(l):imageFields(l)):''}</section>`).join('')}${slideActions()}`;
  }
}
on('#properties','focusin',e=>{if(e.target.matches('[data-field],[data-color]'))record();});
on('#properties','input',e=>{
  const t=e.target,key=t.dataset.field||t.dataset.color;if(!key)return;if(piece()?.htmlDocument)throw Error('Altere a composição em Editar HTML preservado.');
  const target=tab==='background'?slide():layer();if(!target)return;
  if(t.dataset.color){if(!/^#[a-f\d]{6}$/i.test(t.value))return;target[key]=t.value;const picker=$(`[data-field="${key}"]`);if(picker)picker.value=t.value;}
  else if(t.type==='number'||t.type==='range'){if(t.value===''||!t.validity.valid)return;target[key]=Number(t.value);}
  else target[key]=t.value;
  if(t.type==='color'){const text=$(`[data-color="${key}"]`);if(text)text.value=t.value;}
  if(key==='width'||key==='height')$('#dimensions').textContent=`${slide().width} × ${slide().height} px`;
  $$('#properties [data-field="'+key+'"]').filter(el=>el!==t).forEach(el=>el.value=target[key]);const output=$('#properties [data-value="'+key+'"]');if(output)output.textContent=target[key];
  edited();
});
on('#properties','pointerdown',e=>{if(e.target.type==='range'&&document.activeElement===e.target)record();});
on('#properties','change',e=>{
  if(e.target.id==='organize-project')mutate(()=>{piece().projectId=e.target.value;piece().folderId=null;},{rebuild:true});
  if(e.target.id==='organize-folder')mutate(()=>piece().folderId=e.target.value||null);
  if(e.target.hasAttribute('data-piece-channel'))mutate(()=>piece().channel=e.target.value);
});
on('#properties','focusout',e=>{
  const t=e.target,key=t.dataset.field||t.dataset.color;if(!key)return;if(piece()?.htmlDocument)throw Error('Altere a composição em Editar HTML preservado.');const target=tab==='background'?slide():layer();if(target&&((t.type==='number'&&!t.validity.valid)||t.value===''))t.value=target[key];
});
on('#properties','click',e=>{
  const b=e.target.closest('button');if(!b)return;
  if(b.dataset.select){selected=b.dataset.select;renderProperties();refreshCanvas();return;}
  if(b.dataset.visible){mutate(()=>{const l=slide().layers.find(x=>x.id===b.dataset.visible);l.visible=!l.visible;},{rebuild:true});return;}
  if(b.dataset.remove){confirm('Remover elemento?','Você pode recuperar esta remoção usando Desfazer durante esta sessão.',()=>mutate(()=>{slide().layers=slide().layers.filter(x=>x.id!==b.dataset.remove);if(selected===b.dataset.remove)selected=null;},{rebuild:true}),{button:'Remover'});return;}
  if(b.hasAttribute('data-add-text')){if(slide().layers.length>=100){toast('Limite de 100 elementos por slide.',true);return;}mutate(()=>{const l=textLayer('Seu novo texto',{name:`Texto ${slide().layers.filter(l=>l.type==='text').length+1}`,y:Math.round(slide().height*.4)});slide().layers.push(l);selected=l.id;},{rebuild:true});return;}
  if(b.hasAttribute('data-add-image'))chooseImage('add');
  if(b.hasAttribute('data-replace-image'))chooseImage('replace');
  if(b.hasAttribute('data-bg-image'))chooseImage('background');
  if(b.hasAttribute('data-bg-remove'))mutate(()=>slide().bgImage=null,{rebuild:true});
  if(b.dataset.sizeStep&&layer())mutate(()=>layer().size=Math.max(8,Math.min(400,layer().size+Number(b.dataset.sizeStep))),{rebuild:true});
  if(b.hasAttribute('data-circle-avatar')&&layer())mutate(()=>{const l=layer(),d=Math.min(l.w,l.h);l.w=d;l.h=d;l.radius=d/2;},{rebuild:true});
  if(b.dataset.positionAlign&&layer())mutate(()=>{const l=layer(),a=b.dataset.positionAlign,ctx=$('#artboard').getContext('2d'),h=layerHeight(ctx,l);if(['left','center','right'].includes(a))l.x=a==='left'?0:a==='right'?slide().width-l.w:(slide().width-l.w)/2;else l.y=a==='top'?0:a==='bottom'?slide().height-h:(slide().height-h)/2;},{rebuild:true});
  if(b.dataset.toggle&&layer())mutate(()=>layer()[b.dataset.toggle]=!layer()[b.dataset.toggle],{rebuild:true});
  if(b.dataset.align&&layer())mutate(()=>layer().align=b.dataset.align,{rebuild:true});
  if(b.hasAttribute('data-punctuation')&&layer())mutate(()=>layer().text=layer().text.replace(/\.(\s*)$/,'$1'),{rebuild:true});
  if(b.hasAttribute('data-all-punctuation'))mutate(()=>piece().slides.forEach(s=>s.layers.filter(l=>l.type==='text').forEach(l=>l.text=l.text.replace(/\.(\s*)$/,'$1'))),{rebuild:true});
  if(b.dataset.order&&layer())mutate(()=>{const a=slide().layers,index=a.findIndex(l=>l.id===selected),next=Math.max(0,Math.min(a.length-1,index+(b.dataset.order==='up'?1:-1)));[a[index],a[next]]=[a[next],a[index]];},{rebuild:true});
  if(b.hasAttribute('data-duplicate-slide')){if(piece().slides.length>=30){toast('Limite de 30 slides por peça.',true);return;}mutate(()=>{piece().slides.splice(slideIndex+1,0,duplicateSlide(slide()));slideIndex++;selected=null;});renderEditor();}
  if(b.hasAttribute('data-delete-slide')&&piece().slides.length>1)confirm('Excluir slide?',`O slide ${slideIndex+1} será removido.`,()=>{mutate(()=>{piece().slides.splice(slideIndex,1);slideIndex=Math.min(slideIndex,piece().slides.length-1);selected=null;});renderEditor();},{button:'Excluir slide'});
});
function chooseImage(action){imageAction={action,pieceId:activeId,slideId:slide().id,layerId:selected};$('#image-upload').value='';$('#image-upload').click();}
on('#image-upload','change',async e=>{
  const file=e.target.files[0];if(!file)return;const request=imageAction,img=await readImage(file);
  if(activeId!==request.pieceId||slide()?.id!==request.slideId)throw new Error('O slide mudou durante a importação. Selecione a imagem novamente.');
  if(request.action==='add'&&slide().layers.length>=100)throw new Error('Limite de 100 elementos por slide.');
  mutate(()=>{if(request.action==='background')slide().bgImage=img.src;
    else if(request.action==='replace'){const l=slide().layers.find(x=>x.id===request.layerId);if(!l)throw new Error('A imagem selecionada foi removida.');l.src=img.src;}
    else {const w=Math.round(slide().width*.7),l=imageLayer(img,{name:file.name.slice(0,100),x:Math.round((slide().width-w)/2),y:100,w,maxHeight:slide().height*.7});slide().layers.push(l);selected=l.id;tab='image';}
  },{rebuild:true});toast('Imagem importada.');
});

let dragging=null;
const pointerPosition=e=>{const r=$('#artboard').getBoundingClientRect();return{x:(e.clientX-r.left)*slide().width/r.width,y:(e.clientY-r.top)*slide().height/r.height};};
on('#artboard','pointerdown',e=>{if(piece()?.htmlDocument)return;if(e.button!==0)return;const pos=pointerPosition(e),ctx=$('#artboard').getContext('2d');let hit=null;
  for(const l of [...slide().layers].reverse()){if(l.visible&&containsLayer(l,layerHeight(ctx,l),pos)){hit=l;break;}}
  selected=hit?.id||null;if(hit){tab=hit.type;dragging={id:hit.id,start:pos,x:hit.x,y:hit.y,moved:false};$('#artboard').setPointerCapture(e.pointerId);}renderProperties();refreshCanvas();
});
on('#artboard','pointermove',e=>{if(!dragging)return;const pos=pointerPosition(e),l=layer();if(!l)return;const dx=pos.x-dragging.start.x,dy=pos.y-dragging.start.y;
  if(!dragging.moved&&Math.abs(dx)+Math.abs(dy)>3){record();dragging.moved=true;}
  if(dragging.moved){l.x=Math.round(Math.max(-8192,Math.min(8192,dragging.x+dx)));l.y=Math.round(Math.max(-8192,Math.min(8192,dragging.y+dy)));refreshCanvas();}
});
function endDrag(){if(!dragging)return;if(dragging.moved){edited();renderProperties();}dragging=null;}
on('#artboard','pointerup',endDrag);on('#artboard','pointercancel',endDrag);
on(document,'keydown',e=>{
  const typing=e.target.matches('input,textarea,select,[contenteditable]');if($$('dialog[open]').length)return;
  if(!typing&&e.key==='/'&&!activeId){e.preventDefault();$('#search').focus();}
  if(activeId&&!typing&&(e.ctrlKey||e.metaKey)&&e.key.toLowerCase()==='z'){e.preventDefault();history(e.shiftKey?'redo':'undo');}
  if(activeId&&(e.ctrlKey||e.metaKey)&&e.key.toLowerCase()==='s'){e.preventDefault();if(saveFailed)retrySave();else flushSave();}
  if(activeId&&!typing&&layer()&&['ArrowLeft','ArrowRight','ArrowUp','ArrowDown'].includes(e.key)){e.preventDefault();const delta=e.shiftKey?10:1;mutate(()=>{const l=layer(),key=['ArrowLeft','ArrowRight'].includes(e.key)?'x':'y';l[key]=Math.max(-8192,Math.min(8192,l[key]+(['ArrowLeft','ArrowUp'].includes(e.key)?-delta:delta)));},{rebuild:true});}
});
on(window,'beforeunload',e=>{if(dirty!==saved){flushSave();e.preventDefault();e.returnValue='';}});
on(document,'visibilitychange',()=>{if(document.visibilityState==='hidden')flushSave();});

async function exportHTML(target=piece()){
  if(target.htmlDocument){download((await htmlExport(target,'html')).blob,slug(target.title)+'.html');return;}
  const p=clone(portablePiece(target));const pictures=[];for(const s of p.slides){const blob=await pngBlob(s);pictures.push(await new Promise((resolve,reject)=>{const r=new FileReader();r.onload=()=>resolve(r.result);r.onerror=()=>reject(r.error);r.readAsDataURL(blob);}));}
  const metadata=JSON.stringify({version:1,piece:p}).replace(/</g,'\\u003c');
  const html=`<!doctype html><html lang="pt-BR"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>${esc(p.title)}</title><style>body{background:#15101e;color:white;margin:30px;font:16px Arial}main{display:flex;gap:24px;flex-wrap:wrap}img{width:360px;max-width:100%;height:auto;display:block}figure{margin:0}figcaption{padding:12px 0;color:#cdbbdf}footer{margin-top:24px;color:#cdbbdf;font-size:12px}</style><h1>${esc(p.title)}</h1><main>${pictures.map((src,i)=>`<figure><img src="${src}" alt="Slide ${i+1}"><figcaption>${i+1} / ${p.slides.length}</figcaption></figure>`).join('')}</main><footer>Peça Studio · Importe este HTML no aplicativo para editar seus textos, imagens e fundo.</footer><script type="application/json" id="peca-studio-data">${metadata}</script></html>`;
  const blob=new Blob([html],{type:'text/html;charset=utf-8'});assertHTMLSize(blob.size);download(blob,slug(p.title)+'.html');
}
let exporting=false;
async function runExport(type,target=piece(),currentSlide=slideIndex){
  if(exporting)return;exporting=true;$$('#export-dialog button').forEach(b=>b.disabled=true);const progress=$('#export-progress');
  try{
    await ensureIntegralisAccess();progress.textContent='Preparando arquivos…';const p=clone(target);
    if(p.imageConversion&&!await verifyImageQA(p))throw Error('A conversão precisa passar na revisão ou ter exceções justificadas antes de exportar.');
    if(type==='html')await exportHTML(p);
    if(type==='png')download(p.htmlDocument?(await htmlExport(p,'png',currentSlide)).blob:await pngBlob(p.slides[currentSlide]||p.slides[0]),`${slug(p.title)}-${String(currentSlide+1).padStart(2,'0')}.png`);
    if(type==='zip'){const files=[];for(const [i,s]of p.slides.entries()){progress.textContent=`Exportando slide ${i+1} de ${p.slides.length}…`;const blob=p.htmlDocument?(await htmlExport(p,'png',i)).blob:await pngBlob(s);files.push({name:`${slug(p.title)}-${String(i+1).padStart(2,'0')}.png`,bytes:new Uint8Array(await blob.arrayBuffer())});}download(makeZip(files),slug(p.title)+'.zip');}
    progress.textContent='Arquivo preparado. Confira os downloads do navegador.';toast('Exportação concluída.');
  }catch(err){progress.textContent=err.message;throw err;}finally{exporting=false;$$('#export-dialog button').forEach(b=>b.disabled=false);}
}
on('#export-button','click',()=>{$('#export-description').textContent=`${piece().title} · ${piece().slides.length} slide(s).`;$('#export-progress').textContent='';openDialog('#export-dialog');});
on('#save-html','click',()=>runExport('html'));on('#export-html','click',()=>runExport('html'));on('#export-png','click',()=>runExport('png'));on('#export-zip','click',()=>runExport('zip'));

on('#import-button','click',()=>{if(!state.projects.length){showProject();return;}$('#import-project').innerHTML=options(state.projects.map(p=>[p.id,p.name]),filters.project);$('#html-code').value='';$('#html-file').value='';openDialog('#import-dialog');});
on('#html-file','change',async e=>{const file=e.target.files[0];if(!file)return;assertHTMLSize(file.size);$('#html-code').value=await file.text();});
on('#import-form','submit',async e=>{
  e.preventDefault();const source=$('#html-code').value;if(!source.trim())throw new Error('Selecione um HTML ou cole o código para importar.');assertHTMLSize(new Blob([source]).size);
  const inertSource=source.replace(/\b(src|href|srcset|srcdoc|poster|background|data)\s*=/gi,'data-import-$1='),doc=new DOMParser().parseFromString(inertSource,'text/html'),metadata=doc.querySelector('#peca-studio-data'),projectId=$('#import-project').value;let imported,basic=false;
  if(metadata){const parsed=JSON.parse(metadata.textContent);if(parsed.version!==1||!parsed.piece)throw new Error('Formato de design não reconhecido.');const p=clone(parsed.piece);if(p.htmlDocument)p.htmlDocument=await htmlRequest('validate',{document:p.htmlDocument});p.projectId=projectId;p.folderId=null;validateState({version:1,fonts:collectionFonts(),projects:clone(state.projects),pieces:[p]});imported=duplicatePiece(p);imported.title=p.title;imported.demo=false;}
  else if(/data-export-frame/.test(source)){imported=await prepareHTMLPiece(source,projectId,(doc.title||'HTML preservado').slice(0,180));basic=true;}
  else if(/data-export-frame|data-editable|display\s*:\s*(?:flex|grid)|linear-gradient|<svg/i.test(source)){const result=await importPackage(new Map([['index.html',new File([source],'index.html')]]),projectId);imported=result.piece;basic=true;}
  else{
    basic=true;imported=newPiece(projectId,doc.title||'Design importado');const s=imported.slides[0];s.layers=[];let y=90;
    for(const el of [...doc.body.querySelectorAll('h1,h2,h3,p,li,img')].slice(0,40)){
      if(el.tagName==='IMG'){const src=el.getAttribute('data-import-src')||'';if(!/^data:image\/(png|jpeg|webp);base64,/i.test(src)||src.length>8e6)continue;const im=await loadImage(src),l=imageLayer({src,width:im.width,height:im.height},{name:'Imagem importada',x:90,y,w:900,maxHeight:500});s.layers.push(l);y+=l.h+30;}
      else {const text=el.textContent.trim();if(!text)continue;const size=el.tagName==='H1'?80:el.tagName.startsWith('H')?58:34;s.layers.push(textLayer(text.slice(0,10000),{name:el.tagName==='H1'?'Título':'Texto importado',y:Math.min(y,8000),size,bold:el.tagName.startsWith('H')}));y+=Math.ceil(text.length/35)*size*1.2+30;}
    }
    if(!s.layers.length)throw new Error('Nenhum texto ou imagem incorporada foi encontrado. Importe um HTML com títulos, parágrafos ou imagens PNG/JPG/WebP incorporadas.');
    s.height=Math.min(4096,Math.max(1350,Math.round(y+90)));
  }
  if(filters.project===projectId)imported.folderId=filters.folder||null;await importNewPiece(imported);$('#import-dialog').close();toast(basic?'Importação básica: confira o layout e ajuste os elementos.':'Design importado com elementos editáveis.');
});

on('#settings-button','click',async()=>{const estimate=await navigator.storage?.estimate?.();$('#storage-size').textContent=`${state.projects.length} projeto(s) · ${state.pieces.length} peça(s)${estimate?.usage?' · '+(estimate.usage/1024/1024).toFixed(1)+' MB no navegador':''}`;$('#clear-demo').disabled=!state.pieces.some(p=>p.demo);openDialog('#settings-dialog');});
function backup(){const blob=new Blob([JSON.stringify(state,null,2)],{type:'application/json'});assertBackupSize(blob.size);download(blob,`peca-studio-backup-${new Date().toISOString().slice(0,10)}.json`);toast('Backup completo preparado.');}
on('#backup-export','click',backup);
on('#backup-import','change',async e=>{const file=e.target.files[0];if(!file)return;e.target.value='';assertBackupSize(file.size);const incoming=validateState(JSON.parse(await file.text()));confirm('Restaurar biblioteca?',`Substituir ${state.pieces.length} peça(s) por ${incoming.pieces.length} peça(s) deste backup? Baixe um backup atual antes de confirmar.`,async()=>{await refreshFonts(incoming);state=incoming;filters={};$('#search').value='';$('#filter-channel').value='';$('#filter-format').value='';activeId=null;$('#editor').hidden=true;$('#library').hidden=false;changed();renderLibrary();$('#settings-dialog').close();toast('Biblioteca restaurada.');},{button:'Substituir biblioteca'});});
on('#clear-demo','click',()=>confirm('Remover demonstrações?','Somente as peças marcadas como demonstração serão removidas. Cópias que você criou serão mantidas.',()=>{state.pieces=state.pieces.filter(p=>!p.demo);state.demoNotice=false;changed();if(activeId&&!piece())closeEditor();renderLibrary();$('#settings-dialog').close();toast('Peças de demonstração removidas.');},{button:'Remover demonstrações'}));


async function init(){
  $('#pieces').innerHTML='<div class="loading">Abrindo seu estúdio…</div>';
  try{const stored=await openStore();state=stored?validateState(stored):demoState();try{await refreshFonts();}catch(e){FONTS.splice(0,FONTS.length,...fontNames(collectionFonts()));toast("Uma fonte não pôde ser carregada. A arte usa substituta; cadastre novamente a fonte antes de exportar.",true);}if(!stored){await writeStore(state);}htmlUI=initHTMLDocumentUI({getPiece:piece,onApply:async p=>{record();state.pieces[state.pieces.findIndex(x=>x.id===p.id)]=p;edited();renderEditor();},download});libraryUI=initLibraryUI({getState:()=>state,getFilters:()=>filters,onFilter:(key,value)=>{filters[key]=value;page=0;renderLibrary();},onEdit:openEditor,onDuplicate:id=>{const p=duplicatePiece(state.pieces.find(x=>x.id===id));state.pieces.unshift(p);changed();renderLibrary();return p;},onVariation:id=>{const p=state.pieces.find(x=>x.id===id),result=createVariation(p,state.pieces);state.pieces=state.pieces.map(x=>x.id===id?result.original:x);state.pieces.unshift(result.variation);changed();renderLibrary();return result.variation;},onDelete:id=>{const p=state.pieces.find(x=>x.id===id);confirm('Excluir peça?',`“${p.title}” será removida. Suas variações continuam independentes.`,()=>{state=moveToTrash(state,'piece',id);changed();renderLibrary();},{button:'Excluir peça'});},onUpdate:(id,values)=>{const p=state.pieces.find(x=>x.id===id),next={...p,...values,demo:false,updatedAt:new Date().toISOString()};if(!next.title.trim())throw new Error('Informe o nome da peça.');validateState({...state,pieces:state.pieces.map(x=>x.id===id?next:x)});state.pieces=state.pieces.map(x=>x.id===id?next:x);changed();renderLibrary();},onExport:(id,type)=>runExport(type,state.pieces.find(x=>x.id===id),0),onReference:id=>styleUI.openReference(id),onFiles:id=>filesUI.open(id)});styleUI=initStyleUI({getPiece:id=>id?state.pieces.find(x=>x.id===id):piece(),getSlideIndex:()=>slideIndex,projects:()=>state.projects,onError:message=>toast(message,true),onApply:next=>{record();state.pieces=state.pieces.map(p=>p.id===activeId?{...next,demo:false,updatedAt:new Date().toISOString()}:p);changed();renderEditor();}});filesUI=initPackageUI({getPiece:id=>portablePiece(id?state.pieces.find(p=>p.id===id):piece()),projects:()=>state.projects,selectedProject:()=>filters.project,download,onImport:async p=>{await importNewPiece(p);$('#files-dialog').close();},onReload:(id,incoming)=>{const old=state.pieces.find(p=>p.id===id);if(!old)throw new Error('Peça indisponível.');const next={...incoming,id,projectId:old.projectId,folderId:old.folderId,status:old.status,angle:old.angle,variationGroupId:old.variationGroupId,parentPieceId:old.parentPieceId,versionLabel:old.versionLabel,demo:false,updatedAt:new Date().toISOString()};validateState({...state,pieces:state.pieces.map(p=>p.id===id?next:p)});if(activeId===id)record();state.pieces=state.pieces.map(p=>p.id===id?next:p);changed();if(activeId===id){slideIndex=Math.min(slideIndex,next.slides.length-1);selected=null;renderEditor();}else renderLibrary();}});renderLibrary();initBrandUI({projects:()=>state.projects,selectedProject:()=>filters.project,getPiece:piece,onSave:(id,kit)=>{const project=projectById(id);if(!project)throw new Error('Projeto indisponível.');project.brandKit=kit;changed();},onApply:p=>{record();state.pieces[state.pieces.findIndex(x=>x.id===activeId)]={...p,updatedAt:new Date().toISOString()};changed();renderEditor();}});initTemplatesUI({templates:()=>state.templates||[],projects:()=>state.projects,selectedProject:()=>filters.project,getPiece:piece,confirm,onSave:name=>{if((state.templates?.length||0)>=200)throw new Error('Limite de 200 modelos.');const t=validateTemplate(saveTemplate(portablePiece(piece()),name));state.templates=[...(state.templates||[]),t];changed();toast('Modelo salvo sem alterar a peça original.');},onRename:(id,name)=>{if(!name.trim()||name.length>120)throw new Error('Nome inválido.');const t=state.templates.find(t=>t.id===id);t.name=name.trim();changed();},onDelete:id=>{state.templates=state.templates.filter(t=>t.id!==id);changed();},onUse:(id,projectId)=>{if(!projectById(projectId))throw new Error('Escolha um projeto para criar a peça.');const t=state.templates.find(t=>t.id===id),p=useTemplate(t,projectId);state.pieces.unshift(p);changed();renderProjects();openEditor(p.id);toast('Nova peça independente criada do modelo.');}});initSourcesUI({sources:()=>state.sources||[],projects:()=>state.projects,selectedProject:()=>filters.project,confirm,onSave:source=>{const prior=state.sources||[],index=prior.findIndex(s=>s.id===source.id);if(index<0&&prior.length>=100)throw new Error('Limite de 100 fontes.');validateState({version:1,fonts:collectionFonts(),projects:clone(state.projects),pieces:[],sources:[source]});state.sources=index<0?[...prior,source]:prior.map(s=>s.id===source.id?source:s);changed();},onDelete:id=>{state.sources=(state.sources||[]).filter(s=>s.id!==id);changed();}});initAI({templates:()=>state.templates||[],projects:()=>state.projects,selectedProject:()=>filters.project,onCreate:p=>{validateState({version:1,fonts:collectionFonts(),projects:clone(state.projects),pieces:[p]});state.pieces.unshift(p);changed();renderProjects();openEditor(p.id);toast('Criação adicionada com elementos editáveis.');}});

  initFontsUI({getState:()=>state,onChange:async()=>{await refreshFonts();changed();if(piece())renderEditor();},onRefresh:()=>{if(piece())renderEditor();}});
  initImageConversion({getState:()=>({state,selectedProject:filters.project}),onImport:importNewPiece,download});
  imageReviewUI=initImageReview({getPiece:piece,download,onReviewed:next=>{record();state.pieces=state.pieces.map(p=>p.id===activeId?next:p);changed();renderEditor();}});
  artUI=initArtUI({getPiece:piece,getSlideIndex:()=>slideIndex,download,onApply:next=>{validateState({...state,pieces:state.pieces.map(p=>p.id===activeId?next:p)});record();state.pieces=state.pieces.map(p=>p.id===activeId?next:p);changed();renderEditor();}});
  initMediaUI({getState:()=>state,getPiece:piece,download,onSource:result=>{state=saveYouTubeSource(state,result);changed();toast("Fonte YouTube guardada no projeto selecionado.");}});initPublishingUI({getState:()=>state,getPiece:piece,download});initDesktopUI({beforeInstall:async()=>{await flushSave();if(dirty!==saved)throw Error('Salve ou faça backup antes de atualizar.');}});initIntegralisUI({container:document.querySelector('.studio-launchers')});
  initTrashUI({getState:()=>state,download,onApply:async next=>{await replaceLibrary(next);changed();renderLibrary();}});
  initPrintUI({getPiece:()=>portablePiece(piece()),getSlideIndex:()=>slideIndex,download,onResize:next=>{record();state.pieces=state.pieces.map(p=>p.id===activeId?next:p);changed();selected=null;renderEditor();}});
  workspaceUI=initWorkspaceUI({getState:()=>state,onReplace:replaceLibrary,download,isDirty:()=>saving||dirty!==saved||saveFailed,beforeSwitch:async()=>{await flushSave();if(saving||dirty!==saved||saveFailed)throw Error('Conclua o salvamento ou baixe um backup antes de trocar a biblioteca.');}});
  }catch(err){$('#pieces').innerHTML='<div class="empty-state"><h2>Não foi possível abrir a biblioteca.</h2><p>Recarregue a página. Se o erro persistir, confira se o armazenamento do navegador está disponível. Seus dados existentes não foram substituídos.</p></div>';error(err);saveStatus('Biblioteca indisponível',true);$$('.heading-actions button').forEach(b=>b.disabled=true);}
}
init();
