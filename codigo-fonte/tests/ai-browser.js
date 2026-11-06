import {initAI} from '../ai-ui.js';
import {defaultBrand} from '../brand.js';
import {saveTemplate} from '../templates.js';
const $=s=>document.querySelector(s),results=[],calls=[],projects=[],created=[],models=[];
let contentFails=false,imageFails=false;
const fixtureCanvas=document.createElement('canvas');fixtureCanvas.width=16;fixtureCanvas.height=16;fixtureCanvas.getContext('2d').fillRect(0,0,16,16);const fixturePNG=fixtureCanvas.toDataURL('image/png');
const draft={title:'Teste do gerador',caption:'Legenda de teste',slides:[{title:'Uma ideia viva',body:'Textos editáveis em camadas.',imagePrompt:'Uma folha verde'}]};
window.fetch=async(url,options)=>{
 if(!String(url).startsWith('/api/ai/'))throw new Error('Rede externa proibida no QA.');
 const data=options?.body?JSON.parse(options.body):null;calls.push({url,data});
 if(url.endsWith('/config'))return new Response(JSON.stringify({configured:true,simulation:true,providers:{openai:{configured:true},claude:{configured:true},gemini:{configured:true}}}),{status:200});
 if(url.endsWith('/content'))return new Response(JSON.stringify(contentFails?{error:'Erro de teste'}:{draft}),{status:contentFails?502:200});
 if(url.endsWith('/image'))return new Response(JSON.stringify(imageFails?{error:'Erro de imagem de teste'}:{src:fixturePNG}),{status:imageFails?502:200});
 throw new Error('Rota inesperada');
};
initAI({projects:()=>projects,templates:()=>models,onCreate:p=>created.push(p)});
const wait=async fn=>{for(let i=0;i<100;i++){if(fn())return;await new Promise(r=>setTimeout(r,15));}throw new Error('Tempo de espera excedido.');};
const test=async(name,fn)=>{try{await fn();results.push('PASS · '+name);}catch(e){results.push('FAIL · '+name+' · '+e.message);}$('#results').textContent=results.join('\n');};
const assert=(value,message='Condição não satisfeita')=>{if(!value)throw new Error(message);};
await test('Reabrir após criar primeiro projeto habilita a geração',async()=>{
 $('#generate-ai').click();await wait(()=>$('#ai-connection').textContent);assert($('#ai-generate').disabled);
 $('#ai-close').click();projects.push({id:'qa-project',name:'Projeto QA'});$('#generate-ai').click();assert(!$('#ai-generate').disabled);
});
await test('Geração produz prévia sem gravar biblioteca antes da revisão',async()=>{
 $('#ai-form').elements.topic.value='Uma ideia';$('#ai-form').elements.count.value='1';$('#ai-consent').checked=true;
 $('#ai-form').requestSubmit();await wait(()=>!$('#ai-preview').hidden);assert(created.length===0);assert($('#ai-title').value===draft.title);
 assert(calls.filter(c=>c.url.endsWith('content')).length===1);
});
await test('Falha de imagem mantém prévia e não repete chamadas',async()=>{
 imageFails=true;$('#ai-image-consent').checked=true;$('#ai-slides [data-image]').click();await wait(()=>$('#ai-status').textContent==='Erro de imagem de teste');assert($('#ai-title').value===draft.title);assert(calls.filter(c=>c.url.endsWith('image')).length===1);
});
await test('Falha em nova geração permite voltar ao rascunho anterior',async()=>{
 $('#ai-edit-brief').click();contentFails=true;$('#ai-form').requestSubmit();await wait(()=>$('#ai-status').textContent==='Erro de teste');$('#ai-resume').click();assert(!$('#ai-preview').hidden);assert($('#ai-title').value===draft.title);
});
await test('Salvar cria uma peça com camadas e legenda e impede duplicação do clique',async()=>{
 $('#ai-title').value='Título revisado';$('#ai-caption').value='Legenda revisada';$('#ai-save').click();$('#ai-save').click();assert(created.length===1);assert(created[0].title==='Título revisado');assert(created[0].caption==='Legenda revisada');assert(created[0].slides[0].layers.every(l=>l.type==='text'));
});
await test('Configurar chave não inclui a chave em peça ou chamadas de geração',async()=>{
 $('#ai-settings').click();$('#ai-key').value='sk-chave-falsa-do-qa';$('#ai-config-form').requestSubmit();await wait(()=>!$('#ai-config-dialog').open);assert($('#ai-key').value==='');assert(!JSON.stringify(created).includes('sk-chave-falsa'));assert(calls.filter(c=>!c.url.endsWith('config')).every(c=>!JSON.stringify(c).includes('sk-chave-falsa')));
});
await test('Trocar serviço limpa consentimento e separa textos de imagens',async()=>{
 contentFails=false;$('#generate-ai').click();$('#ai-provider').value='claude';$('#ai-provider').dispatchEvent(new Event('change'));assert(!$('#ai-consent').checked);$('#ai-consent').checked=true;$('#ai-form').requestSubmit();await wait(()=>!$('#ai-preview').hidden);assert(calls.filter(c=>c.url.endsWith('content')).at(-1).data.provider==='claude');
 $('#ai-image-consent').checked=true;$('#ai-image-provider').value='gemini';$('#ai-image-provider').dispatchEvent(new Event('change'));assert(!$('#ai-image-consent').checked);assert(![...$('#ai-image-provider').options].some(o=>o.value==='claude'));
});
await test('Gemini PNG vira camada JPEG e a peça mantém autoria Claude',async()=>{
 imageFails=false;$('#ai-image-consent').checked=true;$('#ai-slides [data-image]').click();await wait(()=>$('#ai-status').textContent.startsWith('Imagem adicionada'));assert(calls.filter(c=>c.url.endsWith('image')).at(-1).data.provider==='gemini');
 $('#ai-save').click();assert(created[1].ai.provider==='Claude');assert(created[1].slides[0].layers.some(l=>l.type==='image'&&l.src.startsWith('data:image/jpeg;base64,')));
 $('#ai-settings').click();$('#ai-key').value='sk-ant-falso';$('#ai-key-provider').value='gemini';$('#ai-key-provider').dispatchEvent(new Event('change'));assert($('#ai-key').value==='');$('#ai-config-close').click();
});
$('#results').textContent+='\n\n'+(results.every(r=>r.startsWith('PASS'))?'TODOS OS 8 TESTES PASSARAM':'HÁ FALHAS');
await test('Fonte de Short prepara briefing e preserva referência na peça',async()=>{
 $('#ai-close').click();document.dispatchEvent(new CustomEvent('studio:compose-source',{detail:{projectId:'qa-project',kind:'short',source:{id:'source-qa',title:'Fonte QA',url:'',start:null,end:null,text:'Uma ideia de referência.'}}}));await wait(()=>$('#ai-dialog').open);assert($('#ai-kind').value==='short');assert(!$('#ai-consent').checked);$('#ai-form').elements.count.value='1';$('#ai-consent').checked=true;$('#ai-form').requestSubmit();await wait(()=>!$('#ai-preview').hidden);assert($('#ai-caption-label').textContent.includes('Roteiro'));$('#ai-save').click();assert(created.at(-1).contentKind==='short');assert(created.at(-1).source.text==='Uma ideia de referência.');assert(calls.filter(c=>c.url.endsWith('content')).at(-1).data.source.start===null);
});
$('#results').textContent+='\n\n'+(results.every(r=>r.startsWith('PASS'))?'TODOS OS 9 TESTES PASSARAM':'HÁ FALHAS');

await test('Modelo e logo ficam locais; briefing usa formato final do modelo',async()=>{
 projects[0].brandKit={...defaultBrand('Marca QA'),logo:{src:fixturePNG,width:16,height:16}};models.push(saveTemplate(created[0],'Layout QA'));$('#generate-ai').click();$('#ai-template').value=models[0].id;$('#ai-template').dispatchEvent(new Event('change'));$('#ai-form').elements.format.value='story';$('#ai-consent').checked=true;$('#ai-form').requestSubmit();await wait(()=>!$('#ai-preview').hidden);const sent=calls.filter(c=>c.url.endsWith('content')).at(-1).data;assert(!sent.brandKit&&!sent.template);assert(!JSON.stringify(sent).includes('data:image'));assert(sent.format===models[0].snapshot.format);$('#ai-save').click();assert(created.at(-1).slides[0].layers.some(l=>l.role==='brandLogo'));assert(created.at(-1).format===models[0].snapshot.format);
});
$('#results').textContent+='\n\n'+(results.every(r=>r.startsWith('PASS'))?'TODOS OS 10 TESTES PASSARAM':'HÁ FALHAS');
