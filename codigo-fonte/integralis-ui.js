export async function ensureIntegralisAccess(){
 const response=await fetch('/api/local/integralis/authorize',{method:'POST',headers:{'Content-Type':'application/json','X-Peca-Request':'1'},body:'{}'}),state=await response.json();
 if(!response.ok||!state.allowed)throw Error(state.error||'Entre com sua conta Integralis para usar o produto.');return state;
}
// Browser receives only sanitized account status and the one-time authorization URL.
export function accountLabel(status) {
 if(status.mode==='development')return 'Modo de desenvolvimento local';
 if(!status.configured)return 'Integralis: configuração comercial pendente';
 return status.allowed?'Integralis: acesso confirmado':'Integralis: acesso não confirmado';
}

export function initIntegralisUI({container,openExternal= url=>window.open(url,'_blank','noopener,noreferrer')}={}) {
 if(!container)return;
 const panel=document.createElement('section');panel.setAttribute('aria-label','Conta Integralis');
 const label=document.createElement('strong'),message=document.createElement('p'),login=document.createElement('button'),logout=document.createElement('button');
 login.type=logout.type='button';login.textContent='Entrar com Integralis';logout.textContent='Sair da Integralis';
 const plan=document.createElement('a');plan.href='https://integralislabs.com/marketplace/peca-studio';plan.target='_blank';plan.rel='noopener noreferrer';plan.textContent='Ver plano e assinar';
 panel.append(label,message,login,logout,plan);container.append(panel);
 let stopped=false,timer;
 async function request(action,method='GET') {
  const response=await fetch('/api/local/integralis/'+action,{method,headers:{'X-Peca-Request':'1','Content-Type':'application/json'},...(method==='POST'?{body:'{}'}:{})});
  const result=await response.json();if(!response.ok)throw new Error(result.error||result.message||'Não foi possível consultar a Integralis.');return result;
 }
 function render(status){label.textContent=accountLabel(status);message.textContent=status.message||'';login.disabled=!status.configured||status.mode==='development';logout.disabled=!status.signedIn;plan.hidden=status.mode==='development'||Boolean(status.allowed);panel.dataset.mode=status.mode;panel.dataset.allowed=String(status.allowed);}
 async function refresh(heartbeat=false){
  try {const status=await request(heartbeat?'heartbeat':'status',heartbeat?'POST':'GET');render(status);if(!stopped)timer=setTimeout(()=>refresh(Boolean(status.signedIn)),Math.max(5,Math.min(60,status.heartbeatSeconds||30))*1000);}
  catch(error){message.textContent=error.message;label.textContent='Integralis: acesso não confirmado';if(!stopped)timer=setTimeout(()=>refresh(),30000);}
 }
 login.addEventListener('click',async()=>{login.disabled=true;try{const result=await request('login','POST');const url=new URL(result.url);if(url.protocol!=='https:')throw new Error('Endereço de login inválido.');openExternal(result.url);message.textContent='Conclua a entrada no navegador. O acesso será atualizado aqui.';}catch(error){message.textContent=error.message;}finally{login.disabled=false;}});
 logout.addEventListener('click',async()=>{try{render(await request('logout','POST'));}catch(error){message.textContent=error.message;}});
 refresh();
 return ()=>{stopped=true;clearTimeout(timer);panel.remove();};
}
