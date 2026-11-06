import {initSourcesUI} from '../sources-ui.js';
const $=s=>document.querySelector(s),results=[],saved=[],events=[],calls=[];
let failMedia=false;
window.fetch=async(url,options)=>{calls.push({url,options});if(url!=='/api/ai/transcribe')throw new Error('Rede externa bloqueada no QA');return new Response(JSON.stringify(failMedia?{error:'Erro simulado'}:{cues:[{start:.125,end:3.5,text:'Transcrição simulada.'}]}),{status:failMedia?502:200});};
initSourcesUI({sources:()=>saved,projects:()=>[{id:'project',name:'Projeto QA'}],selectedProject:()=> 'project',onSave:s=>{const i=saved.findIndex(v=>v.id===s.id);if(i<0)saved.push(s);else saved[i]=s;},onDelete:()=>{},confirm:(a,b,fn)=>fn()});
document.addEventListener('studio:compose-source',e=>events.push(e.detail));
const assert=(v,message='Condição não satisfeita')=>{if(!v)throw new Error(message);};
const wait=async fn=>{for(let i=0;i<100;i++){if(fn())return;await new Promise(r=>setTimeout(r,15));}throw new Error('Tempo excedido');};
const test=async(name,fn)=>{try{await fn();results.push('PASS · '+name);}catch(e){results.push('FAIL · '+name+' · '+e.message);}$('#results').textContent=results.join('\n');};
const file=(selector,f)=>{const dt=new DataTransfer();dt.items.add(f);$(selector).files=dt.files;$(selector).dispatchEvent(new Event('change',{bubbles:true}));};
await test('SRT importado localmente preserva frações e salva fonte',async()=>{
 $('#sources-library').click();file('#source-file',new File(['1\n00:17:06,125 --> 00:17:10,500\nPrimeira ideia.\n\n2\n00:17:10,500 --> 00:18:05,250\nSegunda ideia.'],'aula.srt',{type:'text/plain'}));await wait(()=>$('#source-status').textContent.startsWith('Transcrição importada'));$('#source-form').requestSubmit();assert(saved.length===1);assert($('#source-start').value==='17:06.125');assert($('#source-end').value==='18:05.25');assert(calls.length===0);
});
await test('Preparar carrossel encaminha somente trecho selecionado, sem API',()=>{
 $('#source-start').value='17:10.5';$('#source-range').click();$('[data-source-kind="carousel"]').click();assert(events.length===1);assert(events[0].kind==='carousel');assert(events[0].source.text==='Segunda ideia.');assert(events[0].source.start===1030.5);assert(calls.length===0);
});
await test('Preparar Short de texto comum não inventa tempo',()=>{
 $('#sources-library').click();$('#source-title').value='Texto sem horário';$('#source-transcript').value='Uma ideia sem marcação de tempo.';$('#source-read').click();$('[data-source-kind="short"]').click();assert(events.at(-1).kind==='short');assert(events.at(-1).source.start===null);
});
await test('Mídia exige consentimento separado antes de chamar a API',()=>{
 $('#sources-library').click();file('#source-media',new File(['fake-qa'],'qa.wav',{type:'audio/wav'}));$('#source-transcribe').click();assert(calls.length===0);assert($('#source-status').textContent.includes('autorize'));
});
await test('Transcrição retorna prévia; salvar é explícito, sem retry',async()=>{
 const before=saved.length;$('#source-media-consent').checked=true;$('#source-transcribe').click();await wait(()=>$('#source-status').textContent.startsWith('Transcrição pronta'));assert(saved.length===before);assert(calls.length===1);assert(calls[0].options.headers['X-Peca-Consent']==='1');assert($('#source-start').value==='00:00.125');$('#source-form').requestSubmit();assert(saved.length===before+1);
});
await test('Falha preserva transcrição anterior e reativa formulário',async()=>{
 failMedia=true;const previous=$('#source-transcript').value;$('#source-transcribe').click();await wait(()=>$('#source-status').textContent.startsWith('Erro simulado'));assert($('#source-transcript').value===previous);assert(calls.length===2);assert(!$('#source-transcribe').disabled);$('#sources-close').click();
});
$('#results').textContent+='\n\n'+(results.every(r=>r.startsWith('PASS'))?'TODOS OS 6 TESTES PASSARAM':'HÁ FALHAS');
