import {clone,validateState} from './model.js';

/** Resize a composition, never a live library. Caller records one undo step. */
export function resizePiece(piece,width,height,{mode='contain',slideIndex=null}={}){
 if(piece.htmlDocument)throw Error('Redimensione o frame no HTML preservado; o Canvas é apenas a prévia.');
 if(![width,height].every(n=>Number.isInteger(n)&&n>=100&&n<=4096))throw Error('Use dimensões inteiras entre 100 e 4096 px.');
 if(!['contain','cover','scale'].includes(mode))throw Error('Modo de redimensionamento inválido.');
 if(!piece?.slides?.length||slideIndex!==null&&(!Number.isInteger(slideIndex)||!piece.slides[slideIndex]))throw Error('Peça ou slide inválido.');
 const next=clone(piece);
 for(const [i,s]of next.slides.entries()){
  if(slideIndex!==null&&i!==slideIndex)continue;
  const sx=width/s.width,sy=height/s.height,k=mode==='cover'?Math.max(sx,sy):Math.min(sx,sy),dx=(width-s.width*k)/2,dy=(height-s.height*k)/2;
  for(const l of s.layers){
   const x=mode==='scale'?sx:k,y=mode==='scale'?sy:k;
   l.x=l.x*x+(mode==='scale'?0:dx);l.y=l.y*y+(mode==='scale'?0:dy);l.w*=x;
   if(l.type==='image'){l.h*=y;l.offsetX*=x;l.offsetY*=y;if(l.radius!==undefined)l.radius*=Math.min(x,y);}
   else if(l.type==='text'){l.size*=Math.min(x,y);l.letterSpacing*=x;}
   else {l.h*=y;if(l.radius!==undefined)l.radius*=Math.min(x,y);if(l.strokeWidth!==undefined)l.strokeWidth*=Math.min(x,y);}
   if(l.type==='text'&&(l.size<8||l.size>400)||l.w>8192||Math.abs(l.x)>8192||Math.abs(l.y)>8192||l.type==='image'&&(l.h>8192||Math.abs(l.offsetX)>4096||Math.abs(l.offsetY)>4096))throw Error('O tamanho resultante ultrapassa os limites de um elemento. Ajuste a composição ou use uma escala menor.');
  }
  s.width=width;s.height=height;
 }
 next.format=width===height?'quadrado':height/width>1.5?'story':'feed';next.updatedAt=new Date().toISOString();next.demo=false;
 validateState({version:1,projects:[{id:next.projectId,name:'Resize',color:'#123456',folders:next.folderId?[{id:next.folderId,name:'Pasta'}]:[]}],pieces:[next]});
 return next;
}
