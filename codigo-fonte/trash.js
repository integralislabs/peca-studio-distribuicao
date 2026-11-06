import {clone,uid,validateState} from './model.js';
export function moveToTrash(state,kind,id){
 const next=clone(state),project=kind==='project'?next.projects.find(p=>p.id===id):next.projects.find(p=>p.id===next.pieces.find(x=>x.id===id)?.projectId);
 if(!project||!['piece','project'].includes(kind))throw Error('Item indisponível.');
 const pieces=next.pieces.filter(p=>kind==='project'?p.projectId===id:p.id===id);
 if(kind==='piece'&&!pieces.length)throw Error('Peça indisponível.');
 if((next.trash?.length||0)>=500)throw Error('Lixeira cheia. Exporte um backup e remova itens da lixeira.');
 const snapshot={version:1,fonts:clone(next.fonts||[]),projects:[clone(project)],pieces:clone(pieces),sources:kind==='project'?clone((next.sources||[]).filter(s=>s.projectId===id)):[]};
 next.trash=[{id:uid(),kind,deletedAt:new Date().toISOString(),snapshot},...(next.trash||[])];
 next.pieces=next.pieces.filter(p=>!pieces.some(x=>x.id===p.id));
 if(kind==='project'){next.projects=next.projects.filter(p=>p.id!==id);next.sources=(next.sources||[]).filter(s=>s.projectId!==id);}
 return validateState(next);
}
export function restoreTrash(state,id){
 const next=clone(state),entry=next.trash?.find(t=>t.id===id);if(!entry)throw Error('Item não encontrado.');
 const snap=clone(entry.snapshot),project=snap.projects[0],existing=next.projects.find(p=>p.id===project.id);
 if(!existing)next.projects.push(project);
 else for(const folder of project.folders)if(!existing.folders.some(f=>f.id===folder.id))existing.folders.push(folder);
 for(const p of snap.pieces){if(next.pieces.some(x=>x.id===p.id))throw Error('Já existe uma peça com esse ID. Preserve um backup antes de resolver o conflito.');next.pieces.push(p);}
 for(const source of snap.sources||[]){if(!(next.sources||[]).some(x=>x.id===source.id))next.sources=[...(next.sources||[]),source];}
 for(const f of snap.fonts||[]){const old=(next.fonts||[]).find(x=>x.name===f.name);if(old&&old.data!==f.data)throw Error('Conflito de fontes ao restaurar.');if(!old)next.fonts=[...(next.fonts||[]),f];}
 next.trash=next.trash.filter(t=>t.id!==id);return validateState(next);
}
