import {loadFonts,validateFonts} from './fonts.js';

import {newPiece} from './model.js';

import {drawSlide} from './render.js';

import {compareVisualQA} from './visual-qa.js';

import {evaluateQuality,validateQualityReceipt} from './quality-policy.js';



const canonical=value=>Array.isArray(value)?value.map(canonical):value&&typeof value==='object'?Object.fromEntries(Object.keys(value).sort().map(k=>[k,canonical(value[k])])):value;

export async function imageQAHash(value){return [...new Uint8Array(await crypto.subtle.digest('SHA-256',new TextEncoder().encode(JSON.stringify(canonical(value)))))].map(x=>x.toString(16).padStart(2,'0')).join('');}

export async function verifyImageQA(piece){

 try{const receipt=piece.imageConversion;if(!receipt?.qa)return false;

 const hashes={slideHash:await imageQAHash({slide:piece.slides[0],fonts:piece.fonts||[]}),referenceHash:await imageQAHash(receipt.reference),blocksHash:await imageQAHash(receipt.report.blocks),reportHash:await imageQAHash(receipt.report)};

 return validateQualityReceipt(receipt.qa,hashes,{blocks:receipt.report.blocks,slide:piece.slides[0],warnings:receipt.report.warnings||[]});

 }catch{return false;}

}



