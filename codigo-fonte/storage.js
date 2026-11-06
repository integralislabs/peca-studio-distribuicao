let database,revision=0;
let disk={active:false};
export const storageStatus=()=>({...disk});
export async function workspaceRequest(body=null){
 const response=await fetch('/api/local/workspace',{method:body?'POST':'GET',headers:{'X-Peca-Request':'1',...(body?{'Content-Type':'application/json'}:{})},...(body?{body:JSON.stringify(body)}:{})});
 const value=await response.json();if(!response.ok)throw Error(value.error||'Não foi possível acessar a pasta do acervo.');return value;
}
export async function activateWorkspace(snapshot){
 if(snapshot.active!==true||!Number.isInteger(snapshot.revision))throw Error('Resposta do acervo inválida.');disk={active:true,path:snapshot.path,revision:snapshot.revision};return snapshot.data;
}
export function disconnectWorkspace(){disk={active:false};}
export async function externalWorkspace(){return workspaceRequest();}
export async function workspaceVersion(){const r=await fetch('/api/local/workspace-status',{headers:{'X-Peca-Request':'1'}}),s=await r.json();if(!r.ok)throw Error(s.error||'Não foi possível conferir a revisão do acervo.');return s;}
export async function openStore(name='peca-studio'){
  if(!('indexedDB' in window))throw new Error('Este navegador não oferece armazenamento local. Abra no Chrome ou Edge.');
  database=await new Promise((resolve,reject)=>{const request=indexedDB.open(name,1);request.onupgradeneeded=()=>request.result.createObjectStore('library');request.onsuccess=()=>resolve(request.result);request.onerror=()=>reject(request.error);request.onblocked=()=>reject(new Error('Feche outra aba do Peça Studio e tente novamente.'));});
  database.onversionchange=()=>database.close();
  const local=await new Promise((resolve,reject)=>{const request=database.transaction('library').objectStore('library').get('state');request.onsuccess=()=>{revision=request.result?.revision||0;resolve(request.result?.data||null);};request.onerror=()=>reject(request.error);});
  const snapshot=await workspaceRequest();if(snapshot.active)return activateWorkspace(snapshot);disconnectWorkspace();return local;
}
export function closeStore(){database?.close();}
export function writeStore(data){
  if(disk.active)return workspaceRequest({action:'write',data,expectedRevision:disk.revision,expectedPath:disk.path}).then(result=>{disk.revision=result.revision;});
  return new Promise((resolve,reject)=>{
    const tx=database.transaction('library','readwrite'),store=tx.objectStore('library');let reason;
    const request=store.get('state');request.onsuccess=()=>{
      if((request.result?.revision||0)!==revision){reason=new Error('A biblioteca mudou em outra aba. Baixe um backup desta sessão antes de recarregar.');tx.abort();return;}
      store.put({revision:revision+1,data},'state');
    };
    tx.oncomplete=()=>{revision++;resolve();};tx.onabort=()=>reject(reason||new Error('Não foi possível salvar. Confira o espaço do navegador e baixe um backup.'));tx.onerror=()=>{};
  });
}
