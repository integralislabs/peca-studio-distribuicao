import test from 'node:test';
import assert from 'node:assert/strict';
import {newPiece} from '../model.js';
import {importPackage,exportPackage} from '../packages.js';
import {packageFingerprint,readDirectoryPackage} from '../directory.js';
const files=entries=>new Map(entries.map(({name,bytes})=>[name,new File([bytes],name)]));
test('own package roundtrips editable content, metadata and raster assets',async()=>{
 const p=newPiece('old','Pacote','story',2);p.caption='Legenda';p.source={kind:'manual',text:'Referência'};
 delete p.source; p.brand={label:'Marca'};
 p.slides[0].layers.push({id:'image1',type:'image',name:'Foto',src:'data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+aHnQAAAAASUVORK5CYII=',x:10,y:20,w:200,h:200,zoom:1,offsetX:0,offsetY:0,flip:false,visible:true,radius:100});
 const entries=await exportPackage(p); assert.ok(entries.some(f=>f.name.startsWith('assets/')));
 const {piece,warnings}=await importPackage(files(entries),'new');
 assert.equal(piece.projectId,'new');assert.notEqual(piece.id,p.id);assert.equal(piece.format,'story');assert.equal(piece.caption,p.caption);assert.deepEqual(piece.brand,p.brand);
 assert.equal(piece.slides[0].layers[1].src,p.slides[0].layers[1].src);assert.equal(piece.slides[0].layers[1].radius,100); assert.equal(warnings.length,0);
});
test('rejects traversal, external paths, SVG, excessive files and bytes',async()=>{
 for(const path of ['../index.html','a/../../index.html','https://bad/x','C:/x.html','a\\..\\index.html','x.svg']) await assert.rejects(importPackage(new Map([[path,new File(['x'],'x')]]),'p'));
 await assert.rejects(importPackage(Array.from({length:101},(_,i)=>new File(['x'],`${i}.txt`)),'p'),/100/);
 await assert.rejects(importPackage(new Map([['index.html',{size:101*1024*1024}]]),'p'),/100/);
});
test('rejects corrupted manifest numbers and missing package assets',async()=>{
 const p=newPiece('p','x');const entries=await exportPackage(p);const map=files(entries);
 const manifest=JSON.parse(await map.get('peca-studio.json').text());manifest.piece.slides[0].width=Infinity;
 map.set('peca-studio.json',new File([JSON.stringify(manifest)],'peca-studio.json'));await assert.rejects(importPackage(map,'p'));
 p.slides[0].bgImage='data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+aHnQAAAAASUVORK5CYII=';const noAsset=files(await exportPackage(p));for(const key of noAsset.keys())if(key.startsWith('assets/'))noAsset.delete(key);await assert.rejects(importPackage(noAsset,'p'),/ausente/);
});
test('directory fingerprint detects equal-size byte changes and nested files',async()=>{
 let data='abc';const handle={kind:'directory',async *entries(){yield ['index.html',{kind:'file',getFile:async()=>new File([data],'index.html',{lastModified:1})}];}};
 const a=await packageFingerprint(handle);data='abd';assert.notEqual(await packageFingerprint(handle),a);assert.equal((await readDirectoryPackage(handle)).size,1);
});

test('preserves source provenance and rejects nonfinite geometry before export',async()=>{
 const p=newPiece('p','<script>title</script>');p.source={id:'source1',title:'Origem',url:'',start:null,end:null,text:'Texto original'};p.brandKit={name:'Identidade'};
 const entries=await exportPackage(p);const html=new TextDecoder().decode(entries.find(f=>f.name==='index.html').bytes);assert.ok(!html.includes('<script>title'));
 const r=await importPackage(files(entries),'dest');assert.deepEqual(r.piece.source,p.source);assert.deepEqual(r.piece.brandKit,p.brandKit);
 p.slides[0].layers[0].x=NaN;await assert.rejects(exportPackage(p));
});
test('directory permission errors propagate without a false success fingerprint',async()=>{
 const denied={async *entries(){throw new DOMException('Permissão revogada','NotAllowedError');}};await assert.rejects(packageFingerprint(denied),{name:'NotAllowedError'});
});
test('duplicate paths and malformed project ids are rejected',async()=>{
 await assert.rejects(importPackage([new File(['x'],'index.html'),new File(['y'],'index.html')],'p'),/duplicado/);
 await assert.rejects(importPackage([new File(['x'],'index.html')],'../bad'),/Projeto/);
});

