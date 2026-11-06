import {htmlRequest,prepareHTMLPiece} from './html-document-ui.js';
import {richHTML} from './rich-html.js';
import {validateFonts} from './fonts.js';
/** Local package I/O. Own manifests retain editable geometry and embedded fonts.
 * Rich external HTML is measured in a scriptless CSP-isolated frame; supported decoration remains vector geometry.
 * Legacy simple HTML keeps its 1.5 import behavior. No network or original scripts.
 */
import {newPiece,textLayer,validateState,uid,FONTS,sanitizeSVG} from './model.js';
export const PACKAGE_MAX_FILES=100, PACKAGE_MAX_BYTES=100*1024*1024;
const encode=s=>new TextEncoder().encode(s);
const esc=s=>String(s).replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
export function packagePath(value){
 const path=String(value).replace(/\\/g,'/');
 if(!path||path.startsWith('/')||/[\x00-\x1f:?#%]/.test(path)||path.split('/').some(p=>!p||p==='.'||p==='..')||/\.svg$/i.test(path))throw new Error('Caminho de pacote inválido ou SVG não suportado.');
 return path;
}
export function packageFiles(input){
 const entries=input instanceof Map?[...input]:Array.from(input||[],f=>[f.webkitRelativePath||f.name,f]);
 if(!entries.length||entries.length>PACKAGE_MAX_FILES)throw new Error('Selecione de 1 a 100 arquivos.');
 let size=0;const map=new Map();
 for(const [raw,file] of entries){const path=packagePath(raw);if(map.has(path))throw new Error('Caminho duplicado no pacote.');if(!Number.isFinite(file.size)||file.size<0)throw new Error('Tamanho de arquivo inválido.');size+=file.size;if(size>PACKAGE_MAX_BYTES)throw new Error('O pacote deve ter até 100 MB.');map.set(path,file);}
 // Directory inputs include a common top-level directory; ordinary Map paths do not.
 if(!(input instanceof Map)&&entries.every(([p])=>p.includes('/')&&p.split('/')[0]===entries[0][0].split('/')[0]))return new Map([...map].map(([p,f])=>[p.slice(p.indexOf('/')+1),f]));
 return map;
}
function validPiece(piece){
 const copy=structuredClone(piece);copy.folderId=null;
 validateState({version:1,projects:[{id:copy.projectId,name:'Pacote',color:'#123456',folders:[]}],pieces:[copy]});return copy;
}
function imageData(src){
 const m=/^data:image\/(png|jpeg|webp);base64,([a-z\d+/=\s]+)$/i.exec(src||'');if(!m)throw new Error('Imagem inválida; use PNG, JPEG ou WebP.');
 return {ext:m[1].toLowerCase(),bytes:Uint8Array.from(atob(m[2]),c=>c.charCodeAt(0))};
}
async function readImage(path,files){
 path=packagePath(path.replace(/^\.\//,''));const file=files.get(path);if(!file)throw new Error(`Asset ausente: ${path}`);
 const ext=path.split('.').pop().toLowerCase();const mime={png:'png',jpg:'jpeg',jpeg:'jpeg',webp:'webp'}[ext];if(!mime)throw new Error('Asset de imagem não suportado.');
 const bytes=new Uint8Array(await file.arrayBuffer());
 const header=(offset,values)=>values.every((v,i)=>bytes[offset+i]===v);
 if(!(mime==='png'&&bytes.length>=24&&header(0,[137,80,78,71,13,10,26,10])||mime==='jpeg'&&bytes.length>=4&&header(0,[255,216,255])||mime==='webp'&&bytes.length>=12&&header(0,[82,73,70,70])&&header(8,[87,69,66,80])))throw new Error('Asset raster inválido: assinatura de imagem incorreta.');
 let binary='';for(let i=0;i<bytes.length;i+=32768)binary+=String.fromCharCode(...bytes.subarray(i,i+32768));const src=`data:image/${mime};base64,${btoa(binary)}`;
 if(typeof Image!=='undefined'){const {loadImage}=await import('./render.js');const image=await loadImage(src);if(image.width<1||image.height<1||image.width>8192||image.height>8192||image.width*image.height>60e6)throw new Error('Imagem limitada a 8192 px por lado e 60 megapixels.');}
 return src;
}
export async function exportPackage(piece){
 const copy=validPiece(piece),files=[],seen=new Map();
 const asset=src=>{if(seen.has(src))return seen.get(src);const {ext,bytes}=imageData(src),name=`assets/image-${seen.size+1}.${ext}`;files.push({name,bytes});seen.set(src,name);return name;};
 for(const slide of copy.slides){if(slide.bgImage)slide.bgImage=asset(slide.bgImage);for(const layer of slide.layers)if(layer.type==='image')layer.src=asset(layer.src);}
 const style=l=>`position:absolute;opacity:${l.opacity??1};left:${l.x}px;top:${l.y}px;width:${l.w}px;transform:rotate(${l.rotation||0}deg);transform-origin:center;`;
 const layerHTML=l=>{
 if(l.type==='text')return `<div style="${style(l)}font-family:${esc(l.font)};font-size:${l.size}px;color:${l.color};font-weight:${l.bold?'bold':'normal'};font-style:${l.italic?'italic':'normal'};text-decoration:${l.underline?'underline':'none'};text-align:${l.align};line-height:${l.lineHeight};letter-spacing:${l.letterSpacing}px;white-space:pre-wrap">${esc(l.text)}</div>`;
 if(l.type==='vector')return `<div style="${style(l)}height:${l.h}px">${sanitizeSVG(l.svg).replace(/<svg\b/,'<svg style="width:100%;height:100%"')}</div>`;
 if(l.type==='shape'){const bg=l.gradient?`linear-gradient(${l.gradient.angle}deg,${l.gradient.stops.map(s=>`${s.color} ${s.offset*100}%`).join(',')})`:l.fill||'transparent';return `<div style="${style(l)}box-sizing:border-box;height:${l.h}px;background:${bg};border:${l.strokeWidth||0}px solid ${l.stroke||'transparent'};border-radius:${l.shape==='ellipse'?'50%':(l.radius||0)+'px'}"></div>`;}
 return `<div style="${style(l)}overflow:hidden;height:${l.h}px;border-radius:${l.radius||0}px"><img alt="${esc(l.name)}" src="${esc(l.src)}" style="width:100%;height:100%;object-fit:cover;transform:translate(${l.offsetX}px,${l.offsetY}px) scale(${l.flip?-l.zoom:l.zoom},${l.zoom})"></div>`;
 };
 const slides=copy.slides.map(s=>`<section class="slide" style="position:relative;overflow:hidden;width:${s.width}px;height:${s.height}px;background:${s.bg}${s.bgImage?`;background-image:url('${esc(s.bgImage)}');background-size:cover`:''}">${s.layers.filter(l=>l.visible).map(layerHTML).join('')}</section>`).join('\n');
 files.unshift({name:'index.html',bytes:encode(`<!doctype html><html lang="pt-BR"><meta charset="utf-8"><meta name="viewport" content="width=device-width"><title>${esc(copy.title)}</title><style>${validateFonts(copy.fonts||[]).map(f=>`@font-face{font-family:"${f.name}";src:url("${f.data}")}`).join('')}</style><body>${slides}</body></html>`)});
 files.push({name:'peca-studio.json',bytes:encode(JSON.stringify({version:1,kind:'peca-studio-package',piece:copy},null,2))});
 packageFiles(new Map(files.map(f=>[f.name,{size:f.bytes.length}])));return files;
}
export async function importPackage(input,projectId,{preferHTML=false}={}){
 if(!/^[a-z\d_-]{1,100}$/i.test(projectId||''))throw new Error('Projeto destino inválido.');
 const files=packageFiles(input),warnings=[];let piece;
 if(!preferHTML&&files.has('peca-studio.json')){
  const manifest=JSON.parse(await files.get('peca-studio.json').text());if(manifest.version!==1||manifest.kind!=='peca-studio-package'||!manifest.piece)throw new Error('Manifesto de pacote inválido.');piece=manifest.piece;
  if(!Array.isArray(piece.slides)||piece.slides.length>30)throw new Error('Slides inválidos.');
  for(const s of piece.slides){if(s.bgImage)s.bgImage=await readImage(s.bgImage,files);if(!Array.isArray(s.layers)||s.layers.length>100)throw new Error('Elementos inválidos.');for(const l of s.layers)if(l.type==='image')l.src=await readImage(l.src,files);}
  validPiece(piece);
 }else{
  const html=[...files.keys()].find(p=>p==='index.html')||[...files.keys()].find(p=>/\.html?$/i.test(p));if(!html)throw new Error('Selecione index.html e seus assets.');
  let source=await files.get(html).text();const cssText=(await Promise.all([...files].filter(([name])=>/\.css$/i.test(name)).map(([,file])=>file.text()))).join('\n');if(/data-export-frame/.test(source)){
   const base=html.includes('/')?html.slice(0,html.lastIndexOf('/')+1):'';
   const inert=source.replace(/\b(src|href|srcset|poster|background|data)\s*=/gi,'data-package-$1=');
   const doc=new DOMParser().parseFromString(inert,'text/html');
   for(const link of [...doc.querySelectorAll('link')]){if(link.rel!=='stylesheet')throw Error('HTML preservado aceita somente stylesheet local.');const path=base+packagePath(link.getAttribute('data-package-href')||''),file=files.get(path);if(!file)throw Error('Stylesheet ausente: '+path);const style=doc.createElement('style');style.textContent=await file.text();style.dataset.sourceBase=path.includes('/')?path.slice(0,path.lastIndexOf('/')+1):'';link.replaceWith(style);}
   for(const img of doc.querySelectorAll('img')){const raw=img.getAttribute('data-package-src')||'';img.src=await readImage(raw.startsWith('data:')?raw:base+packagePath(raw),files);img.removeAttribute('data-package-src');}
   for(const node of doc.querySelectorAll('style,[style]')){const css=node.tagName==='STYLE'?node.textContent:node.getAttribute('style');let output=css;for(const match of [...css.matchAll(/url\(\s*["']?([^\s)"']+)["']?\s*\)/g)]){const raw=match[1];if(raw.startsWith('data:')||raw.startsWith('#'))continue;const path=(node.dataset.sourceBase??base)+packagePath(raw.replace(/^\.\//,'')),file=files.get(path);if(!file)throw Error('Ativo CSS ausente: '+path);const data=await new Promise((resolve,reject)=>{const reader=new FileReader();reader.onload=()=>resolve(reader.result);reader.onerror=reject;reader.readAsDataURL(file);});const mime=/\.woff2?$/i.test(path)?'font/'+(path.toLowerCase().endsWith('woff2')?'woff2':'woff'):/\.otf$/i.test(path)?'font/otf':/\.ttf$/i.test(path)?'font/ttf':null;output=output.replace(match[0],'url("'+(mime?data.replace(/^data:[^;]+;/,'data:'+mime+';'):data)+'")');}if(node.tagName==='STYLE')node.textContent=output;else node.setAttribute('style',output);delete node.dataset.sourceBase;}
   for(const node of doc.querySelectorAll('*'))for(const a of [...node.attributes])if(a.name.startsWith('data-package-')){if(a.name!=='data-package-data')throw Error('Recurso ativo não suportado no HTML preservado.');node.removeAttribute(a.name);}
   piece=await prepareHTMLPiece('<!doctype html>'+doc.documentElement.outerHTML,projectId,(doc.title||'HTML preservado').slice(0,180));
  }else piece=await (/data-editable|display\s*:\s*(flex|grid)|gradient\s*\(|transform\s*:|<svg\b/i.test(source+cssText)?richHTML(source,files,html,projectId,warnings,readImage,packagePath):externalHTML(source,files,html,projectId,warnings));
 }
 if(piece.htmlDocument)piece.htmlDocument=await htmlRequest('validate',{document:piece.htmlDocument});
 piece.projectId=projectId;piece.folderId=null;piece.id=uid();piece.slides.forEach(s=>{s.id=uid();s.layers.forEach(l=>l.id=uid());});for(const key of ['parentPieceId','variationGroupId','versionLabel'])delete piece[key];piece.updatedAt=new Date().toISOString();
 return {piece:validPiece(piece),warnings:[...new Set(warnings)]};
}


function declarations(text){return Object.fromEntries(text.split(';').map(x=>{const i=x.indexOf(':');return i<0?[]:[x.slice(0,i).trim().toLowerCase(),x.slice(i+1).trim().replace(/\s*!important$/,'')];}).filter(x=>x.length===2));}
function number(value,fallback,min,max){if(value===undefined||value===null||value==='')return fallback;const n=Number(String(value).replace(/px$/,''));if(!Number.isFinite(n)||n<min||n>max)throw new Error('Número/dimensão CSS inválido ou fora do limite.');return n;}
function color(value,fallback){if(!value)return fallback;const hex=/^#([a-f\d]{3}|[a-f\d]{6})$/i.exec(value);if(hex)return hex[1].length===3?'#'+[...hex[1]].map(x=>x+x).join(''):value;const rgb=/^rgb\(\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)\s*\)$/.exec(value);if(rgb&&rgb.slice(1).every(n=>+n<=255))return '#'+rgb.slice(1).map(n=>(+n).toString(16).padStart(2,'0')).join('');const names={white:'#ffffff',black:'#000000',red:'#ff0000',blue:'#0000ff',green:'#008000',transparent:fallback};return names[value.toLowerCase()]||fallback;}
async function externalHTML(html,files,htmlPath,projectId,warnings){
 if(typeof DOMParser==='undefined')throw new Error('A importação de HTML externo requer um navegador com DOMParser.');
 warnings.push('HTML externo: conversão limitada a texto e imagens com dimensões/posição em px. Flex/grid, transformações, fontes externas, gradientes e scripts não são convertidos.');
 if(/<(script|iframe|object|embed)\b|\son\w+\s*=|@import|url\(/i.test(html))warnings.push('Scripts, eventos, conteúdo incorporado e referências CSS externas foram ignorados.');
 // Neutralize resource attributes before parsing the detached document (including broken markup).
 const inert=html.replace(/\b(src|href|srcset|poster|background|data)\s*=/gi,'data-package-$1=');
 const doc=new DOMParser().parseFromString(inert,'text/html');doc.querySelectorAll('script,iframe,object,embed,base,svg').forEach(e=>e.remove());
 const rules=[];
 for(const sheet of doc.querySelectorAll('style,link')){
  let css=sheet.textContent;
  if(sheet.tagName==='LINK'){
   if(!(sheet.getAttribute('rel')||'').toLowerCase().split(/\s+/).includes('stylesheet'))continue;
   const raw=sheet.getAttribute('data-package-href')||'',path=packagePath(raw.replace(/^\.\//,''));
   if(!/\.css$/i.test(path))throw new Error('Stylesheet local deve ser um arquivo CSS.');
   const base=htmlPath.includes('/')?htmlPath.slice(0,htmlPath.lastIndexOf('/')+1):'',file=files.get(base+path);
   if(!file){warnings.push(`Stylesheet ausente: ${base+path}`);continue;}
   css=await file.text();
  }
  if(/@import|url\(/i.test(css))warnings.push('Referências CSS via @import/url foram ignoradas; inclua as imagens como IMG e selecione todos os arquivos locais.');
  for(const match of css.replace(/\/\*[\s\S]*?\*\//g,'').matchAll(/([^{}]+)\{([^{}]*)\}/g))for(const selector of match[1].split(','))if(/^[\w.#\s>\[\]="'-]+$/.test(selector.trim()))rules.push([selector.trim(),declarations(match[2])]);
 }
 const style=el=>{let out={};for(const [selector,decl] of rules){try{if(el.matches(selector))Object.assign(out,decl);}catch{}}return Object.assign(out,declarations(el.getAttribute('style')||''));};
 const nodes=[...doc.querySelectorAll('.slide,[data-slide]')];if(!nodes.length)throw new Error('HTML sem slides: use .slide ou [data-slide].');if(nodes.length>30)throw new Error('Máximo de 30 slides.');
 const piece=newPiece(projectId,(doc.title||'HTML importado').slice(0,180));piece.slides=[];
 for(const node of nodes){const st=style(node);const width=number(st.width||node.getAttribute('width')||node.getAttribute('data-width'),1080,100,4096),height=number(st.height||node.getAttribute('height')||node.getAttribute('data-height'),1350,100,4096);const slide={id:uid(),width,height,bg:color(st['background-color']||st.background,'#ffffff'),bgImage:null,layers:[]};
  for(const el of node.querySelectorAll('h1,h2,h3,p,div,img')){if(el.closest('.slide,[data-slide]')!==node||el.tagName!=='IMG'&&el.children.length)continue;const cs=style(el);if(cs.display==='none'||cs.visibility==='hidden')continue;const x=number(cs.left,0,-8192,8192),y=number(cs.top,0,-8192,8192),w=number(cs.width||el.getAttribute('width'),width,1,8192);
   if(el.tagName==='IMG'){
    const raw=el.getAttribute('data-package-src')||'';if(!raw){warnings.push('Imagem sem src ignorada.');continue;}const path=packagePath(raw.replace(/^\.\//,''));const base=htmlPath.includes('/')?htmlPath.slice(0,htmlPath.lastIndexOf('/')+1):'';let src;try{src=await readImage(base+path,files);}catch(e){if(!e.message.includes('ausente'))throw e;warnings.push(e.message);continue;}
    const h=number(cs.height||el.getAttribute('height'),w,1,8192),radius=cs['border-radius']==='50%'?Math.min(w,h)/2:number(cs['border-radius'],0,0,4096);slide.layers.push({id:uid(),type:'image',name:(el.getAttribute('alt')||'Imagem').slice(0,120),src,x,y,w,h,radius,zoom:1,offsetX:0,offsetY:0,flip:false,visible:true});
   }else{const text=el.textContent.trim();if(!text)continue;let font=(cs['font-family']||'Arial').split(',')[0].trim().replace(/["']/g,'');if(!FONTS.includes(font)){font='Arial';warnings.push('Fonte não suportada substituída por Arial.');}
    const size=number(cs['font-size'],el.tagName==='H1'?64:32,8,400);let lineHeight=cs['line-height'];if(lineHeight?.endsWith('px'))lineHeight=number(lineHeight,size,.1,1200)/size;slide.layers.push(textLayer(text,{x,y,w,font,size,color:color(cs.color,'#000000'),bold:cs['font-weight']==='bold'||+cs['font-weight']>=600||/^H[123]$/.test(el.tagName),italic:cs['font-style']==='italic',underline:(cs['text-decoration']||'').includes('underline'),align:['left','center','right'].includes(cs['text-align'])?cs['text-align']:'left',lineHeight:number(lineHeight,1.15,.6,3),letterSpacing:number(cs['letter-spacing'],0,-10,60)}));}
  }piece.slides.push(slide);
 }
 const first=piece.slides[0];piece.format=first.width===first.height?'quadrado':first.height/first.width>1.5?'story':'feed';return piece;
}
