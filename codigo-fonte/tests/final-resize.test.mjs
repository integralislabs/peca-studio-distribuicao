import {test} from 'node:test';
import assert from 'node:assert/strict';
import {newPiece,textLayer,imageLayer} from '../model.js';
import {resizePiece} from '../resize.js';
test('resize rejects every invalid resulting field without touching original',()=>{
 for(const [type,key,value,w] of [['text','letterSpacing',60,2160],['text','w',1,540],['image','h',1,540],['image','radius',4096,2160]]){
 const p=newPiece('p','Resize','quadrado');p.slides[0].layers=[type==='text'?textLayer('X',{size:32}):imageLayer('data:image/png;base64,AAAA')];p.slides[0].layers[0][key]=value;const before=structuredClone(p);assert.throws(()=>resizePiece(p,w,w),key);assert.deepEqual(p,before);
 }
});
