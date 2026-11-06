import test from 'node:test';
import assert from 'node:assert/strict';
import {compareForegroundMasks} from '../visual-qa.js';
import {evaluateQuality,validateQualityReceipt} from '../quality-policy.js';
const hashes={slideHash:'s',referenceHash:'r',blocksHash:'b',reportHash:'p'};
const input=()=>({hashes,blocks:[{id:'a',text:'Preço'}],slide:{layers:[{type:'text',text:'Preço'}]},warnings:[],metrics:{regions:[{id:'a',foregroundIoU:.85,pixelsWithin20:.9}]}});
test('foreground overlap measures shifted ink even when background matches',()=>{
 const a=new Uint8ClampedArray(5*5*4).fill(255),b=new Uint8ClampedArray(a);a.set([0,0,0,255],24);b.set([0,0,0,255],28);
 assert.equal(compareForegroundMasks(a,b,5,5).foregroundIoU,0);
});
test('all regions must pass independently and global cannot hide failures',()=>{const i=input();i.metrics.global={foregroundIoU:1,pixelsWithin20:1};i.metrics.regions[0].foregroundIoU=.84;assert.equal(evaluateQuality(i).allowed,false);i.metrics.regions[0].foregroundIoU=.85;assert.equal(evaluateQuality(i).strictPass,true);});
test('missing text and warnings fail with individually bound exceptions',()=>{const i=input();i.slide.layers=[];i.warnings=['fonte'];let r=evaluateQuality(i);assert.equal(r.allowed,false);assert.deepEqual(r.failures.map(x=>x.id),['a','$global']);i.exceptions=r.failures.map(x=>({id:x.id,reason:'Alteração editorial intencional',...hashes}));r=evaluateQuality(i);assert.equal(r.allowed,true);assert.equal(r.strictPass,false);i.exceptions[0].referenceHash='other';assert.equal(evaluateQuality(i).allowed,false);});
test('receipt rejects old manual approvals and changed artifacts or metrics',()=>{const i=input();assert.equal(validateQualityReceipt({status:'reviewed',...hashes},hashes,i),false);const decision=evaluateQuality(i);const qa={schemaVersion:2,status:decision.status,...hashes,metrics:i.metrics,exceptions:[],reviewedAt:new Date().toISOString()};assert.equal(validateQualityReceipt(qa,hashes,i),true);assert.equal(validateQualityReceipt(qa,{...hashes,slideHash:'edited'},i),false);qa.metrics.regions=[];assert.equal(validateQualityReceipt(qa,hashes,i),false);});
test('missing measurements cannot be waived as intentional edit',()=>{const i=input();i.metrics=null;i.exceptions=[{id:'a',reason:'Alteração editorial intencional',...hashes}];assert.equal(evaluateQuality(i).allowed,false);});
test('empty foreground masks are not evidence of overlap',()=>{const a=new Uint8ClampedArray(16).fill(255);assert.equal(compareForegroundMasks(a,a,2,2).foregroundIoU,0);});
