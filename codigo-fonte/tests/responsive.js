const frame=document.querySelector('#app');
function measure(){
  const doc=frame.contentDocument;if(!doc?.body)return;
  const root=doc.documentElement,w=root.clientWidth;
  const visible=el=>!!el&&el.getBoundingClientRect().width>0&&el.getBoundingClientRect().height>0;
  const results=[['Sem transbordamento horizontal da página',root.scrollWidth<=w+1],['Fontes acessíveis',visible(doc.querySelector('#fonts-button'))],['Pastas acessíveis',[...doc.querySelectorAll('[data-folder]')].every(visible)]];
  if(frame.contentWindow.innerWidth<=600){
    const boxes=['#all-content','#fonts-button','#settings-button'].map(id=>doc.querySelector(id)?.getBoundingClientRect());
    results.push(['Controles móveis com alvo de 44px',boxes.every(r=>r&&r.width>=44&&r.height>=44)]);
    results.push(['Controles móveis sem sobreposição',boxes.every((a,i)=>boxes.every((b,j)=>i===j||a.right<=b.left+1||b.right<=a.left+1||a.bottom<=b.top+1||b.bottom<=a.top+1))]);
  }
  const panel=doc.querySelector('dialog[open]');if(panel){results.push(['Painel sem transbordamento horizontal',panel.scrollWidth<=panel.clientWidth+1]);if(panel.classList.contains('studio-dialog'))results.push(['Ações do painel com alvo de 44px',[...panel.querySelectorAll('button')].filter(visible).every(e=>e.getBoundingClientRect().height>=44)]);}
  document.querySelector('#measurement').textContent=`Viewport ${w}px · conteúdo ${root.scrollWidth}px`;
  document.querySelector('#checks').textContent=results.map(([name,pass])=>`${pass?'PASS':'FAIL'} · ${name}`).join('\n');
}
document.querySelectorAll('[data-width]').forEach(button=>button.addEventListener('click',()=>{frame.style.width=button.dataset.width+'px';requestAnimationFrame(measure);}));
frame.addEventListener('load',()=>{const root=frame.contentDocument.documentElement;new ResizeObserver(measure).observe(root);new MutationObserver(measure).observe(root,{childList:true,subtree:true,attributes:true});measure();});
