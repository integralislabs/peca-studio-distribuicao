import {newPiece,textLayer,wrapText} from './model.js';
import {applyBrand,validateBrandKit} from './brand.js';
import {fillTemplate,validateTemplate} from './templates.js';
import {checkReference} from './studio-contracts.js';
export const AI_NAMES={openai:'OpenAI',claude:'Claude',gemini:'Gemini'};

const fail=()=>{throw new Error('Rascunho de IA inválido. Confira os campos e limites.');};
const string=(v,max,required=false)=>{if(typeof v!=='string'||v.length>max||(required&&!v.trim()))fail();return v.trim();};
export function validateAIDraft(draft,count){
 if(!draft||!Array.isArray(draft.slides)||draft.slides.length!==count||!Number.isInteger(count)||count<1||count>10)fail();
 return {title:string(draft.title,180,true),caption:string(draft.caption,4000,true),slides:draft.slides.map(s=>({title:string(s?.title,100,true),body:string(s?.body,360),imagePrompt:string(s?.imagePrompt,1200)}))};
}
export function validateAIFile(input){
 if(input?.version!==1||!input.brief)fail();const b=input.brief;
 if(!['feed','story','quadrado'].includes(b.format)||!['editorial','impacto','minimal'].includes(b.style)||![b.bg,b.accent].every(c=>typeof c==='string'&&/^#[a-f\d]{6}$/i.test(c)))fail();
 const brief={count:b.count,format:b.format,style:b.style,bg:b.bg,accent:b.accent};
 const provider=b.provider===undefined?'openai':b.provider,imageProvider=b.imageProvider===undefined?'openai':b.imageProvider;
 if(typeof provider!=='string'||!Object.hasOwn(AI_NAMES,provider)||!['openai','gemini'].includes(imageProvider))fail();
 brief.provider=provider;brief.imageProvider=imageProvider;
 if(b.brandKit!==undefined)brief.brandKit=validateBrandKit(b.brandKit);
 if(b.template!==undefined)brief.template=validateTemplate(b.template);
 brief.kind=b.kind??(b.count===1?'post':'carousel');if(!['post','carousel','short'].includes(brief.kind))fail();
 if(b.source!==undefined)brief.source=checkReference(b.source);
 for(const [name,max] of [['topic',2500],['audience',300],['goal',300],['tone',300],['brand',120]])brief[name]=string(b[name],max,name==='topic');
 const draft=validateAIDraft(input.draft,b.count);
 if(!Array.isArray(input.images)||input.images.length>b.count)fail();
 const images=input.images.map(src=>{if(src!==null&&(typeof src!=='string'||src.length>7_000_000||!/^data:image\/jpeg;base64,\/9j\/[a-z\d+/=\s]+$/i.test(src)))fail();return src;});
 return {version:1,brief,draft,images};
}
export function fitCopy(text,width,height,font,start,measure){
 for(let size=start;size>=12;size--){if(wrapText(text,width,t=>measure(t,font,size)).length*size*1.15<=height)return size;}
 throw new Error('Este texto não cabe no slide. Reduza o conteúdo antes de salvar.');
}
function ink(hex){const rgb=hex.slice(1).match(/../g).map(c=>parseInt(c,16)/255).map(v=>v<=.04045?v/12.92:((v+.055)/1.055)**2.4);return .2126*rgb[0]+.7152*rgb[1]+.0722*rgb[2]>.4?'#171322':'#ffffff';}
function finishPiece(p,b,measure){
 p.contentKind=b.kind;if(b.source)p.source=b.source;if(b.brandKit)p=applyBrand(p,b.brandKit,measure);
 for(const s of p.slides){const title=s.layers.find(l=>l.type==='text'&&(l.role==='title'||l.name==='Título')),body=s.layers.find(l=>l.type==='text'&&(l.role==='body'||l.name==='Conteúdo'));for(const l of [title,body]){if(!l)continue;const height=l===title&&body&&body.y>l.y?Math.max(20,body.y-l.y-32):Math.max(20,s.height*.91-l.y);l.size=fitCopy(l.text,l.w,height,l.font,l.size,measure);}}
 return p;
}
export function buildAIPiece(input,projectId,measure){
 const {brief:b,draft:d,images}=validateAIFile({version:1,...input});
 if(b.template){const p=fillTemplate(b.template,d,projectId,images);p.ai={provider:AI_NAMES[b.provider],generatedAt:new Date().toISOString()};for(const s of p.slides){const title=s.layers.find(l=>l.role==='title'),body=s.layers.find(l=>l.role==='body');for(const l of [title,body]){const height=l===title?Math.max(20,body.y-l.y-32):Math.max(20,s.height*.91-l.y);l.size=fitCopy(l.text,l.w,height,l.font,l.size,measure);}}return finishPiece(p,b,measure);}
 const p=newPiece(projectId,d.title,b.format,b.count);p.demo=false;p.caption=d.caption;
 p.ai={provider:AI_NAMES[b.provider],generatedAt:new Date().toISOString()};
 p.slides.forEach((s,i)=>{
  const w=s.width,h=s.height,m=Math.round(w*.08),width=w-2*m,hasImage=!!images[i],font=b.style==='editorial'?'Georgia':b.style==='impacto'?'Impact':'Arial',color=ink(b.bg);
  s.bg=b.bg;s.layers=[];
  const add=(text,y,height,start,name,opts={})=>s.layers.push(textLayer(text,{name,x:m,y:Math.round(y),w:width,font,size:fitCopy(text,width,height,opts.font||font,start,measure),lineHeight:1.15,color,...opts}));
  add(b.brand||'UMA IDEIA PARA COMPARTILHAR',h*.055,h*.045,22,'Marca',{font:'Arial',bold:false});
  if(hasImage)s.layers.push({id:crypto.randomUUID(),type:'image',name:`Imagem do slide ${i+1}`,src:images[i],x:m,y:Math.round(h*.13),w:width,h:Math.round(h*.33),zoom:1,offsetX:0,offsetY:0,flip:false,visible:true});
  add(d.slides[i].title,h*(hasImage?.51:.24),h*(hasImage?.18:.23),b.style==='impacto'?92:78,'Título');
  add(d.slides[i].body,h*(hasImage?.73:.53),h*(hasImage?.18:.29),38,'Conteúdo',{bold:false,font:'Arial'});
  add(`${String(i+1).padStart(2,'0')} / ${String(b.count).padStart(2,'0')}`,h*.94,h*.04,20,'Numeração',{font:'Arial',color:ink(b.bg),bold:false});
  // A narrow accent marker stays independently editable like all text elements.
  s.layers.push(textLayer('━━━━',{name:'Detalhe de cor',x:m,y:Math.round(h*.105),w:width,font:'Arial',size:20,color:b.accent}));
 });return finishPiece(p,b,measure);
}
