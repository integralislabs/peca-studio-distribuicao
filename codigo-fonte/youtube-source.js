import {clone,validateState} from './model.js';
import {makeSource} from './sources.js';
export function saveYouTubeSource(state,result){
 const next=clone(state);if(!next.projects.some(p=>p.id===result.projectId))throw Error('Escolha o projeto para guardar a fonte.');
 if((next.sources?.length||0)>=100)throw Error('Limite de 100 fontes. Remova uma fonte antes de importar.');
 const subtitle=result.subtitles?.find(s=>s.language?.startsWith('pt'))||result.subtitles?.[0];
 const transcript=subtitle?.text||['METADADOS — SEM TRANSCRIÇÃO: as legendas não foram obtidas.',result.title,result.description||'Descrição indisponível.',...(result.warnings||[])].join('\n\n').slice(0,150000);
 const source=makeSource({projectId:result.projectId,title:String(result.title||'YouTube').slice(0,180),url:result.url,transcript});
 next.sources=[source,...(next.sources||[])];return validateState(next);
}
