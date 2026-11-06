import test from 'node:test';
import assert from 'node:assert/strict';
import { validateState, duplicatePiece, filterPieces, newPiece, wrapText, makeZip, imageLayer, assertHTMLSize, MAX_HTML_BYTES, assertBackupSize } from '../model.js';

const state = () => ({version:1,projects:[{id:'p1',name:'Marca',color:'#9b75ff',folders:[]}],pieces:[newPiece('p1','Teste','feed',2)]});
test('extreme image aspect ratios never create zero-height layers or invalid backups',()=>{
  const s=state(),src='data:image/png;base64,aA==';
  const layer=imageLayer({src,width:2200,height:1},{w:756,maxHeight:945});
  assert.equal(layer.h,1);s.pieces[0].slides[0].layers.push(layer);assert.doesNotThrow(()=>validateState(s));
});
test('HTML accepts files above the previous 12MB ceiling and rejects files above the shared export limit',()=>{
  assert.doesNotThrow(()=>assertHTMLSize(15*1024*1024));assert.doesNotThrow(()=>assertHTMLSize(MAX_HTML_BYTES));
  assert.throws(()=>assertHTMLSize(MAX_HTML_BYTES+1),/100 MB/);
});
test('backup export and restore share the same 100MB boundary',()=>{
  assert.doesNotThrow(()=>assertBackupSize(100_000_000));
  assert.throws(()=>assertBackupSize(100_000_001),/100 MB/);
});
test('backup rejects invalid layers, foreign project and excessive dimensions', () => {
  assert.equal(validateState(state()).version,1);
  for (const mutate of [s=>s.pieces[0].projectId='missing',s=>s.pieces[0].slides[0].width=1e8,s=>s.pieces[0].slides[0].layers.push({id:'bad',type:'script'})]) {
    const s=state();mutate(s);assert.throws(()=>validateState(s));
  }
  assert.throws(()=>validateState({version:100}));
});
test('duplicate assigns independent IDs and deep copies slide and layer data', () => {
  const p=state().pieces[0], copy=duplicatePiece(p);
  assert.notEqual(copy.id,p.id);assert.notEqual(copy.slides[0].id,p.slides[0].id);
  assert.notEqual(copy.slides[0].layers[0].id,p.slides[0].layers[0].id);
  copy.slides[0].layers[0].text='Outro';assert.notEqual(p.slides[0].layers[0].text,'Outro');
});
test('copies of demo pieces are user work, and unsafe identifiers are rejected', () => {
  const p=state().pieces[0];p.demo=true;assert.equal(duplicatePiece(p).demo,false);
  const s=state();s.projects[0].id='bad" onclick="alert(1)';s.pieces[0].projectId=s.projects[0].id;
  assert.throws(()=>validateState(s));
});
test('filters combine project, folder, text, channel and format without mutating source', () => {
  const s=state();s.pieces[0].folderId='f1';s.pieces[0].title='Café especial';
  assert.equal(filterPieces(s.pieces,{project:'p1',folder:'f1',query:'cafe',channel:'Instagram',format:'feed'}).length,1);
  assert.equal(filterPieces(s.pieces,{project:'p2'}).length,0);
  assert.equal(s.pieces.length,1);
});
test('long text wraps and explicit blank lines survive', () => {
  const measure=t=>t.length*10;
  assert.deepEqual(wrapText('abc def',35,measure),['abc','def']);
  assert.deepEqual(wrapText('abc\n\ndef',100,measure),['abc','','def']);
  assert.ok(wrapText('abcdefghij',30,measure).every(t=>t.length<=3));
});
test('ZIP retains unicode filenames and complete bytes', async () => {
  const zip=makeZip([{name:'capa-ação.txt',bytes:new TextEncoder().encode('Olá!')}]);
  const bytes=new Uint8Array(await zip.arrayBuffer());
  assert.deepEqual([...bytes.slice(0,4)],[80,75,3,4]);
  assert.equal(new DataView(bytes.buffer).getUint16(12,true),33,'ZIP needs a valid DOS date: 1980-01-01');
  assert.ok(new TextDecoder().decode(bytes).includes('capa-ação.txt'));
  const {writeFile}=await import('node:fs/promises');await writeFile('tests/export-test.zip',bytes);
});
