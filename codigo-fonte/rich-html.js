import {readFont,validateFonts,fontKey} from './fonts.js';

/** Browser-measured, resource-neutral HTML. Never insert original markup. */

import {newPiece,textLayer,uid,FONTS,shapeLayer,sanitizeSVG} from './model.js';

import {loadImage} from './render.js';

const px=(v,f=0)=>Number.parseFloat(v)||f;

const hex=rgb=>{const m=rgb.match(/\d+/g);return m&&m.length>=3?'#'+m.slice(0,3).map(n=>(+n).toString(16).padStart(2,'0')).join(''):'#000000';};

export async function richHTML(html,files,htmlPath,projectId,warnings,readImage,packagePath){

 if(html.length>5e6)throw Error('HTML externo limitado a 5 MB.');

 warnings.push('HTML externo: conversão limitada; caixas, gradientes lineares, bordas, SVG simples, texto e imagens editáveis. Efeitos CSS complexos podem ser omitidos; confira a referência.');

 const inert=html.replace(/\b(src|href|srcset|poster|background|data)\s*=/gi,'data-package-$1=');

 const doc=new DOMParser().parseFromString(inert,'text/html');

 doc.querySelectorAll('script,iframe,object,embed,base,meta,foreignObject,animate,animateTransform,set,video,audio,source,track').forEach(e=>e.remove());

 if(doc.querySelectorAll('*').length>2000)throw Error('HTML limitado a 2000 nós.');

 if(/<(script|iframe|object|embed)\b|\son\w+\s*=/i.test(html))warnings.push('Scripts, eventos e conteúdo incorporado foram removidos.');

 const base=htmlPath.includes('/')?htmlPath.slice(0,htmlPath.lastIndexOf('/')+1):'';

 const local=raw=>base+packagePath(raw.replace(/^\.\//,''));

 for(const e of doc.querySelectorAll('*'))for(const a of [...e.attributes])if(/^on/i.test(a.name)||['action','formaction','ping','srcdoc'].includes(a.name))e.removeAttribute(a.name);

 const fonts=[];for(const [path,file] of files)if(/\.(ttf|otf|woff2?)$/i.test(path)){try{const font=await readFont(file);if(fonts.some(f=>fontKey(f.name)===fontKey(font.name)))throw Error('duplicate');fonts.push(font);}catch{warnings.push('Fonte local inválida ignorada.');}}validateFonts(fonts);

 const fontCSS=[...doc.querySelectorAll('style')].map(e=>e.textContent).concat(await Promise.all([...files].filter(([p])=>/\.css$/i.test(p)).map(([,f])=>f.text()))).join('\n');

 for(const match of fontCSS.matchAll(/@font-face\s*\{([^}]+)\}/gi)){

  const family=/font-family\s*:\s*["']?([^;"']+)/i.exec(match[1])?.[1].trim(),url=/url\(\s*["']?([^\s)"']+)/i.exec(match[1])?.[1];if(!family||!url)continue;

  try{if(/^data:font\/(?:ttf|otf|woff2?);base64,/.test(url)){const font={name:family,data:url};validateFonts([font]);if(!fonts.some(f=>fontKey(f.name)===fontKey(family)))fonts.push(font);continue;}const path=packagePath(url.replace(/^\.\//,'')),file=[...files].find(([p])=>p===path||p.endsWith('/'+path))?.[1];if(file){const font=await readFont(file);font.name=family;validateFonts([font]);if(!fonts.some(f=>fontKey(f.name)===fontKey(family)))fonts.push(font);}}catch{warnings.push('Referência de fonte externa ou inválida ignorada.');}

 }validateFonts(fonts);

 const cssSafe=css=>css.replace(/@import[^;]*(;|$)/gi,'').replace(/url\([^)]*\)/gi,'none').replace(/@font-face\s*\{[^}]*\}/gi,'');

 for(const link of [...doc.querySelectorAll('link')]){if(link.rel==='stylesheet'){try{const f=files.get(local(link.getAttribute('data-package-href')||''));if(f){const style=doc.createElement('style');style.textContent=cssSafe(await f.text());link.replaceWith(style);}}catch{warnings.push('Referência de stylesheet bloqueada.');}}link.remove();}

 for(const s of doc.querySelectorAll('style'))s.textContent=cssSafe(s.textContent);

 for(const e of doc.querySelectorAll('[style]'))e.setAttribute('style',cssSafe(e.getAttribute('style')));

 for(const e of doc.querySelectorAll('svg *'))for(const a of [...e.attributes])if(/href$/i.test(a.name)&&!/^#[a-z\w-]+$/i.test(a.value))e.removeAttribute(a.name);

 for(const img of doc.querySelectorAll('img')){try{const src=await readImage(local(img.getAttribute('data-package-src')||''),files);img.setAttribute('src',src);}catch{img.remove();warnings.push('Imagem ausente ou referência externa bloqueada.');}}

 // All resource attributes are neutralized before parsing; only validated data images restored.

 const frame=document.createElement('iframe');frame.sandbox='allow-same-origin';frame.setAttribute('aria-hidden','true');frame.style.cssText='position:fixed;left:-20000px;top:0;width:8192px;height:8192px;visibility:hidden;pointer-events:none';

 const loaded=new Promise(resolve=>frame.onload=resolve);frame.srcdoc=`<!doctype html><meta http-equiv="Content-Security-Policy" content="default-src 'none'; style-src 'unsafe-inline'; img-src data:; font-src data:; base-uri 'none'; form-action 'none'"><style>${fonts.map(f=>`@font-face{font-family:"${f.name}";src:url("${f.data}")}`).join('')}html,body{margin:0}*,*::before,*::after{animation:none!important;transition:none!important}</style>${doc.head.innerHTML}${doc.body.innerHTML}`;document.body.append(frame);

 try{await loaded;const d=frame.contentDocument;await d.fonts.ready;await Promise.all([...d.images].map(i=>i.decode().catch(()=>{})));

 const nodes=[...d.querySelectorAll('[data-export-frame],.slide,[data-slide]')].filter(n=>!n.parentElement.closest('[data-export-frame],.slide,[data-slide]'));if(!nodes.length||nodes.length>30)throw Error('Use 1 a 30 frames data-export-frame, .slide ou data-slide.');

 const piece=newPiece(projectId,(doc.title||'HTML importado').slice(0,180));piece.slides=[];if(fonts.length)piece.fonts=fonts;

 for(const node of nodes){const r=node.getBoundingClientRect(),width=Math.round(r.width),height=Math.round(r.height);if(width<100||height<100||width>4096||height>4096)throw Error('Frame deve ter entre 100 e 4096 px.');

 const slide={id:uid(),width,height,bg:'#ffffff',bgImage:null,layers:[]};const order=new Map([node,...node.querySelectorAll('*')].map((e,i)=>[e,i]));const orderOf=e=>({htmlOrder:order.get(e)||0,htmlZ:px(frame.contentWindow.getComputedStyle(e).zIndex),opacity:effectiveOpacity(e,node)});

 // Reconstruct supported decoration as actual editable geometry, never a generic PNG.

 for(const e of [node,...node.querySelectorAll('*')]){if(e.closest('svg')&&e.tagName.toLowerCase()!=='svg')continue;const cs=frame.contentWindow.getComputedStyle(e),b=e.getBoundingClientRect();if(cs.display==='none'||cs.visibility==='hidden'||!b.width||!b.height)continue;

 const geo=geometry(e,b,r,cs),gradient=linearGradient(cs.backgroundImage),fill=alphaColor(cs.backgroundColor),stroke=px(cs.borderTopWidth)>0?alphaColor(cs.borderTopColor):null;

 if(e.tagName.toLowerCase()==='svg'){try{const copy=e.cloneNode(true);for(const n of [copy,...copy.querySelectorAll('*')])for(const a of [...n.attributes])if(a.name.startsWith('data-package-'))n.removeAttribute(a.name);slide.layers.push({id:uid(),type:'vector',name:'SVG local',svg:sanitizeSVG(new XMLSerializer().serializeToString(copy)),...geo,...orderOf(e),visible:true});}catch{warnings.push('SVG fora do subconjunto seguro foi omitido.');}continue;}

 if(e===node&&fill&&!stroke&&!gradient&&effectiveOpacity(e,node)===1)slide.bg=fill;
 if(e.tagName!=='IMG'&&(fill||stroke||gradient)&&!(e===node&&fill&&!stroke&&!gradient&&effectiveOpacity(e,node)===1))slide.layers.push(shapeLayer({...geo,...orderOf(e),name:'Caixa HTML',fill,stroke,strokeWidth:Math.min(100,px(cs.borderTopWidth)),radius:Math.min(4096,px(cs.borderRadius)),...(gradient?{gradient}:{}),opacity:effectiveOpacity(e,node)}));

 if(cs.backgroundImage!=='none'&&!gradient)warnings.push('Fundo CSS complexo omitido; use imagem local ou gradiente linear.');if(cs.boxShadow!=='none'||cs.filter!=='none')warnings.push('Sombras/filtros CSS precisam de revisão manual.');

 }

 for(const e of node.querySelectorAll('*')){const cs=frame.contentWindow.getComputedStyle(e),b=e.getBoundingClientRect();if(cs.display==='none'||cs.visibility==='hidden'||!b.width||!b.height)continue;const x=b.x-r.x,y=b.y-r.y,w=Math.min(8192,b.width),h=Math.min(8192,b.height);if(x < -8192||x>8192||y < -8192||y>8192)continue;

 if(e.tagName==='IMG'){slide.layers.push({id:uid(),type:'image',name:(e.alt||'Imagem').slice(0,120),src:e.src,...geometry(e,b,r,cs),...orderOf(e),zoom:1,offsetX:0,offsetY:0,flip:false,visible:true,radius:Math.min(4096,px(cs.borderRadius))});continue;}

 }

 for(const segment of textSegments(d,node)){const {text,rect:b,style:cs,element}=segment,x=b.x-r.x,y=b.y-r.y,w=Math.max(1,Math.min(8192,b.width));if(x < -8192||x>8192||y < -8192||y>8192)continue;

 let font=cs.fontFamily.split(',')[0].replace(/[\"']/g,'').trim();font=[...FONTS,...fonts.map(f=>f.name)].find(f=>fontKey(f)===fontKey(font))||'Arial';const size=Math.min(400,Math.max(8,px(cs.fontSize,32)));

 slide.layers.push(textLayer(text,{x,y,w,...orderOf(element),...(element&&Math.abs(effectiveRotation(element,node))>.01?geometry(element,element.getBoundingClientRect(),r,cs):{}),font,size,color:hex(cs.color),bold:+cs.fontWeight>=600,italic:cs.fontStyle==='italic',underline:cs.textDecorationLine.includes('underline'),align:'left',lineHeight:Math.min(3,Math.max(.6,px(cs.lineHeight,size*1.15)/size)),letterSpacing:Math.min(60,Math.max(-10,px(cs.letterSpacing))),opacity:effectiveOpacity(element,node)}));if(slide.layers.length>100)throw Error('Máximo de 100 elementos por frame.');

 }if(slide.layers.length>100)throw Error('Máximo de 100 elementos por frame.');slide.layers.sort((a,b)=>(a.htmlZ||0)-(b.htmlZ||0)||(a.htmlOrder||0)-(b.htmlOrder||0));for(const l of slide.layers){delete l.htmlZ;delete l.htmlOrder;}piece.slides.push(slide);}

 const first=piece.slides[0];piece.format=first.width===first.height?'quadrado':first.height/first.width>1.5?'story':'feed';return piece;

 }finally{frame.remove();}

}











/** Each DOM text node owns its characters exactly once, including frame-root text.

 * Ranges retain inline-run positions; multi-line runs split by their real line boxes.

 */

function textSegments(doc,root){

 const walker=doc.createTreeWalker(root,NodeFilter.SHOW_TEXT),out=[];let total=0;

 while(walker.nextNode()){

  const node=walker.currentNode,raw=node.data;if(!raw.trim()||node.parentElement.closest('style,script,svg'))continue;

  total+=raw.length;if(total>100000)throw Error('Texto HTML limitado a 100 mil caracteres por frame.');

  const style=doc.defaultView.getComputedStyle(node.parentElement);if(style.display==='none'||style.visibility==='hidden')continue;

  const first=raw.search(/\S/),last=raw.search(/\s*$/),range=doc.createRange();range.setStart(node,first);range.setEnd(node,last);

  const rects=[...range.getClientRects()].filter(r=>r.width>0&&r.height>0);if(!rects.length)continue;

  if(rects.length===1){out.push({text:raw.slice(first,last).replace(/\s+/g,' '),rect:rects[0],style,element:node.parentElement});continue;}

  let line=null;const flush=()=>{if(line?.text.trim())out.push({text:line.text.trim(),rect:{x:line.x,y:line.y,width:line.right-line.x},style,element:node.parentElement});line=null;};

  for(let i=first;i<last;i++){

   range.setStart(node,i);range.setEnd(node,i+1);const b=range.getBoundingClientRect();if(!b.width||!b.height)continue;

   if(line&&Math.abs(line.y-b.y)>1)flush();const char=/\s/.test(raw[i])?' ':raw[i];if(!line){if(char===' ')continue;line={text:'',x:b.x,y:b.y,right:b.right};}

   line.text+=char;line.right=Math.max(line.right,b.right);

  }flush();if(out.length>100)throw Error('Máximo de 100 segmentos textuais por frame.');

 }return out;

}



function alphaColor(v){const n=v?.match(/[\d.]+/g);return n&&n.length>=3&&(n.length<4||+n[3]>0)?hex(v):null;}

function rotation(cs){const m=/^matrix\(([^)]+)\)/.exec(cs.transform);if(!m)return 0;const v=m[1].split(',').map(Number);return Math.atan2(v[1],v[0])*180/Math.PI;}

function geometry(e,b,r,cs){const angle=effectiveRotation(e,e.closest('[data-export-frame],.slide,[data-slide]')),w=Math.max(1,Math.min(8192,e.offsetWidth||px(cs.width,b.width))),h=Math.max(1,Math.min(8192,e.offsetHeight||px(cs.height,b.height)));return {x:b.x-r.x+(b.width-w)/2,y:b.y-r.y+(b.height-h)/2,w,h,rotation:angle};}

export function linearGradient(css){

 if(!/^linear-gradient\(/.test(css||''))return null;const body=css.slice(css.indexOf('(')+1,-1),parts=[];let depth=0,start=0;for(let i=0;i<body.length;i++){if(body[i]==='(')depth++;if(body[i]===')')depth--;if(body[i]===','&&depth===0){parts.push(body.slice(start,i).trim());start=i+1;}}parts.push(body.slice(start).trim());let angle=180;

 if(/deg$/.test(parts[0]))angle=px(parts.shift());else if(/^to /.test(parts[0])){angle={'to top':0,'to right':90,'to bottom':180,'to left':270}[parts.shift()];if(angle===undefined)return null;}

 if(parts.length<2||parts.length>16)return null;const stops=parts.map((p,i)=>{const c=/^(rgba?\([^)]*\)|#[a-f\d]{6})(?:\s+([\d.]+)%)?$/i.exec(p);if(!c)return null;return {color:c[1].startsWith('#')?c[1]:hex(c[1]),offset:c[2]===undefined?i/(parts.length-1):Math.min(1,+c[2]/100)};});return stops.every(Boolean)?{angle:Math.max(-360,Math.min(360,angle)),stops}:null;

}


function effectiveOpacity(e,root){let alpha=1;while(e){alpha*=Number(e.ownerDocument.defaultView.getComputedStyle(e).opacity);if(e===root)break;e=e.parentElement;}return Math.min(1,Math.max(0,alpha));}

function effectiveRotation(e,root){let angle=0;while(e){angle+=rotation(e.ownerDocument.defaultView.getComputedStyle(e));if(e===root)break;e=e.parentElement;}return ((angle+180)%360+360)%360-180;}