test('package files support directory selection with a single common root',async()=>{
 const p=newPiece('p','Diretório');const entries=await exportPackage(p);const selected=entries.map(e=>{const f=new File([e.bytes],e.name);Object.defineProperty(f,'webkitRelativePath',{value:'meu-pacote/'+e.name});return f;});assert.equal((await importPackage(selected,'p')).piece.title,'Diretório');
});

test('local asset references allow a standard leading dot slash',async()=>{
 const p=newPiece('p','Refs');p.slides[0].bgImage='data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+aHnQAAAAASUVORK5CYII=';const map=files(await exportPackage(p));const manifest=JSON.parse(await map.get('peca-studio.json').text());manifest.piece.slides[0].bgImage='./'+manifest.piece.slides[0].bgImage;map.set('peca-studio.json',new File([JSON.stringify(manifest)],'peca-studio.json'));assert.equal((await importPackage(map,'p')).piece.slides[0].bgImage,p.slides[0].bgImage);
});

test('independent package import clears all variation links',async()=>{const p=newPiece('p','Var');p.parentPieceId='old';p.variationGroupId='group';p.versionLabel='V2';const r=await importPackage(files(await exportPackage(p)),'p');for(const k of ['parentPieceId','variationGroupId','versionLabel'])assert.equal(r.piece[k],undefined);});
test('exported HTML preserves layer opacity',async()=>{const p=newPiece('p','Alpha');p.slides[0].layers[0].opacity=.25;const out=await exportPackage(p);assert.match(new TextDecoder().decode(out[0].bytes),/opacity:0.25/);});
test('raster imports reject bytes without a raster magic header',async()=>{const p=newPiece('p','Raster');p.slides[0].bgImage='data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+aHnQAAAAASUVORK5CYII=';const out=files(await exportPackage(p));out.set('assets/image-1.png',new File(['not png'],'image.png'));await assert.rejects(importPackage(out,'p'),/imagem|raster/i);});
test('directory walk bounds depth and empty entry counts',async()=>{
 const nested=n=>({kind:'directory',async *entries(){if(n)yield ['folder',nested(n-1)];else yield ['index.html',{kind:'file',getFile:async()=>new File(['x'],'index.html')}];}});
 await assert.rejects(readDirectoryPackage(nested(18)),/profundidade|16/);
 const many={async *entries(){for(let i=0;i<501;i++)yield ['f'+i,{kind:'directory',async *entries(){}}];}};await assert.rejects(readDirectoryPackage(many),/500|entradas/);
});


test('empty directory can be linked and fingerprinted but cannot be imported',async()=>{
 const empty={async *entries(){}};assert.equal((await readDirectoryPackage(empty)).size,0);assert.equal(await packageFingerprint(empty),'');await assert.rejects(importPackage(new Map(),'p'),/1 a 100/);
});
test('directory writes assets before manifest and index last regardless of input order',async()=>{
 const {saveDirectoryPackage}=await import('../directory.js');const order=[],empty={async *entries(){}};
 const dir=(prefix='')=>({...empty,getDirectoryHandle:async name=>dir(prefix+name+'/'),getFileHandle:async name=>({createWritable:async()=>({write:async()=>order.push(prefix+name),close:async()=>{},abort:async()=>{}})})});
 const entries=['index.html','peca-studio.json','assets/a.png','assets/b.png'].map(name=>({name,bytes:new Uint8Array([1])}));await saveDirectoryPackage(dir(),entries);assert.deepEqual(order,['assets/a.png','assets/b.png','peca-studio.json','index.html']);assert.equal(entries[0].name,'index.html');
});
test('failed directory write aborts current stream and preserves the original error',async()=>{
 const {saveDirectoryPackage}=await import('../directory.js');const error=new Error('Gravação interrompida'),written=[];let aborted=0;
 const handle={getFileHandle:async name=>({createWritable:async()=>({write:async()=>{written.push(name);throw error;},close:async()=>{},abort:async()=>{aborted++;throw new Error('Abort também falhou');}})})};
 await assert.rejects(saveDirectoryPackage(handle,[{name:'index.html',bytes:new Uint8Array([1])},{name:'peca-studio.json',bytes:new Uint8Array([2])}]),e=>e===error);assert.equal(aborted,1);assert.deepEqual(written,['peca-studio.json']);
});
