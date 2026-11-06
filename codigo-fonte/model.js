import {validateFonts,BASE_FONTS} from './fonts.js';
import {checkBrand,checkCues,checkReference,youtubeURL} from './studio-contracts.js';
export const uid = () => crypto.randomUUID();
export const FORMATS = {feed:[1080,1350],story:[1080,1920],quadrado:[1080,1080]};
export const STATUSES = ['Rascunho','Em edição','Em revisão','Pronto','Publicado'];
export const FONTS = [...BASE_FONTS];
export const clone = x => structuredClone(x);
export const MAX_HTML_BYTES=100*1024*1024;
export function assertHTMLSize(bytes){if(bytes>MAX_HTML_BYTES)throw new Error('O HTML deve ter até 100 MB. Reduza as imagens ou divida o carrossel antes de exportar/importar.');}
export function assertBackupSize(bytes){if(bytes>100_000_000)throw new Error('O backup deve ter até 100 MB. Preserve as peças também em HTML e reduza as imagens para diminuir o arquivo.');}
export function imageLayer(image,{name='Imagem',x=90,y=100,w=900,maxHeight=1000}={}){
  const h=Math.max(1,Math.round(Math.min(maxHeight,w*image.height/image.width)));
  return {id:uid(),type:'image',name,src:image.src,x,y,w,h,zoom:1,offsetX:0,offsetY:0,flip:false,visible:true};
}
export const textLayer = (text='Seu texto aqui',extra={}) => ({id:uid(),type:'text',name:'Texto',text,x:90,y:550,w:900,font:'Arial',size:64,color:'#ffffff',bold:true,italic:false,underline:false,align:'left',lineHeight:1.15,letterSpacing:0,visible:true,...extra});
export function newSlide(format='feed') {
  const [width,height]=FORMATS[format]||FORMATS.feed;
  return {id:uid(),width,height,bg:'#151020',bgImage:null,layers:[textLayer('Uma nova ideia.\nUma nova peça.',{y:Math.round(height*.4),name:'Título'})]};
}
export function newPiece(projectId,title,format='feed',count=1) {
  return {id:uid(),projectId,folderId:null,title:title.trim()||'Sem título',channel:'Instagram',format,status:'Rascunho',updatedAt:new Date().toISOString(),slides:Array.from({length:Math.max(1,Math.min(30,count))},()=>newSlide(format))};
}
export function duplicateSlide(slide) {const s=clone(slide);s.id=uid();s.layers.forEach(l=>l.id=uid());return s;}
export function duplicatePiece(piece) {const copy={...clone(piece),id:uid(),demo:false,title:(piece.title+' · cópia').slice(0,180),updatedAt:new Date().toISOString(),slides:piece.slides.map(duplicateSlide)};for(const key of ['variationGroupId','parentPieceId','versionLabel','publishedAt'])delete copy[key];return copy;}
export const normalized = t => String(t).normalize('NFD').replace(/[\u0300-\u036f]/g,'').toLowerCase();
export function filterPieces(pieces,f={}) {
  return pieces.filter(p=>(!f.project||p.projectId===f.project)&&(!f.folder||p.folderId===f.folder)&&(!f.channel||p.channel===f.channel)&&(!f.format||p.format===f.format)&&(!f.status||p.status===f.status)&&(!f.angle||normalized(p.angle||'')===normalized(f.angle))&&(!f.family||(p.variationGroupId||p.id)===f.family)&&(!f.query||normalized(p.title).includes(normalized(f.query))));
}
export function wrapText(text,width,measure) {
  const lines=[];
  for (const para of String(text).split('\n')) {
    if(!para){lines.push('');continue;}
    let line='';
    for(const word of para.split(/\s+/)) {
      const candidate=line?line+' '+word:word;
      if(measure(candidate)<=width){line=candidate;continue;}
      if(line){lines.push(line);line='';}
      for(const char of word){if(line&&measure(line+char)>width){lines.push(line);line='';}line+=char;}
    }
    lines.push(line);
  }
  return lines;
}
export function validateState(input) {
  const fail=()=>{throw new Error('Arquivo inválido: confira projetos, peças, slides e elementos.');};
  if(!input||input.version!==1||!Array.isArray(input.projects)||!Array.isArray(input.pieces)||input.projects.length>500||input.pieces.length>5000)fail();
  const stateFonts=validateFonts(input.fonts||[]);
  const ids=new Set();const id=x=>{if(typeof x!=='string'||!/^[a-z\d_-]{1,100}$/i.test(x)||ids.has(x))fail();ids.add(x);};
  const str=(x,max=10000)=>{if(typeof x!=='string'||x.length>max)fail();};
  const num=(x,min,max)=>{if(!Number.isFinite(x)||x<min||x>max)fail();};
  const color=x=>{if(typeof x!=='string'||!/^#[a-f\d]{6}$/i.test(x))fail();};
  const image=x=>{if(typeof x!=='string'||x.length>8e6||!/^data:image\/(png|jpeg|webp);base64,[a-z\d+/=\s]+$/i.test(x))fail();};
  const projectIds=new Set(),folders=new Map();
  for(const p of input.projects){id(p.id);projectIds.add(p.id);str(p.name,120);color(p.color);if(p.brandKit!==undefined)checkBrand(p.brandKit,[...BASE_FONTS,...stateFonts.map(f=>f.name)]);if(!Array.isArray(p.folders)||p.folders.length>500)fail();for(const f of p.folders){id(f.id);str(f.name,120);folders.set(f.id,p.id);}}
  for(const p of input.pieces){
    const pieceFonts=validateFonts(p.fonts||[]),allowedFonts=[...BASE_FONTS,...stateFonts.map(f=>f.name),...pieceFonts.map(f=>f.name)];
    id(p.id);str(p.title,180);if(!projectIds.has(p.projectId)||(p.folderId&&folders.get(p.folderId)!==p.projectId))fail();
    if(p.angle!==undefined)str(p.angle,160);if(p.versionLabel!==undefined)str(p.versionLabel,64);for(const key of ['variationGroupId','parentPieceId'])if(p[key]!==undefined&&(typeof p[key]!=='string'||!/^[a-z\d_-]{1,100}$/i.test(p[key])))fail();
    if(p.caption!==undefined)str(p.caption,4000);
    if(p.htmlDocument!==undefined){const d=p.htmlDocument;if(d.version!==1||typeof d.html!=='string'||d.html.length>20000000||!Array.isArray(d.editables)||!Array.isArray(d.controls)||!Array.isArray(d.frames)||!d.frames.length||d.frames.length>30||!/^([a-f0-9]{64})$/.test(d.sha256))fail();}
    if(p.source!==undefined)checkReference(p.source);
    if(p.contentKind!==undefined&&!['post','carousel','short'].includes(p.contentKind))fail();
    if(!FORMATS[p.format]||!STATUSES.includes(p.status)||!['Instagram','YouTube','LinkedIn','Outro'].includes(p.channel))fail();
    if(!Array.isArray(p.slides)||!p.slides.length||p.slides.length>30)fail();
    for(const s of p.slides){
      id(s.id);num(s.width,100,4096);num(s.height,100,4096);color(s.bg);if(s.bgImage)image(s.bgImage);
      if(!Array.isArray(s.layers)||s.layers.length>100)fail();
      for(const l of s.layers){
        id(l.id);str(l.name,120);if(!['text','image','shape','vector'].includes(l.type)||typeof l.visible!=='boolean')fail();
        if(l.rotation!==undefined)num(l.rotation,-360,360);if(l.radius!==undefined)num(l.radius,0,4096);if(l.opacity!==undefined)num(l.opacity,0,1);
        num(l.x,-8192,8192);num(l.y,-8192,8192);num(l.w,1,8192);
        if(l.type==='text'){str(l.text);if(!allowedFonts.includes(l.font))fail();num(l.size,8,400);color(l.color);num(l.lineHeight,.6,3);num(l.letterSpacing,-10,60);if(!['left','center','right'].includes(l.align))fail();for(const k of ['bold','italic','underline'])if(typeof l[k]!=='boolean')fail();}
        else if(l.type==='shape'){num(l.h,1,8192);if(!['rect','ellipse'].includes(l.shape))fail();for(const k of ['fill','stroke'])if(l[k]!==null&&l[k]!==undefined)color(l[k]);num(l.strokeWidth??0,0,100);if(l.gradient){num(l.gradient.angle,-360,360);if(!Array.isArray(l.gradient.stops)||l.gradient.stops.length<2||l.gradient.stops.length>16)fail();let prev=-1;for(const st of l.gradient.stops){num(st.offset,0,1);if(st.offset<prev)fail();prev=st.offset;color(st.color);}}}
        else if(l.type==='vector'){num(l.h,1,8192);sanitizeSVG(l.svg);}
        else {image(l.src);num(l.h,1,8192);num(l.zoom,.2,5);num(l.offsetX,-4096,4096);num(l.offsetY,-4096,4096);if(typeof l.flip!=='boolean')fail();}
      }
    }
  }
  if(input.templates!==undefined){
    if(!Array.isArray(input.templates)||input.templates.length>200)fail();
    for(const t of input.templates){id(t.id);str(t.name,120);if(!t.name.trim()||!t.snapshot||typeof t.snapshot!=='object')fail();validateState({version:1,projects:[{id:t.snapshot.projectId,name:'Modelo',color:'#123456',folders:[]}],pieces:[{...t.snapshot,folderId:null}]});}
  }
  if(input.sources!==undefined){if(!Array.isArray(input.sources)||input.sources.length>100)fail();for(const s of input.sources){id(s.id);str(s.title,180);if(!s.title.trim()||!projectIds.has(s.projectId))fail();youtubeURL(s.url);checkCues(s.cues);}}
  if(input.trash!==undefined){if(!Array.isArray(input.trash)||input.trash.length>500)fail();for(const entry of input.trash){id(entry.id);if(!['piece','project'].includes(entry.kind)||typeof entry.deletedAt!=='string'||!Number.isFinite(Date.parse(entry.deletedAt)))fail();if(!entry.snapshot||typeof entry.snapshot!=='object'||entry.snapshot.trash!==undefined)fail();validateState(entry.snapshot);if(entry.snapshot.projects.length!==1||(entry.kind==='piece'&&entry.snapshot.pieces.length!==1))fail();}}
  return clone(input);
}

// ZIP without compression: PNG files are already compressed. UTF-8 names, CRC32 and central directory.
const crcTable=Uint32Array.from({length:256},(_,n)=>{for(let i=0;i<8;i++)n=(n&1)?0xedb88320^(n>>>1):n>>>1;return n>>>0;});
const crc32=bytes=>{let c=0xffffffff;for(const b of bytes)c=crcTable[(c^b)&255]^(c>>>8);return(c^0xffffffff)>>>0;};
export function makeZip(files) {
  const parts=[],central=[];let offset=0;
  for(const f of files){
    const name=new TextEncoder().encode(f.name),data=f.bytes,crc=crc32(data);
    const header=new Uint8Array(30+name.length),v=new DataView(header.buffer);
    v.setUint32(0,0x04034b50,true);v.setUint16(4,20,true);v.setUint16(6,0x800,true);v.setUint16(12,33,true);v.setUint32(14,crc,true);v.setUint32(18,data.length,true);v.setUint32(22,data.length,true);v.setUint16(26,name.length,true);header.set(name,30);
    const dir=new Uint8Array(46+name.length),d=new DataView(dir.buffer);
    d.setUint32(0,0x02014b50,true);d.setUint16(4,20,true);d.setUint16(6,20,true);d.setUint16(8,0x800,true);d.setUint16(14,33,true);d.setUint32(16,crc,true);d.setUint32(20,data.length,true);d.setUint32(24,data.length,true);d.setUint16(28,name.length,true);d.setUint32(42,offset,true);dir.set(name,46);
    parts.push(header,data);central.push(dir);offset+=header.length+data.length;
  }
  const size=central.reduce((n,x)=>n+x.length,0),end=new Uint8Array(22),e=new DataView(end.buffer);
  e.setUint32(0,0x06054b50,true);e.setUint16(8,files.length,true);e.setUint16(10,files.length,true);e.setUint32(12,size,true);e.setUint32(16,offset,true);
  return new Blob([...parts,...central,end],{type:'application/zip'});
}

export const shapeLayer=(extra={})=>({id:uid(),type:'shape',name:'Forma',shape:'rect',x:90,y:90,w:300,h:200,fill:'#bd8aff',stroke:null,strokeWidth:0,radius:0,rotation:0,visible:true,...extra});
/** Strict non-active SVG subset. Reject rather than silently reinterpret unsafe markup. */
export function sanitizeSVG(svg){
 if(typeof svg!=='string'||svg.length>200000||/<!|<\?|&|[\x00-\x08\x0b\x0c\x0e-\x1f]/.test(svg))throw Error('SVG inválido ou ativo.');
 const tags=new Set(['svg','g','path','rect','circle','ellipse','line','polyline','polygon','defs','linearGradient','radialGradient','stop','clipPath']);
 const attrs=new Set(['xmlns','viewBox','width','height','x','y','x1','x2','y1','y2','cx','cy','r','rx','ry','d','points','fill','stroke','stroke-width','stroke-linecap','stroke-linejoin','stroke-miterlimit','fill-rule','clip-rule','opacity','fill-opacity','stroke-opacity','transform','id','offset','stop-color','stop-opacity','gradientUnits','gradientTransform','spreadMethod','fx','fy','clip-path']);
 let end=0,count=0,stack=[];for(const m of svg.matchAll(/<([^<>]+)>/g)){
 if(svg.slice(end,m.index).trim())throw Error('Texto SVG não suportado.');end=m.index+m[0].length;if(++count>2000)throw Error('SVG excede 2000 nós.');
 const close=m[1].startsWith('/'),body=m[1].replace(/^\//,'').replace(/\/\s*$/,'').trim(),name=/^[A-Za-z]+/.exec(body)?.[0];if(!tags.has(name))throw Error('Elemento SVG não permitido.');
 if(close){if(body!==name||stack.pop()!==name)throw Error('SVG malformado.');continue;}if(count===1&&name!=='svg')throw Error('Raiz SVG inválida.');if(count>1&&!stack.length)throw Error('SVG com raízes múltiplas.');
 let rest=body.slice(name.length),used=new Set();while(rest.trim()){const a=/^\s+([\w:-]+)\s*=\s*(["'])(.*?)\2/s.exec(rest);if(!a||!attrs.has(a[1])||used.has(a[1]))throw Error('Atributo SVG não permitido.');used.add(a[1]);const v=a[3];if(['viewBox','width','height','x','y','x1','x2','y1','y2','cx','cy','r','rx','ry','d','points','stroke-width','stroke-miterlimit','opacity','fill-opacity','stroke-opacity','transform','offset','stop-opacity','gradientTransform','fx','fy'].includes(a[1])){if(/NaN|Infinity/i.test(v)||[...v.matchAll(/[-+]?(?:\d*\.)?\d+(?:e[-+]?\d+)?/gi)].some(n=>!Number.isFinite(+n[0])||Math.abs(+n[0])>1e6))throw Error('Geometria SVG fora do limite.');}if(v.length>100000||/[<>\\]/.test(v)||(a[1]!=='xmlns'&&/(?:javascript|data:|https?:|file:|@|expression)/i.test(v)))throw Error('Recurso SVG bloqueado.');if(a[1]==='xmlns'&&v!=='http://www.w3.org/2000/svg')throw Error('Namespace SVG inválido.');if(/url\s*\(/i.test(v)&&!/^url\(#[A-Za-z][\w-]{0,63}\)$/.test(v))throw Error('URL SVG bloqueada.');rest=rest.slice(a[0].length);}
 if(!/\/\s*$/.test(m[1]))stack.push(name);
 }if(!count||stack.length||svg.slice(end).trim())throw Error('SVG malformado.');return svg;
}
