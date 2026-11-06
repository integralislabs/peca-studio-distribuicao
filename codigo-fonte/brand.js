import {clone,FONTS,textLayer,uid,wrapText} from './model.js';
import {checkBrand} from './studio-contracts.js';
export const defaultBrand=(name='')=>({name,signature:'',tone:'Claro e próximo',bg:'#171322',accent:'#b8e38b',text:'#ffffff',titleFont:'Georgia',bodyFont:'Arial',logo:null});
export const validateBrandKit=kit=>checkBrand(kit,FONTS);
export function applyBrand(piece,kit,measure=(text,font,size)=>text.length*size*.9){
 const b=validateBrandKit(kit),p=clone(piece);p.demo=false;
 for(const s of p.slides){
  s.bg=b.bg;const w=s.width,h=s.height,m=Math.round(w*.08);
  const old=s.layers.filter(l=>l.role?.startsWith('brand'));
  s.layers=s.layers.filter(l=>!l.role?.startsWith('brand'));
  let first=true;
  for(const l of s.layers){if(l.type!=='text')continue;const title=l.role==='title'||/título/i.test(l.name)||first;
   l.font=title?b.titleFont:b.bodyFont;l.color=/detalhe|destaque/i.test(l.name)?b.accent:b.text;first=false;
   if(l.name==='Marca'){l.text=b.name;l.font=b.bodyFont;l.size=Math.min(l.size,26);l.x=m+(b.logo?Math.round(w*.16):0);l.w=w-l.x-m;}
   if(l.name==='Numeração'){l.x=Math.round(w*.78);l.w=Math.round(w*.14);l.align='right';}
  }
  const add=(role,layer)=>{layer.role=role;layer.id=old.find(l=>l.role===role)?.id||layer.id;s.layers.push(layer);};
  if(!s.layers.some(l=>l.type==='text'&&l.name==='Marca'))add('brandName',textLayer(b.name,{name:'Marca',x:m+(b.logo?Math.round(w*.16):0),y:Math.round(h*.05),w:Math.round(w*(b.logo?.66:.84)),size:22,font:b.bodyFont,color:b.text,bold:false}));
  if(b.logo){const maxW=w*.13,maxH=h*.065,scale=Math.min(maxW/b.logo.width,maxH/b.logo.height);add('brandLogo',{id:uid(),type:'image',name:'Logo da marca',src:b.logo.src,x:m,y:Math.round(h*.035),w:Math.max(1,Math.round(b.logo.width*scale)),h:Math.max(1,Math.round(b.logo.height*scale)),zoom:1,offsetX:0,offsetY:0,flip:false,visible:true});}
  if(b.signature)add('brandSignature',textLayer(b.signature,{name:'Assinatura',x:m,y:Math.round(h*.94),w:Math.round(w*.65),size:18,font:b.bodyFont,color:b.text,bold:false}));
  for(const l of s.layers.filter(l=>l.type==='text'&&(l.name==='Marca'||l.role==='brandSignature'))){const height=l.role==='brandSignature'?h*.05:h*.065;for(let size=l.size;size>=8;size--){if(wrapText(l.text,l.w,t=>measure(t,l.font,size)).length*size*l.lineHeight<=height){l.size=size;break;}if(size===8)throw new Error('Nome ou assinatura da marca não cabe. Reduza o texto.');}}
  if(s.layers.length>100)throw new Error('A marca excederia 100 elementos neste slide. Remova elementos antes de aplicar.');
 }return p;
}
