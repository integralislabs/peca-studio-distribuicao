import test from 'node:test';
import assert from 'node:assert/strict';
import {defaultBrand,validateBrandKit,applyBrand} from '../brand.js';
import {newPiece,validateState} from '../model.js';
const project={id:'project',name:'Marca',color:'#123456',folders:[]};
test('old libraries remain valid and brand kit survives backup',()=>{
 validateState({version:1,projects:[project],pieces:[]});
 const kit={...defaultBrand('Minha marca'),signature:'@minhamarca',tone:'Educativo'};
 assert.equal(validateState({version:1,projects:[{...project,brandKit:kit}],pieces:[]}).projects[0].brandKit.signature,'@minhamarca');
});
test('invalid colors fonts and external logos are rejected',()=>{
 for(const extra of [{bg:'red'},{titleFont:'unknown'},{logo:{src:'https://example.com/logo.png',width:1,height:1}},{signature:'x'.repeat(161)}])assert.throws(()=>validateBrandKit({...defaultBrand(),...extra}));
});
test('applying brand preserves original and text identity, is idempotent in layer count',()=>{
 const p=newPiece('project','Peça','feed',3),kit={...defaultBrand('Minha marca'),signature:'@minhamarca',bg:'#234567',titleFont:'Georgia'};
 const a=applyBrand(p,kit),b=applyBrand(a,kit);
 assert.equal(p.slides[0].bg,'#151020');assert.equal(a.slides[0].bg,'#234567');assert.equal(a.slides[0].layers[0].id,p.slides[0].layers[0].id);
 assert.equal(a.slides[0].layers[0].font,'Georgia');assert.equal(a.slides[0].layers.length,b.slides[0].layers.length);
 validateState({version:1,projects:[project],pieces:[b]});
});
test('brand scale 10x: 1000 applications preserve valid independent pieces',()=>{
 const p=newPiece('project','Peça','feed',10),start=performance.now();for(let i=0;i<1000;i++)applyBrand(p,defaultBrand('Marca'));
 console.log(`MEDIDA MARCA · 1000 aplicações / 10 slides: ${(performance.now()-start).toFixed(2)} ms`);
});
