import test from 'node:test';
import assert from 'node:assert/strict';
import {parseTranscript,makeSource,selectExcerpt,sourceLink,formatTime,timeSeconds} from '../sources.js';
import {validateState} from '../model.js';
const project={id:'project',name:'Projeto',color:'#123456',folders:[]};
const vtt='WEBVTT\n\n00:17:06.000 --> 00:17:10.000\n<c>Primeira ideia.</c>\n\n00:17:10.000 --> 00:17:18.000\nSegunda ideia &amp; exemplo.\n';
test('VTT and SRT retain exact time and normalize markup',()=>{
 const cues=parseTranscript(vtt);assert.equal(cues[0].start,1026);assert.equal(cues[1].text,'Segunda ideia & exemplo.');
 assert.equal(parseTranscript('1\n01:02:03,400 --> 01:02:04,500\nOlá.')[0].start,3723.4);
 for(const t of [0.125,59.999,60.001,3723.4])assert.equal(timeSeconds(formatTime(t)),t);
});
test('plain text has no invented timestamps; timed excerpt is bounded',()=>{
 const plain=makeSource({projectId:'project',title:'Texto',url:'',transcript:'Uma ideia sem tempo.'});assert.equal(selectExcerpt(plain).start,null);
 const source=makeSource({projectId:'project',title:'Vídeo',url:'https://youtu.be/3FEjcVt0VtM',transcript:vtt}),ref=selectExcerpt(source,1030,1038);
 assert.equal(ref.text,'Segunda ideia & exemplo.');assert.equal(ref.start,1030);assert.equal(ref.end,1038);assert.ok(sourceLink(ref).endsWith('&t=1030s'));
 validateState({version:1,projects:[project],pieces:[],sources:[source]});
});
test('reject bad URLs, empty content and excessive excerpts without truncating',()=>{
 assert.throws(()=>makeSource({projectId:'project',title:'X',url:'javascript:alert(1)',transcript:'Olá'}));
 assert.throws(()=>parseTranscript('WEBVTT\n\n'));assert.throws(()=>parseTranscript('x'.repeat(150001)));
 const source=makeSource({projectId:'project',title:'Longo',url:'',transcript:'x'.repeat(12000)});assert.throws(()=>selectExcerpt(source),/trecho menor/i);
});
test('backup rejects malformed sources and foreign projects',()=>{
 const s=makeSource({projectId:'project',title:'Fonte',url:'',transcript:vtt});
 assert.throws(()=>validateState({version:1,projects:[],pieces:[],sources:[s]}));
 assert.throws(()=>validateState({version:1,projects:[project],pieces:[],sources:[{...s,cues:[{start:4,end:3,text:'x'}]}]}));
});
test('10x transcript scale: 15000 lines / 5000 cues',()=>{
 const stamp=i=>`${String(Math.floor(i/3600)).padStart(2,'0')}:${String(Math.floor(i/60)%60).padStart(2,'0')}:${String(i%60).padStart(2,'0')}.000`;
 const value=Array.from({length:5000},(_,i)=>`${stamp(i)} --> ${stamp(i+1)}\nIdeia ${i}\n`).join('\n');
 const start=performance.now();const cues=parseTranscript(value,{maxInput:1_000_000});assert.equal(cues.length,5000);console.log(`MEDIDA FONTES · 15000 linhas: ${(performance.now()-start).toFixed(2)} ms`);
});
