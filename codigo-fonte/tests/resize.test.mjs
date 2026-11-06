import {test} from 'node:test';
import assert from 'node:assert/strict';
import {newPiece,textLayer,validateState} from '../model.js';
const module=await import('../resize.js').catch(()=>null);
test('proportional resize preserves original, scales layers and offsets within a valid piece',()=>{
 assert.ok(module,'resize module missing');const p=newPiece('project','Resize','quadrado');p.slides[0].layers=[textLayer('Preço R$ 29',{x:100,y:200,w:600,size:60})];
 const next=module.resizePiece(p,1080,1920,{mode:'contain'});assert.equal(p.slides[0].height,1080);assert.equal(next.slides[0].height,1920);assert.equal(next.slides[0].layers[0].x,100);assert.equal(next.slides[0].layers[0].y,620);
 validateState({version:1,projects:[{id:'project',name:'P',color:'#123456',folders:[]}],pieces:[next]});
});
test('resize rejects nonfinite geometry and dimensions outside bounds before mutation',()=>{
 assert.ok(module);for(const size of [0,99,4097,Infinity,NaN])assert.throws(()=>module.resizePiece(newPiece('project','X'),size,1080));
});
test('resize supports each slide with independent source dimensions and keeps stable IDs',()=>{
 assert.ok(module);const p=newPiece('project','Many','feed',30),n=module.resizePiece(p,540,675,{mode:'scale'});assert.equal(n.slides.length,30);assert.equal(n.id,p.id);assert.equal(n.slides[20].layers[0].size,32);assert.equal(n.slides[20].id,p.slides[20].id);
});
