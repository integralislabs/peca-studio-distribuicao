import {initPackageUI} from '../package-ui.js';import {newPiece} from '../model.js';
const $=s=>document.querySelector(s),results=[],created=[];let current=newPiece('project','Peça QA'),reloaded=0,writes=0;
const tree=new Map();let permissionError=false;
function dir(map,name='QA descartável'){return {kind:'directory',name,async *entries(){yield*map.entries();},async getDirectoryHandle(name){if(!map.has(name))map.set(name,dir(new Map(),name));return map.get(name);},async getFileHandle(name){if(!map.has(name))map.set(name,{kind:'file',async getFile(){return new File([''],name);}});const old=map.get(name);return {...old,async createWritable(){if(permissionError)throw new DOMException('Permissão revogada','NotAllowedError');let pending;return {async write(bytes){pending=bytes;writes++;},async close(){map.set(name,{kind:'file',async getFile(){return new File([pending],name);}});},async abort(){}};}};}};}
const handle=dir(tree),api=initPackageUI({getPiece:id=>current,projects:()=>[{id:'project',name:'Projeto QA'}],selectedProject:()=> 'project',onImport:p=>created.push(p),onReload:(id,p)=>{current={...p,id};reloaded++;},download:()=>{},chooseDirectory:async()=>handle,watchInterval:60000});
const assert=(v,msg='Condição não satisfeita')=>{if(!v)throw new Error(msg);};const wait=async f=>{for(let i=0;i<100;i++){if(f())return;await new Promise(r=>setTimeout(r,10));}throw new Error('Tempo excedido');};const test=async(name,fn)=>{try{await fn();results.push('PASS · '+name);}catch(e){results.push('FAIL · '+name+' · '+e.message);}$('#results').textContent=results.join('\n');};
await test('pasta vazia vinculada não grava sem autorização',async()=>{api.open(current.id);$('#files-link').click();await wait(()=>$('#files-status').textContent.includes('vinculada'));$('#files-save').click();await wait(()=>$('#files-status').textContent.includes('autorize'));assert(writes===0);});
await test('salvar grava pacote e mantém biblioteca sem substituição',async()=>{$('#files-write-consent').checked=true;$('#files-save').click();await wait(()=>$('#files-status').textContent.includes('Pacote salvo'));assert(tree.has('index.html')&&tree.has('peca-studio.json'));assert(reloaded===0);});
await test('mudança externa é detectada e bloqueia sobrescrita',async()=>{const old=await tree.get('index.html').getFile();tree.set('index.html',{kind:'file',async getFile(){return new File([await old.text(),'<!--externo-->'],'index.html');}});$('#files-check').click();await wait(()=>$('#files-status').textContent.includes('Alteração externa'));const before=writes;$('#files-save').click();await wait(()=>$('#files-status').textContent.includes('pasta mudou'));assert(writes===before);});
await test('recarregar exige confirmação para descartar edição local',async()=>{current.title='Edição local';$('#files-reload').click();await wait(()=>!$('#files-reload-confirm').hidden);assert(reloaded===0);$('#files-confirm-reload').click();await wait(()=>reloaded===1);assert(current.title==='Peça QA');});
await test('permissão revogada informa possível gravação parcial sem alterar peça',async()=>{permissionError=true;const title=current.title;$('#files-save').click();await wait(()=>$('#files-status').textContent.includes('parcial'));assert(current.title===title);permissionError=false;});
await test('desvincular conserva peça e remove sessão de arquivo',()=>{$('#files-unlink').click();assert(current.title==='Peça QA');assert($('#files-save').disabled);$('#files-close').click();api.destroy();});

