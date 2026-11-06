import {openStore,closeStore} from '../storage.js';
const normalize=value=>Array.isArray(value)?value.map(normalize):value&&typeof value==='object'?Object.fromEntries(Object.keys(value).sort().map(key=>[key,normalize(value[key])])):value;
try{
  const state=await openStore();closeStore();
  if(!state)throw new Error('Esta origem ainda não tem uma biblioteca.');
  const bytes=new TextEncoder().encode(JSON.stringify(normalize(state)));
  const hash=[...new Uint8Array(await crypto.subtle.digest('SHA-256',bytes))].map(b=>b.toString(16).padStart(2,'0')).join('');
  document.querySelector('#result').textContent=JSON.stringify({projects:state.projects.length,pieces:state.pieces.length,slides:state.pieces.reduce((n,p)=>n+p.slides.length,0),sha256:hash},null,2);
}catch(error){document.querySelector('#result').textContent='FALHOU: '+error.message;}
