import test from 'node:test';
import assert from 'node:assert/strict';
import {newPiece,textLayer,imageLayer} from '../model.js';

const style={bg:'#123456',text:'#eeeeee',accent:'#ff9900',titleFont:'Georgia',bodyFont:'Verdana'};
test('applies style to a selected slide without mutating image, identities or other slides',async()=>{
 const {applyStyle}=await import('../studio-style.js');
 const p=newPiece('project','Teste','feed',2);
 p.slides[0].layers.push(imageLayer({src:'data:image/png;base64,AAAA',width:1,height:1}));
 const before=structuredClone(p),next=applyStyle(p,style,{slideIndex:0});
 assert.deepEqual(p,before);assert.equal(next.id,p.id);assert.equal(next.slides[0].bg,style.bg);
 assert.equal(next.slides[0].layers[0].font,'Georgia');
 assert.deepEqual(next.slides[0].layers[1],before.slides[0].layers[1]);
 assert.deepEqual(next.slides[1],before.slides[1]);
});
test('fits with final fonts and width, applies body/accent and rejects invalid scope or style',async()=>{
 const {applyStyle}=await import('../studio-style.js');const p=newPiece('project','Teste');
 p.slides[0].layers=[textLayer('Título',{role:'title',w:180,size:50,y:100}),textLayer('Detalhe longo',{name:'Destaque',role:'body',w:180,size:30,y:600})];
 const measured=[];const measure=(text,font,size)=>{measured.push(font);return text.length*size*(font==='Arial'?.4:1);};
 const next=applyStyle(p,style,{measure});
 assert.ok(next.slides[0].layers[0].size<50);assert.equal(next.slides[0].layers[1].color,style.accent);
 assert.equal(next.slides[0].layers[1].font,'Verdana');assert.ok(measured.includes('Georgia'));
 assert.throws(()=>applyStyle(p,{...style,titleFont:'unknown'}),/estilo/i);
 assert.throws(()=>applyStyle(p,{...style,bg:'url(x)'}),/estilo/i);
 assert.throws(()=>applyStyle(p,style,{slideIndex:8}),/slide/i);
});
test('reference contains readable composition and source, but no base64 or unknown secret fields',async()=>{
 const {referenceText,referenceJSON}=await import('../reference.js');const p=newPiece('project','Teste');
 p.apiKey='secret';p.caption='Legenda';p.parentPieceId='parent';p.variationGroupId='family';p.versionLabel='V2';
 p.source={id:'src',title:'Vídeo',url:'https://www.youtube.com/watch?v=abcdefghijk',start:1,end:8,text:'Trecho fonte'};
 p.slides[0].bgImage='data:image/png;base64,AAAA';
 p.slides[0].layers.push(imageLayer({src:'data:image/png;base64,AAAA',width:1,height:1}));
 const project={id:'project',name:'Projeto',brandKit:{logo:{src:'SECRET'}}};
 const text=referenceText(p,project),json=referenceJSON(p,project);
 for(const value of [text,json]){assert.match(value,/Teste/);assert.match(value,/Legenda/);assert.match(value,/Trecho fonte/);assert.doesNotMatch(value,/base64|apiKey|SECRET|secret/);}
 assert.match(text,/Slide 1/);assert.match(text,/1080/);assert.match(text,/Família: family/);assert.equal(JSON.parse(json).piece.variationGroupId,'family');assert.equal(JSON.parse(json).piece.parentPieceId,'parent');
});
test('reference tolerates optional context and rejects oversized input without truncating silently',async()=>{
 const {referenceText,referenceJSON}=await import('../reference.js');const p=newPiece('project','Teste');
 assert.match(referenceText(p),/Teste/);assert.doesNotThrow(()=>JSON.parse(referenceJSON(p)));
 p.caption='x'.repeat(200001);assert.throws(()=>referenceText(p),/limite/i);
});
test('all slides receive style atomically and an impossible narrow text fails without mutation',async()=>{
 const {applyStyle}=await import('../studio-style.js');const p=newPiece('project','Teste','feed',2);
 const next=applyStyle(p,style);assert.ok(next.slides.every(s=>s.bg===style.bg));
 p.slides[1].layers[0].w=1;const before=structuredClone(p);
 assert.throws(()=>applyStyle(p,style),/não cabe/i);assert.deepEqual(p,before);
});
test('reference describes rendered circular radius and opacity',async()=>{
 const {referenceText}=await import('../reference.js');const p=newPiece('project','Imagem');
 p.slides[0].layers=[{...imageLayer({src:'data:image/png;base64,AAAA',width:1,height:1}),w:200,h:200,radius:100,opacity:.4}];
 const text=referenceText(p);assert.match(text,/máscara=circular/);assert.match(text,/opacidade=0.4/);
});
