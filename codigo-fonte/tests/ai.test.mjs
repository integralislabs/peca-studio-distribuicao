import test from 'node:test';
import assert from 'node:assert/strict';
import {validateAIDraft,buildAIPiece,fitCopy,validateAIFile} from '../ai.js';
import {validateState,wrapText} from '../model.js';
const brief={topic:'Plantas',audience:'Iniciantes',goal:'Ensinar',tone:'Didático',brand:'Botânica',style:'editorial',format:'feed',count:2,bg:'#171322',accent:'#b8e38b'};
const draft={title:'Plantas em casa',caption:'Salve para consultar.',slides:[{title:'Comece com luz',body:'Observe a janela.',imagePrompt:'Uma planta verde'},{title:'Sem excessos',body:'Confira a umidade.',imagePrompt:'Folhas verdes'}]};
const measure=(text,font,size)=>text.length*size*.6;
test('AI pieces contain editable independent layers, caption and valid state',()=>{
 const p=buildAIPiece({draft,brief,images:[]},'project1',measure),q=buildAIPiece({draft,brief,images:[]},'project1',measure);
 assert.notEqual(p.id,q.id);assert.equal(p.caption,draft.caption);assert.equal(p.slides.length,2);assert.ok(p.slides.every(s=>s.layers.every(l=>l.type==='text')));
 validateState({version:1,projects:[{id:'project1',name:'Projeto',color:'#aabbcc',folders:[]}],pieces:[p]});
 assert.notEqual(p.slides[0].layers[0].id,q.slides[0].layers[0].id);
});
test('long copy fits its box at every supported format',()=>{
 for(const font of ['Arial','Georgia','Impact']) {
  const size=fitCopy('Palavras compridas '.repeat(20),900,300,font,64,measure);
  assert.ok(wrapText('Palavras compridas '.repeat(20),900,t=>measure(t,font,size)).length*size*1.15<=300);
 }
});
test('draft validation rejects wrong slide count and excessive text',()=>{
 assert.throws(()=>validateAIDraft({...draft,slides:[]},2));
 assert.throws(()=>validateAIDraft({...draft,slides:[{...draft.slides[0],title:'x'.repeat(101)},draft.slides[1]]},2));
 assert.equal(validateAIDraft(draft,2).slides[0].title,draft.slides[0].title);
});
test('draft file rejects arbitrary images, bad styles and versions',()=>{
 for(const value of [{version:1,brief,draft,images:['https://example.com/a.jpg']},{version:1,brief:{...brief,style:'bad'},draft,images:[]},{version:2,brief,draft,images:[]}]) assert.throws(()=>validateAIFile(value));
 assert.equal(validateAIFile({version:1,brief,draft,images:[]}).draft.caption,draft.caption);
});
test('10x scale: build 100 carousels of 10 editable slides',()=>{
 const large={...draft,slides:Array.from({length:10},()=>({...draft.slides[0]}))};
 const start=performance.now();let slides=0;
 for(let i=0;i<100;i++)slides+=buildAIPiece({draft:large,brief:{...brief,count:10},images:[]},'project1',measure).slides.length;
 assert.equal(slides,1000);console.log(`MEDIDA IA · 100 carrosséis / ${slides} slides: ${(performance.now()-start).toFixed(2)} ms`);
});
test('provider survives draft and piece, old drafts default to OpenAI',()=>{
 assert.equal(validateAIFile({version:1,brief,draft,images:[]}).brief.provider,'openai');
 for(const provider of ['claude','gemini']){
  const file=validateAIFile({version:1,brief:{...brief,provider,imageProvider:'gemini'},draft,images:[]});
  assert.equal(file.brief.provider,provider);assert.equal(buildAIPiece(file,'project1',measure).ai.provider,provider==='claude'?'Claude':'Gemini');
 }
 assert.throws(()=>validateAIFile({version:1,brief:{...brief,provider:'evil'},draft,images:[]}));
 assert.throws(()=>validateAIFile({version:1,brief:{...brief,imageProvider:'claude'},draft,images:[]}));
});
import {defaultBrand} from '../brand.js';
import {saveTemplate} from '../templates.js';
test('source, model and final brand font survive composition without losing source or overflowing',()=>{
 const original=buildAIPiece({draft,brief,images:[]},'project1',measure),template=saveTemplate(original,'Modelo');
 const kit={...defaultBrand('Marca'),titleFont:'Courier New'},source={id:'source1',title:'Vídeo',url:'https://www.youtube.com/watch?v=3FEjcVt0VtM',start:1026.125,end:1085.5,text:'Uma ideia de referência.'};
 const wide=(text,font,size)=>text.length*size*(font==='Courier New'?.8:.2),long={...draft,slides:draft.slides.map(s=>({...s,title:'i'.repeat(100)}))};
 for(const model of [undefined,template]){
  const p=buildAIPiece({draft:long,brief:{...brief,kind:'short',brandKit:kit,source,...(model?{template:model}:{})},images:[]},'project1',wide);
  assert.equal(p.contentKind,'short');assert.deepEqual(p.source,source);assert.notEqual(p.source,source);
  for(const slide of p.slides){const title=slide.layers.find(l=>l.role==='title'||l.name==='Título'),body=slide.layers.find(l=>l.role==='body'||l.name==='Conteúdo');assert.equal(title.font,'Courier New');assert.ok(wrapText(title.text,title.w,t=>wide(t,title.font,title.size)).length*title.size*1.15<=body.y-title.y-32);}
  validateState({version:1,projects:[{id:'project1',name:'Projeto',color:'#aabbcc',folders:[]}],pieces:[p]});
 }
});