export function initImageConversion({getState,onImport,download}){

  if(document.querySelector('#image-conversion-dialog'))return;

  const style=document.createElement('style');style.textContent=`

  #image-conversion-dialog{width:min(1000px,calc(100vw - 24px));max-width:calc(100vw - 24px);max-height:90vh;overflow:auto;box-sizing:border-box;background:#191622;color:#f5f1ff;border:1px solid #665577;border-radius:16px;padding:20px}

  #image-conversion-dialog::backdrop{background:#000a} #image-conversion-dialog *{box-sizing:border-box;min-width:0}

  #image-conversion-dialog input:not([type=checkbox]),#image-conversion-dialog select,#image-conversion-dialog textarea{max-width:100%;color:#fff;background:#252131;border:1px solid #776789;padding:8px;border-radius:5px}

  #image-conversion-dialog button{padding:9px;margin:4px;border:1px solid #887699;border-radius:6px;background:#30253f;color:#fff;cursor:pointer}

  #image-conversion-dialog button:disabled{opacity:.45;cursor:default} .ic-toolbar{display:flex;gap:8px;flex-wrap:wrap;align-items:center}.ic-compare{display:grid;grid-template-columns:1fr 1fr;gap:12px}.ic-compare img,.ic-compare canvas{width:100%;height:auto;display:block}.ic-block{padding:10px;border:1px solid #645772;margin:8px 0;border-radius:8px}.ic-block textarea{display:block;width:100%;margin:6px 0}.ic-box{display:flex;flex-wrap:wrap;gap:6px}.ic-box label{width:90px}.ic-box input{width:100%}.ic-warning{color:#ffdb91;white-space:pre-line}.ic-status{white-space:pre-line;overflow-wrap:anywhere} @media(max-width:600px){.ic-compare{grid-template-columns:1fr}#image-conversion-dialog{padding:12px}.ic-toolbar>*{max-width:100%}}

  `;document.head.append(style);

  const dialog=document.createElement('dialog');dialog.id='image-conversion-dialog';dialog.setAttribute('aria-labelledby','ic-title');

  dialog.innerHTML=`<div class="ic-toolbar"><h2 id="ic-title">Imagem para camadas</h2><button type="button" data-close aria-label="Fechar conversão">Fechar</button></div>

  <p>OCR e limpeza locais. Revise preços, CTA e cada região. A reconstrução é aproximada e preserva a referência original.</p>

  <div class="ic-toolbar"><label>Projeto <select data-project aria-label="Projeto de destino"></select></label><label>Imagem PNG, JPEG ou WebP <input data-file type="file" accept="image/png,image/jpeg,image/webp"></label><label>Idioma <select data-language><option value="por+eng">Português + inglês</option><option value="por">Português</option><option value="eng">Inglês</option></select></label><button data-analyze disabled>Analisar texto localmente</button></div>

  <p class="ic-status" role="status" aria-live="polite"></p><p class="ic-warning"></p>

  <section data-review hidden><h3>1. Selecione e corrija os blocos</h3><p>Selecione até 100 blocos. Desmarque texto que deve permanecer na imagem. Ajuste texto e caixas antes da comparação.</p><div data-blocks></div><details><summary>Painéis e primeiro plano (opcionais)</summary><p>Painéis sólidos detectados ficam desmarcados. Confira a caixa e a cor antes de incluir.</p><div data-panels></div><p>Clique na imagem para marcar um polígono sobre objetos que devem ficar acima do texto. A sobreposição copia pixels originais; evite incluir letras antigas.</p><canvas data-mask-preview style="max-width:100%;height:auto;cursor:crosshair" aria-label="Marcar pontos do primeiro plano"></canvas><div><label>Alpha <input data-alpha type="number" min="0.01" max="1" step="0.05" value="1"></label><button data-save-mask>Salvar polígono</button><button data-undo-point>Desfazer ponto</button><button data-clear-masks>Limpar sobreposições</button></div><p data-mask-status role="status"></p></details><button data-add>Adicionar bloco manual</button><button data-convert>Gerar comparação</button></section>

  <section data-comparison hidden><h3>2. Compare referência e resultado</h3><div class="ic-compare"><div><h4>Referência preservada</h4><img data-original alt="Imagem original preservada"></div><div><h4>Reconstrução aproximada</h4><canvas data-result aria-label="Prévia da reconstrução"></canvas></div></div><h4>QA por região e texto</h4><div data-qa></div><label><input data-approve type="checkbox"> Conferi visualmente fundo, posições, textos, preços e CTA. Esta conferência manual não altera os critérios numéricos.</label><div><button data-create disabled>Criar peça revisada</button><button data-report>Baixar relatório QA</button></div></section>`;

  document.body.append(dialog);

  const q=s=>dialog.querySelector(s),status=q('.ic-status'),warning=q('.ic-warning');

  let image=null,blocks=[],panels=[],occlusions=[],points=[],preview=null,result=null,busy=false,generation=0;

  const state=()=>{const value=getState();return value.state||value;};

  const invalidate=()=>{generation++;result=null;q('[data-comparison]').hidden=true;q('[data-create]').disabled=true;q('[data-approve]').checked=false;};

  const fail=error=>{status.textContent=error.message||String(error);};

  const request=async(endpoint,body)=>{const response=await fetch('/api/local/image/'+endpoint,{method:'POST',headers:{'Content-Type':'application/json','X-Peca-Request':'1'},body:JSON.stringify(body)});const value=await response.json();if(!response.ok||value.error)throw new Error(value.error||'Falha no serviço local.');return value;};

  const work=async(callback)=>{if(busy)return;busy=true;dialog.setAttribute('aria-busy','true');for(const b of dialog.querySelectorAll('[data-analyze],[data-convert],[data-add],[data-file],[data-language]'))b.disabled=true;try{await callback();}catch(error){fail(error);}finally{busy=false;dialog.removeAttribute('aria-busy');q('[data-analyze]').disabled=!image;for(const b of dialog.querySelectorAll('[data-convert],[data-add],[data-file],[data-language]'))b.disabled=false;}};

  function renderBlocks(){q('[data-blocks]').replaceChildren();blocks.forEach((block,index)=>{const row=document.createElement('div');row.className='ic-block';const label=document.createElement('label'),check=document.createElement('input');check.type='checkbox';check.checked=block.selected!==false;check.onchange=()=>{block.selected=check.checked;invalidate();};label.append(check,` Bloco ${index+1} · confiança ${block.confidence??'manual'}%`);row.append(label);const text=document.createElement('textarea');text.value=block.text;text.setAttribute('aria-label',`Texto do bloco ${index+1}`);text.oninput=()=>{block.text=text.value;invalidate();};row.append(text);const box=document.createElement('div');box.className='ic-box';for(const key of ['x','y','w','h']){const label=document.createElement('label');label.textContent=key;const input=document.createElement('input');input.type='number';input.value=block[key];input.min=key==='w'||key==='h'?1:0;input.setAttribute('aria-label',`${key} bloco ${index+1}`);input.oninput=()=>{block[key]=Number(input.value);invalidate();};label.append(input);box.append(label);}row.append(box);q('[data-blocks]').append(row);});}

  function drawMask(){const canvas=q('[data-mask-preview]');if(!preview)return;canvas.width=preview.naturalWidth;canvas.height=preview.naturalHeight;const ctx=canvas.getContext('2d');ctx.drawImage(preview,0,0);ctx.lineWidth=Math.max(2,canvas.width/300);for(const polygon of [...occlusions,{points}]){if(!polygon.points.length)continue;ctx.beginPath();polygon.points.forEach(([x,y],i)=>i?ctx.lineTo(x,y):ctx.moveTo(x,y));if(polygon!==undefined&&polygon.points!==points)ctx.closePath();ctx.strokeStyle='#00ffcc';ctx.stroke();for(const [x,y] of polygon.points){ctx.fillStyle='#ff0088';ctx.fillRect(x-3,y-3,6,6);}}q('[data-mask-status]').textContent=`${occlusions.length}/16 sobreposições; ${points.length}/64 pontos no polígono atual.`;}

  function renderPanels(){q('[data-panels]').replaceChildren();panels.forEach((panel,index)=>{const row=document.createElement('div');row.className='ic-box';const check=document.createElement('input');check.type='checkbox';check.checked=panel.selected;check.setAttribute('aria-label',`Incluir painel ${index+1}`);check.onchange=()=>{panel.selected=check.checked;invalidate();};row.append(check);for(const key of ['x','y','w','h','color']){const label=document.createElement('label');label.textContent=key;const input=document.createElement('input');input.type=key==='color'?'color':'number';input.value=panel[key];input.setAttribute('aria-label',`${key} painel ${index+1}`);input.oninput=()=>{panel[key]=key==='color'?input.value:Number(input.value);invalidate();};label.append(input);row.append(label);}q('[data-panels]').append(row);});}

  q('[data-mask-preview]').onclick=event=>{if(busy||!preview||points.length>=64)return;const rect=event.currentTarget.getBoundingClientRect();points.push([Math.min(preview.naturalWidth-1,Math.max(0,Math.round((event.clientX-rect.left)*preview.naturalWidth/rect.width))),Math.min(preview.naturalHeight-1,Math.max(0,Math.round((event.clientY-rect.top)*preview.naturalHeight/rect.height)))]);invalidate();drawMask();};

  q('[data-save-mask]').onclick=()=>{if(busy)return;const alpha=Number(q('[data-alpha]').value);if(points.length<3||occlusions.length>=16||!Number.isFinite(alpha)||alpha<=0||alpha>1){fail(new Error('Use 3 a 64 pontos, alpha entre 0 e 1 e até 16 polígonos.'));return;}occlusions.push({points:points.map(p=>[...p]),alpha});points=[];invalidate();drawMask();};

  q('[data-undo-point]').onclick=()=>{points.pop();invalidate();drawMask();};q('[data-clear-masks]').onclick=()=>{points=[];occlusions=[];invalidate();drawMask();};

  const updateCreate=()=>{q('[data-create]').disabled=!result||!q('[data-approve]').checked||[...q('[data-qa]').querySelectorAll('input')].some(x=>!x.checked);};

  q('[data-close]').onclick=()=>dialog.close();

  q('[data-file]').onchange=async()=>{invalidate();image=null;blocks=[];panels=[];occlusions=[];points=[];preview=null;q('[data-review]').hidden=true;q('[data-analyze]').disabled=true;warning.textContent='';const file=q('[data-file]').files[0];if(!file)return;try{if(!['image/png','image/jpeg','image/webp'].includes(file.type)||file.size>20*1024*1024)throw new Error('Escolha PNG/JPEG/WebP de até 20 MB.');image=await new Promise((resolve,reject)=>{const reader=new FileReader();reader.onload=()=>resolve(reader.result);reader.onerror=()=>reject(new Error('Falha ao ler imagem.'));reader.readAsDataURL(file);});q('[data-analyze]').disabled=false;status.textContent='Imagem pronta para análise local.';}catch(error){fail(error);}};

  q('[data-analyze]').onclick=()=>work(async()=>{invalidate();status.textContent='Analisando com Tesseract local…';const analysis=await request('analyze',{image,language:q('[data-language]').value});blocks=analysis.blocks;panels=analysis.panels||[];occlusions=[];points=[];renderBlocks();renderPanels();preview=new Image();preview.src=image;await preview.decode();drawMask();warning.textContent=analysis.warnings.join('\n');q('[data-review]').hidden=false;status.textContent=`${blocks.length} blocos encontrados. Revise e selecione antes de converter.`;});

  q('[data-add]').onclick=()=>{invalidate();blocks.push({id:crypto.randomUUID(),text:'Texto manual',x:0,y:0,w:100,h:30,selected:true});renderBlocks();};

  q('[data-convert]').onclick=()=>work(async()=>{invalidate();if(blocks.filter(b=>b.selected!==false).length>100)throw new Error('Selecione no máximo 100 blocos; desmarque os demais antes de converter.');const ticket=generation;status.textContent='Limpando o fundo e reconstruindo camadas…';if(points.length)throw new Error('Salve ou limpe os pontos do polígono antes de converter.');const fonts=validateFonts(state().fonts||[]);const next=await request('convert',{image,language:q('[data-language]').value,blocks,fonts,panels,occlusions});await loadFonts(next.fonts||fonts);if(ticket!==generation){status.textContent='Os blocos mudaram durante a conversão. Gere novamente.';return;}q('[data-original]').src=next.reference.image;await drawSlide(q('[data-result]'),next.slide,{width:Math.min(1024,next.slide.width)});const metrics=await compareVisualQA(next.reference,q('[data-result]'),next.report.blocks);if(ticket!==generation){status.textContent='Os blocos mudaram durante a comparação. Gere novamente.';return;}next.report.qa.metrics=metrics;result=next;warning.textContent=[...(result.report.notices||[]),...result.report.warnings].join('\n');q('[data-qa]').replaceChildren();for(const region of result.report.qa.regions){const label=document.createElement('label');label.style.display='block';const check=document.createElement('input');check.type='checkbox';check.dataset.region=region.id;check.onchange=()=>{region.approved=check.checked;updateCreate();};const metric=metrics.regions.find(item=>item.id===region.id);label.append(check,` Revisei região: ${region.text} · erro RGB médio ${metric.meanAbsoluteError}/255 · ${(metric.pixelsWithin20*100).toFixed(1)}% dos pixels dentro de 20 níveis`);q('[data-qa]').append(label);}q('[data-comparison]').hidden=false;q('[data-approve]').checked=false;status.textContent=`Compare as duas imagens. A revisão vale apenas para esta versão.\nAmostragem ${metrics.resolution.width} × ${metrics.resolution.height} (máximo 1024 px). Global: erro RGB médio ${metrics.global.meanAbsoluteError}/255; ${(metrics.global.pixelsWithin20*100).toFixed(1)}% dentro de 20 níveis.\n${metrics.notice}`;updateCreate();});

  q('[data-approve]').onchange=updateCreate;

  async function receipt(){

    if(!result)throw new Error('Gere uma comparação primeiro.');

    const hashes={slideHash:await imageQAHash({slide:result.slide,fonts:result.fonts||[]}),referenceHash:await imageQAHash(result.reference),blocksHash:await imageQAHash(result.report.blocks),reportHash:await imageQAHash(result.report)};

    const manual=q('[data-approve]').checked&&result.report.qa.regions.every(x=>x.approved);

    const decision=evaluateQuality({metrics:result.report.qa.metrics,blocks:result.report.blocks,slide:result.slide,warnings:result.report.warnings||[],hashes,exceptions:[]});

    return {schemaVersion:2,status:manual?decision.status:'blocked',strictPass:manual&&decision.strictPass,metrics:result.report.qa.metrics,exceptions:[],...hashes,reviewedAt:new Date().toISOString()};

  }

  q('[data-create]').onclick=()=>work(async()=>{if(q('[data-create]').disabled)return;const projectId=q('[data-project]').value;if(!state().projects.some(p=>p.id===projectId))throw new Error('Crie ou escolha um projeto para importar a peça.');const qa=await receipt();if(!['passed','exception-approved','blocked'].includes(qa.status))throw new Error('Gere as métricas antes de importar o rascunho.');const ratio=result.slide.height/result.slide.width;const piece=newPiece(projectId,'Imagem convertida',ratio===1?'quadrado':ratio>1.5?'story':'feed',1);piece.slides=[result.slide];piece.fonts=validateFonts(result.fonts||state().fonts||[]);piece.imageConversion={reference:result.reference,report:result.report,qa};await onImport(piece);dialog.close();});

  q('[data-report]').onclick=async()=>{try{const data={...result.report,qa:await receipt()};download(new Blob([JSON.stringify(data,null,2)],{type:'application/json'}),'revisao-imagem.json');}catch(error){fail(error);}};

  const button=document.createElement('button');button.type='button';button.className='button';button.id='image-conversion-launch';button.textContent='▧ Imagem para camadas';button.onclick=()=>{const value=getState(),data=value.state||value;q('[data-project]').replaceChildren();for(const project of data.projects){const option=document.createElement('option');option.value=project.id;option.textContent=project.name;q('[data-project]').append(option);}const selected=value.selectedProject||value.projectId;if(selected&&data.projects.some(p=>p.id===selected))q('[data-project]').value=selected;if(!data.projects.length)status.textContent='Crie um projeto na biblioteca antes de importar a conversão.';dialog.showModal();};document.querySelector('.studio-launchers')?.append(button);

  return {open:()=>button.click()};

}
