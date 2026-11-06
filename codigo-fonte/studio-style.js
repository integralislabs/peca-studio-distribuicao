import {clone,FONTS,wrapText} from './model.js';

export function validateStyle(style){
 if(!style||!['bg','text','accent'].every(k=>/^#[a-f\d]{6}$/i.test(style[k]))||!FONTS.includes(style.titleFont)||!FONTS.includes(style.bodyFont))throw new Error('Estilo inválido: confira cores e fontes.');
 return Object.fromEntries(['bg','text','accent','titleFont','bodyFont'].map(k=>[k,style[k]]));
}

export function applyStyle(piece,style,{slideIndex=null,measure=(text,font,size)=>text.length*size*.9}={}){
 const value=validateStyle(style);
 if(!piece?.slides?.length)throw new Error('Abra uma peça para aplicar o estilo.');
 if(slideIndex!==null&&(!Number.isInteger(slideIndex)||slideIndex<0||slideIndex>=piece.slides.length))throw new Error('Slide inválido.');
 const next=clone(piece);
 for(const [index,slide] of next.slides.entries()){
  if(slideIndex!==null&&slideIndex!==index)continue;
  slide.bg=value.bg;
  const texts=slide.layers.filter(l=>l.type==='text');
  const title=texts.find(l=>l.role==='title'||/título/i.test(l.name))||texts.find(l=>!l.role?.startsWith('brand')&&l.role!=='body');
  for(const layer of texts){
   const originalHeight=wrapText(layer.text,layer.w,t=>measure(t,layer.font,layer.size,layer)).length*layer.size*layer.lineHeight;
   layer.font=layer===title?value.titleFont:value.bodyFont;
   layer.color=/detalhe|destaque/i.test(layer.name)||layer.role==='accent'?value.accent:value.text;
   const available=Math.max(0,Math.min(originalHeight,slide.height-layer.y));
   const fits=size=>{const width=t=>measure(t,layer.font,size,{...layer,size}),lines=wrapText(layer.text,layer.w,width);return lines.length*size*layer.lineHeight<=available&&lines.every(line=>width(line)<=layer.w);};
   let size=layer.size;while(size>8&&!fits(size))size=Math.max(8,size-1);
   if(!fits(size))throw new Error('O texto não cabe com este estilo. Reduza o texto ou ajuste sua posição e largura.');
   layer.size=size;
  }
 }
 return next;
}