async function freshUI(options={}){const instance=initPackageUI({getPiece:()=>current,projects:()=>[{id:'project',name:'Projeto QA'}],selectedProject:()=> 'project',onImport:p=>created.push(p),onReload:(id,p)=>{current={...p,id};reloaded++;},download:()=>{},chooseDirectory:async()=>handle,watchInterval:60000,...options});instance.open(current.id);return instance;}
await test('resultado Watching antigo não sobrescreve salvamento concluído',async()=>{
 const ui=await freshUI();try{
  $('#files-link').click();await wait(()=>$('#files-status').textContent.includes('vinculada'));
  const original=tree.get('index.html'),file=await original.getFile();let entered=false,release;const gate=new Promise(resolve=>release=resolve);let pause=true;
  tree.set('index.html',{kind:'file',async getFile(){if(!pause)return file;pause=false;return {size:file.size,async arrayBuffer(){entered=true;await gate;return file.arrayBuffer();}};}});
  $('#files-check').click();await wait(()=>entered);current.title='Versão salva durante Watching';$('#files-write-consent').checked=true;$('#files-save').click();await wait(()=>$('#files-status').textContent.includes('Pacote salvo'));release();await new Promise(r=>setTimeout(r,80));assert($('#files-status').textContent==='Pacote salvo na pasta vinculada.','Watching antigo substituiu status salvo');assert(!$('#files-state').textContent.includes('alteração externa'),'Watching marcou conflito falso');
 }finally{ui.destroy();}
});
await test('erro Watching pendente não reaparece após desvincular',async()=>{
 const ui=await freshUI();let release;try{
  $('#files-link').click();await wait(()=>$('#files-status').textContent.includes('vinculada'));const file=await tree.get('index.html').getFile();let entered=false;const gate=new Promise(resolve=>release=resolve);let pause=true;
  tree.set('index.html',{kind:'file',async getFile(){if(!pause)return file;pause=false;return {size:file.size,async arrayBuffer(){entered=true;await gate;throw new Error('Falha antiga do Watching');}};}});
  $('#files-check').click();await wait(()=>entered);$('#files-unlink').click();release();await new Promise(r=>setTimeout(r,80));assert($('#files-status').textContent==='Pasta desvinculada. A peça permanece na biblioteca.','erro antigo reapareceu após desvincular');assert($('#files-save').disabled,'sessão desvinculada foi reativada');
 }finally{release?.();ui.destroy();}
});
await test('cancelar seletor nativo não grava nem cria vínculo',async()=>{
 let pickerCalls=0;const before=writes,ui=await freshUI({chooseDirectory:async options=>{pickerCalls++;assert(options.mode==='readwrite','modo do seletor incorreto');throw new DOMException('Cancelado','AbortError');}});try{$('#files-link').click();await wait(()=>$('#files-dialog').getAttribute('aria-busy')==='false');assert(pickerCalls===1&&writes===before,'cancelamento gerou gravação');assert($('#files-state').textContent==='Sem pasta vinculada.','cancelamento criou vínculo');assert(!$('#files-status').classList.contains('error'),'cancelamento foi tratado como erro');}finally{ui.destroy();}
});
$('#results').textContent=results.join('\n')+'\n\n'+(results.every(r=>r.startsWith('PASS'))?'TODOS OS '+results.length+' TESTES PASSARAM':'HÁ FALHAS');

await test('Watching pendente não substitui resultado de recarga explícita',async()=>{
 const ui=await freshUI();let release;try{
  $('#files-link').click();await wait(()=>$('#files-status').textContent.includes('vinculada'));const file=await tree.get('index.html').getFile();let entered=false,pause=true;const gate=new Promise(resolve=>release=resolve);
  tree.set('index.html',{kind:'file',async getFile(){if(!pause)return file;pause=false;return {size:file.size,async arrayBuffer(){entered=true;await gate;return file.arrayBuffer();}};}});
  $('#files-check').click();await wait(()=>entered);const before=reloaded;$('#files-reload').click();await wait(()=>reloaded===before+1&&$('#files-status').textContent.includes('Peça recarregada'));release();await new Promise(r=>setTimeout(r,80));assert($('#files-status').textContent.startsWith('Peça recarregada da pasta.'),'Watching antigo substituiu recarga');
 }finally{release?.();ui.destroy();}
});
$('#results').textContent=results.join('\n')+'\n\n'+(results.every(r=>r.startsWith('PASS'))?'TODOS OS '+results.length+' TESTES PASSARAM':'HÁ FALHAS');
