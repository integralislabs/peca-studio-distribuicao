import {uid} from './model.js';
import {youtubeURL,checkCues,checkReference} from './studio-contracts.js';
const clean=text=>text.replace(/<[^>]*>/g,'').replace(/&nbsp;/g,' ').replace(/&amp;/g,'&').replace(/&lt;/g,'<').replace(/&gt;/g,'>').replace(/&quot;/g,'"').replace(/&#39;/g,"'").trim();
export function timeSeconds(value){
 if(typeof value==='number')return value;if(typeof value!=='string')return NaN;const p=value.trim().replace(',','.').split(':');if(!p.length||p.length>3||p.some(x=>!/^\d+(?:\.\d+)?$/.test(x)))return NaN;
 if(p.length>1&&Number(p.at(-1))>=60)return NaN;if(p.length===3&&Number(p[1])>=60)return NaN;return p.reduce((n,v)=>n*60+Number(v),0);
}
export function formatTime(seconds){if(seconds===null)return 'sem tempo';const ms=Math.round(seconds*1000),n=Math.floor(ms/1000),h=Math.floor(n/3600),fraction=ms%1000;return (h?h+':':'')+String(Math.floor(n/60)%60).padStart(2,'0')+':'+String(n%60).padStart(2,'0')+(fraction?'.'+String(fraction).padStart(3,'0').replace(/0+$/,''):'');}
export function parseTranscript(input){
 if(typeof input!=='string'||input.length>1_000_000)throw new Error('Arquivo de transcrição limitado a 1 milhão de caracteres.');const text=input.replace(/^\uFEFF/,'').replace(/\r/g,''),lines=text.split('\n'),cues=[];
 if(text.includes('-->')){
  for(let i=0;i<lines.length;i++){const m=lines[i].match(/^\s*((?:\d+:)?\d{2}:\d{2}[.,]\d{1,3})\s*-->\s*((?:\d+:)?\d{2}:\d{2}[.,]\d{1,3})/);if(!m)continue;const start=timeSeconds(m[1]),end=timeSeconds(m[2]),parts=[];while(i+1<lines.length&&lines[i+1].trim()&&!lines[i+1].includes('-->'))parts.push(lines[++i]);const value=clean(parts.join('\n'));if(!value)continue;const last=cues.at(-1);if(last?.text===value&&start<=last.end){last.end=Math.max(last.end,end);continue;}cues.push({start,end,text:value});}
 }else{
  const timed=[];for(const line of lines){const m=line.match(/^\s*((?:\d+:)?\d{1,2}:\d{2})\s+(.+)$/);if(m)timed.push({start:timeSeconds(m[1]),text:clean(m[2])});}
  if(timed.length&&lines.filter(l=>l.trim()).length===timed.length)timed.forEach((c,i)=>cues.push({...c,end:timed[i+1]?.start??c.start}));
  else{const value=clean(text);if(!value||value==='WEBVTT')throw new Error('Nenhum texto de transcrição encontrado.');for(let i=0;i<value.length;i+=3000)cues.push({start:null,end:null,text:value.slice(i,i+3000)});}
 }checkCues(cues);return cues;
}
export function makeSource({id=uid(),projectId,title,url='',transcript,cues}){if(typeof title!=='string'||!title.trim()||title.length>180)throw new Error('Informe um título de até 180 caracteres.');return {id,projectId,title:title.trim(),url:youtubeURL(url),cues:checkCues(cues||parseTranscript(transcript)),updatedAt:new Date().toISOString()};}
export function selectExcerpt(source,start=null,end=null,workText=null){
 let cues=checkCues(source.cues),timed=cues[0].start!==null;
 if(timed){start=start??cues[0].start;end=end??cues.at(-1).end;if(!Number.isFinite(start)||!Number.isFinite(end)||start<0||end<start||end>86400)throw new Error('Intervalo de tempo inválido.');cues=cues.filter(c=>c.start===c.end?c.start>=start&&c.start<=end:c.start<end&&c.end>start);if(!cues.length)throw new Error('Nenhum trecho nesse intervalo.');}
 const value=workText===null?cues.map(c=>c.text).join('\n'):workText;if(typeof value!=='string'||value.length>10000)throw new Error('Selecione um trecho menor: o envio à IA aceita até 10 mil caracteres.');
 return checkReference({id:source.id,title:source.title,url:source.url,start:timed?cues[0].start:null,end:timed?Math.max(...cues.map(c=>c.end)):null,text:value});
}
export const sourceLink=source=>source.url?(source.url+(source.start===null?'':'&t='+Math.floor(source.start)+'s')):'';
export function transcriptText(cues){return cues.map(c=>c.start===null?c.text:`${String(Math.floor(c.start/3600)).padStart(2,'0')}:${String(Math.floor(c.start/60)%60).padStart(2,'0')}:${(c.start%60).toFixed(3).padStart(6,'0')} --> ${String(Math.floor(c.end/3600)).padStart(2,'0')}:${String(Math.floor(c.end/60)%60).padStart(2,'0')}:${(c.end%60).toFixed(3).padStart(6,'0')}\n${c.text}`).join('\n\n');}
