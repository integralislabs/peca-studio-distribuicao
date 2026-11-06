import {newPiece,uid} from './model.js';

export async function htmlRequest(action,body){
 const r=await fetch('/api/local/html/'+action,{method:'POST',headers:{'Content-Type':'application/json','X-Peca-Request':'1'},body:JSON.stringify(body)}),v=await r.json();if(!r.ok)throw Error(v.error||'Não foi possível processar o HTML.');return v;
}
export async function htmlExport(piece,format,frame=0){
 const v=await htmlRequest('render',{document:piece.htmlDocument,format,frame});return {blob:new Blob([Uint8Array.from(atob(v.base64),c=>c.charCodeAt(0))],{type:v.mime}),warnings:['HTML renderizado pelo Microsoft Edge; confira fontes e elementos antes da impressão.']};
}
export async function prepareHTMLPiece(source,projectId,title='HTML preservado'){
 const document=await htmlRequest('prepare',{html:source});
 const p=newPiece(projectId,title);p.htmlDocument=document;p.slides=[];
 for(const [index,frame] of document.frames.entries()){
  const v=await htmlRequest('render',{document,format:'png',frame:index});
  p.slides.push({id:uid(),width:frame.width,height:frame.height,bg:'#ffffff',bgImage:'data:image/png;base64,'+v.base64,layers:[]});
 }
 return p;
}

/** Keep the actual HTML as source of truth. Canvas is a regenerated thumbnail, never the editor. */
export function initHTMLDocumentUI({getPiece,onApply,download}){
 const trigger=document.createElement('button');trigger.id='edit-html-document';trigger.className='button';trigger.textContent='Editar HTML preservado';trigger.hidden=true;document.querySelector('.editor-heading').append(trigger);
 const d=document.createElement('dialog');d.id='html-document-dialog';d.className='studio-dialog';d.style.width='min(1100px,95vw)';
 d.innerHTML='<div class="dialog-heading"><h2>HTML preservado</h2><button data-close class="icon-btn" aria-label="Fechar">×</button></div><p>Esta peça mantém o HTML/CSS como fonte. Altere os campos e controles abaixo; a prévia e as exportações usam esse mesmo documento.</p><div data-fields></div><div style="overflow:auto;max-height:55vh;background:#fff"><iframe title="Prévia do HTML preservado" sandbox="allow-same-origin" referrerpolicy="no-referrer" style="border:0;display:block"></iframe></div><div class="studio-card-actions"><button data-save class="button primary">Aplicar e atualizar prévia</button><button data-export class="button">Baixar HTML editável</button><button data-detach class="button">Desvincular do HTML</button></div><p data-status role="status"></p>';
 document.body.append(d);const fields=d.querySelector('[data-fields]'),preview=d.querySelector('iframe'),status=d.querySelector('[data-status]');let snapshot;
 const esc=x=>String(x).replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
 function paint(){const doc=snapshot.htmlDocument,frame=doc.frames[0];fields.innerHTML=doc.editables.map((e,i)=>`<label>${esc(e.key)}${e.type==='image'?`<input type="file" accept="image/png,image/jpeg,image/webp" data-image="${i}">`:`<textarea data-text="${i}">${esc(e.value)}</textarea>`}</label>`).join('')+doc.controls.map((c,i)=>`<label>${esc(c.label)} (${esc(c.unit)})<input data-control="${i}" type="number" min="${c.min}" max="${c.max}" step="any" value="${c.value??''}" placeholder="${c.min} a ${c.max}"></label>`).join('');preview.width=frame.width;preview.height=frame.height;preview.style.width=frame.width+'px';preview.style.height=frame.height+'px';preview.style.maxWidth='none';preview.srcdoc=doc.html;}
 trigger.onclick=async()=>{try{snapshot=structuredClone(getPiece());snapshot.htmlDocument=await htmlRequest('validate',{document:snapshot.htmlDocument});paint();status.textContent='';d.showModal();}catch(e){status.textContent=e.message;d.showModal();fields.replaceChildren();preview.srcdoc='';}};d.querySelector('[data-close]').onclick=()=>d.close();
 d.querySelector('[data-save]').onclick=async()=>{const button=d.querySelector('[data-save]');button.disabled=true;try{status.textContent='Aplicando controles e renderizando o HTML…';const texts={},controls={};for(const input of fields.querySelectorAll('[data-text]'))texts[snapshot.htmlDocument.editables[+input.dataset.text].key]=input.value;for(const input of fields.querySelectorAll('[data-image]'))if(input.files[0]){if(input.files[0].size>5_000_000)throw Error('Imagem limitada a 5 MB.');texts[snapshot.htmlDocument.editables[+input.dataset.image].key]=await new Promise((resolve,reject)=>{const r=new FileReader();r.onload=()=>resolve(r.result);r.onerror=reject;r.readAsDataURL(input.files[0]);});}for(const input of fields.querySelectorAll('[data-control]'))if(input.value!=='')controls[snapshot.htmlDocument.controls[+input.dataset.control].variable]=Number(input.value);const doc=await htmlRequest('update',{document:snapshot.htmlDocument,texts,controls});const current=getPiece();if(current.id!==snapshot.id||current.htmlDocument?.sha256!==snapshot.htmlDocument.sha256)throw Error('A peça mudou durante a edição. Feche e abra novamente.');const next=structuredClone(current);next.htmlDocument=doc;for(const [i,frame] of doc.frames.entries()){const v=await htmlRequest('render',{document:doc,format:'png',frame:i});next.slides[i]={...next.slides[i],width:frame.width,height:frame.height,bgImage:'data:image/png;base64,'+v.base64,layers:[]};}await onApply(next);snapshot=structuredClone(next);paint();status.textContent='HTML e prévia atualizados. Os estilos e controles continuam preservados.';}catch(e){status.textContent=e.message;}finally{button.disabled=false;}};
 d.querySelector('[data-export]').onclick=async()=>{try{download((await htmlExport(snapshot,'html')).blob,'peca-html-editavel.html');}catch(e){status.textContent=e.message;}};
 d.querySelector('[data-detach]').onclick=async()=>{try{const next=structuredClone(getPiece());delete next.htmlDocument;await onApply(next);d.close();}catch(e){status.textContent=e.message;}};
 return {refresh(){trigger.hidden=!getPiece()?.htmlDocument;}};
}

