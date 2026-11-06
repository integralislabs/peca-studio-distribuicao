import test from 'node:test';
import assert from 'node:assert/strict';
import {saveTemplate,useTemplate,fillTemplate} from '../templates.js';
import {newPiece,validateState} from '../model.js';
const project={id:'project',name:'Projeto',color:'#123456',folders:[]},p=newPiece('project','Meu layout','feed',3);
test('template snapshot is independent and can create in another project',()=>{
 const t=saveTemplate(p,'Modelo de abertura'),q=useTemplate(t,'other');
 q.slides[0].layers[0].text='Mudou';assert.notEqual(q.slides[0].id,p.slides[0].id);assert.notEqual(q.slides[0].layers[0].id,p.slides[0].layers[0].id);
 assert.equal(q.projectId,'other');assert.notEqual(t.snapshot.slides[0].layers[0].text,'Mudou');assert.equal(p.title,'Meu layout');
});
test('template backup validation independent from deleted source project',()=>{
 const t=saveTemplate(p,'Modelo');assert.equal(validateState({version:1,projects:[],pieces:[],templates:[t]}).templates.length,1);
 assert.throws(()=>validateState({version:1,projects:[project],pieces:[],templates:[{...t,snapshot:{}}]}));
 assert.throws(()=>validateState({version:1,projects:[project],pieces:[],templates:Array(201).fill(t)}));
});
test('AI template changes copy while retaining positions and creating missing body',()=>{
 const t=saveTemplate(p,'Modelo'),draft={title:'Nova peça',caption:'Legenda',slides:[{title:'Texto novo',body:'Explicação nova',imagePrompt:''}]};
 const q=fillTemplate(t,draft,'project');assert.equal(q.slides.length,1);assert.equal(q.slides[0].layers[0].x,p.slides[0].layers[0].x);assert.equal(q.slides[0].layers[0].text,'Texto novo');assert.ok(q.slides[0].layers.some(l=>l.text==='Explicação nova'));validateState({version:1,projects:[project],pieces:[q]});
});
test('template scale 10x: 100 independent templates',()=>{
 const start=performance.now(),items=Array.from({length:100},(_,i)=>saveTemplate(p,'Modelo '+i));assert.equal(new Set(items.map(t=>t.id)).size,100);console.log(`MEDIDA MODELOS · 100 snapshots: ${(performance.now()-start).toFixed(2)} ms`);
});
