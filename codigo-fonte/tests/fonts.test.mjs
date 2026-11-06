import test from 'node:test';
import assert from 'node:assert/strict';
import {validateFonts,readFont,fontNames} from '../fonts.js';
import {newPiece,validateState} from '../model.js';
test('fonts reject untrusted names, signatures and oversize',async()=>{
 await assert.rejects(readFont(new File(['evil'],'bad.ttf')));
 assert.throws(()=>validateFonts([{name:'evil";url(x)',data:'data:font/ttf;base64,AAEAAA=='}]));
 assert.throws(()=>validateFonts(Array.from({length:33},()=>({}))));
});
test('font data is portable and validated even when font unused',()=>{
 const font={name:'Local Demo',data:'data:font/ttf;base64,AAEAAAAAAAAAAAAAAAAAAAAAAAA='};
 assert.equal(validateFonts([font])[0].name,'Local Demo');assert.ok(fontNames([font]).includes('Local Demo'));
 const p=newPiece('p','Test');p.fonts=[font];p.slides[0].layers[0].font=font.name;
 assert.equal(validateState({version:1,projects:[{id:'p',name:'P',color:'#ffffff',folders:[]}],pieces:[p]}).pieces[0].fonts[0].name,font.name);
 p.fonts[0].data='https://evil';assert.throws(()=>validateState({version:1,projects:[],pieces:[],fonts:p.fonts}));
});
test('font pieces retain embedded font bytes across package export/import',async()=>{
 const {exportPackage,importPackage}=await import('../packages.js');const p=newPiece('p','Font');p.fonts=[{name:'Local Demo',data:'data:font/ttf;base64,AAEAAAAAAAAAAAAAAAAAAAAAAAA='}];p.slides[0].layers[0].font='Local Demo';
 const entries=await exportPackage(p);const html=new TextDecoder().decode(entries.find(f=>f.name==='index.html').bytes);assert.match(html,/@font-face/);
 const {piece}=await importPackage(new Map(entries.map(f=>[f.name,new File([f.bytes],f.name)])),'new');assert.deepEqual(piece.fonts,p.fonts);
});
test('font families reserve basic names and Unicode/case aliases cannot collide',async()=>{
 const data='data:font/ttf;base64,AAEAAAAAAAAAAAAAAAAAAAAAAAA=';
 for(const name of ['arial','ARIAL','Ａｒｉａｌ'])assert.throws(()=>validateFonts([{name,data}]));
 for(const names of [['Demo','demo'],['Café','CAFÉ'],['Demo','Ｄｅｍｏ']])assert.throws(()=>validateFonts(names.map(name=>({name,data}))));
 await assert.rejects(readFont(new File([Uint8Array.of(0,1,0,0,...Array(16).fill(0))],'ARIAL.ttf')));
});
