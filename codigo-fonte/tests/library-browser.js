import {newPiece,duplicatePiece,filterPieces,validateState} from '../model.js';
import {createVariation,familyId,libraryStats} from '../library.js';
import {initLibraryUI} from '../library-ui.js';
const checks=[],$=s=>document.querySelector(s),assert=(ok,label)=>{if(!ok)throw new Error(label);checks.push(label);};
const tick=()=>new Promise(resolve=>setTimeout(resolve,30));
const click=async name=>{$(`[data-detail-action="${name}"]`).click();await tick();};
try{
 const project={id:'project-qa',name:'Projeto fictício',color:'#123456',folders:[{id:'folder-qa',name:'Campanha QA'}]},a=newPiece(project.id,'Peça A'),b=newPiece(project.id,'Peça B');
 a.folderId='folder-qa';a.caption='Legenda A';b.caption='Legenda B';
 const state={version:1,projects:[project],pieces:[a,b]},filters={},exports=[],refs=[],edits=[];
 let ui;
 const update=(id,values)=>{const index=state.pieces.findIndex(p=>p.id===id),next={...state.pieces[index],...values};validateState({...state,pieces:state.pieces.map((p,i)=>i===index?next:p)});state.pieces[index]=next;};
 function paintCards(){const grid=$('#pieces');grid.replaceChildren();for(const p of filterPieces(state.pieces,filters)){const button=document.createElement('button');button.type='button';button.className='piece-art-button';button.style.minHeight='80px';button.dataset.selectPiece=p.id;button.textContent=p.title;button.addEventListener('click',()=>ui.select(p.id));grid.append(button);}}
 ui=initLibraryUI({getState:()=>state,getFilters:()=>filters,onFilter:(key,value)=>{filters[key]=value;paintCards();ui.render();},onEdit:id=>edits.push(id),onDuplicate:id=>{const piece=duplicatePiece(state.pieces.find(p=>p.id===id));state.pieces.push(piece);paintCards();return piece;},onVariation:id=>{const index=state.pieces.findIndex(p=>p.id===id),result=createVariation(state.pieces[index],state.pieces);state.pieces[index]=result.original;state.pieces.push(result.variation);paintCards();return result.variation;},onDelete:id=>{state.pieces=state.pieces.filter(p=>p.id!==id);paintCards();ui.render();},onUpdate:update,onExport:(id,type)=>exports.push({id,type,caption:state.pieces.find(p=>p.id===id).caption}),onReference:id=>refs.push(id),onFiles:()=>{}});
 paintCards();ui.render();
 $(`[data-select-piece="${a.id}"]`).click();assert(ui.getSelected().id===a.id,'seleção A por botão');await click('html');
 $(`[data-select-piece="${b.id}"]`).click();await click('png');await click('zip');
 assert(exports[0].id===a.id&&exports[0].type==='html'&&exports[0].caption==='Legenda A','exporta HTML explicitamente da peça A');
 assert(exports.slice(1).every(e=>e.id===b.id&&e.caption==='Legenda B')&&exports[1].type==='png'&&exports[2].type==='zip','PNG/ZIP pertencem à seleção B');
 assert($(`[data-select-piece="${b.id}"]`).getAttribute('aria-pressed')==='true'&&$(`[data-select-piece="${a.id}"]`).getAttribute('aria-pressed')==='false','seleção acessível aria-pressed estável');
 await click('reference');assert(refs[0]===b.id,'Ref. IA recebe ID explícito B');
 const originalB=structuredClone(state.pieces.find(p=>p.id===b.id));await click('variation');const variation=ui.getSelected(),original=state.pieces.find(p=>p.id===b.id);
 assert(variation.id!==b.id&&variation.parentPieceId===b.id&&familyId(variation)===familyId(original),'variação independente ligada à família B');
 assert(variation.slides[0].id!==original.slides[0].id&&variation.slides[0].layers[0].id!==original.slides[0].layers[0].id,'IDs independentes de slides e camadas');
 variation.slides[0].layers[0].text='Alteração só na variação';assert(original.slides[0].layers[0].text===originalB.slides[0].layers[0].text,'editar variação preserva original');
 await click('compare');assert($('#compare-dialog').open,'comparação abre diálogo');assert(new Set([$('#compare-left').value,$('#compare-right').value]).size===2&&$('#compare-left').options.length===2,'comparação contém as duas peças da família');
 $('#compare-open-right').click();assert(edits.at(-1)===original.id&&!$('#compare-dialog').open,'editar direita usa ID mostrado na comparação');
 await click('family');assert(filters.family===familyId(variation)&&$('#pieces').children.length===2,'filtro família mostra original e variação');$('#clear-family').click();assert(!filters.family&&$('#pieces').children.length===3,'limpar família restaura três peças');
 const form=$('#detail-form');form.elements.status.value='Publicado';form.elements.angle.value='Educação';form.elements.caption.value='Legenda da variação';form.requestSubmit();await tick();
 assert(ui.getSelected().status==='Publicado'&&ui.getSelected().angle==='Educação','detalhes salvam Publicado e ângulo editorial');const stats=libraryStats(state.pieces);assert(stats.published===1&&stats.pipeline===2&&stats.angles===1&&stats.total===3,'contadores derivados corretos');
 assert([...$('#library-metrics').children].some(el=>el.textContent==='1Publicados'),'contador Publicados refletido no DOM');
 $('#filter-status').value='Publicado';$('#filter-status').dispatchEvent(new Event('change'));assert($('#pieces').children.length===1,'filtro Publicado usa estado salvo');$('#filter-status').value='';$('#filter-status').dispatchEvent(new Event('change'));
 const details=$('#piece-detail details');details.open=true;const field=$('[aria-label="ID Peça"]'),copy=$(`[data-copy-id="${variation.id}"]`);assert(field.readOnly&&field.value===variation.id&&copy,'IDs disponíveis em campo somente leitura e botão');
 // Clipboard permission depends on browser focus; exercise rejection without touching the system clipboard.
 const descriptor=Object.getOwnPropertyDescriptor(navigator,'clipboard');Object.defineProperty(navigator,'clipboard',{configurable:true,value:{writeText:async()=>{throw new Error('Cópia indisponível no teste; copie o ID pelo teclado.');}}});
 try{copy.click();await tick();assert($('#detail-status').textContent.includes('copie o ID pelo teclado'),'erro de clipboard tem alternativa pelo teclado');}finally{if(descriptor)Object.defineProperty(navigator,'clipboard',descriptor);else delete navigator.clipboard;}
 await click('duplicate');const duplicate=ui.getSelected();assert(!duplicate.variationGroupId&&!duplicate.parentPieceId&&duplicate.id!==variation.id,'duplicação simples é independente da família');
 ui.select(a.id);assert(ui.getSelected().id===a.id&&$('#piece-detail h2').textContent==='Peça A','seleção A continua independente depois das operações');
 const renderedControls=[...$('#piece-detail').querySelectorAll('button,input,select,textarea')].filter(el=>el.getClientRects().length);
 assert(renderedControls.every(el=>el.getBoundingClientRect().width>0),'controles do painel têm largura positiva');
 const overflow=document.documentElement.scrollWidth>innerWidth;
 $('#results').textContent=`PASS ${checks.length}\n${checks.join('\n')}\nViewport: ${innerWidth}px; overflow horizontal: ${overflow?'SIM':'não'}\n`;document.title='PASS Biblioteca '+checks.length;
 window.libraryQA={ui,state,checks};
}catch(e){$('#results').textContent='FAIL '+e.stack+'\n'+checks.join('\n');document.title='FAIL Biblioteca';}
