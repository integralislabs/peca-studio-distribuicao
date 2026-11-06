import {wrapText,sanitizeSVG} from './model.js';
const images=new Map();
export function loadImage(src) {
  if(!images.has(src)){
    const promise=new Promise((resolve,reject)=>{const img=new Image();img.onload=()=>resolve(img);img.onerror=()=>{images.delete(src);reject(new Error('Não foi possível ler uma das imagens. Substitua a imagem no editor.'));};img.src=src;});
    images.set(src,promise);if(images.size>100)images.delete(images.keys().next().value);
  }
  return images.get(src);
}
export function textLayout(ctx,layer) {
  ctx.font=`${layer.italic&&!layer.fontFaceExact?'italic ':''}${layer.bold&&!layer.fontFaceExact?'bold ':''}${layer.size}px "${layer.font}"`;
  ctx.letterSpacing=`${layer.letterSpacing||0}px`;
  return wrapText(layer.text,layer.w,t=>ctx.measureText(t).width);
}
export function layerHeight(ctx,layer){return layer.type!=='text'?layer.h:textLayout(ctx,layer).length*layer.size*layer.lineHeight;}
function cover(ctx,img,x,y,w,h,zoom=1,ox=0,oy=0,flip=false,radius=0) {
  ctx.save();ctx.beginPath();if(radius)ctx.roundRect(x,y,w,h,Math.min(radius,w/2,h/2));else ctx.rect(x,y,w,h);ctx.clip();
  const factor=Math.max(w/img.width,h/img.height)*zoom,iw=img.width*factor,ih=img.height*factor;
  ctx.translate(x+w/2+ox,y+h/2+oy);ctx.scale(flip?-1:1,1);ctx.drawImage(img,-iw/2,-ih/2,iw,ih);ctx.restore();
}
const drawVersion=new WeakMap();
export async function drawSlide(canvas,slide,{width=slide.width,selection=null}={}) {
  const version=(drawVersion.get(canvas)||0)+1;drawVersion.set(canvas,version);
  const vectorSrc=l=>'data:image/svg+xml;charset=utf-8,'+encodeURIComponent(sanitizeSVG(l.svg));
  const sources=[...slide.layers.filter(l=>l.type==='vector'&&l.visible).map(vectorSrc),slide.bgImage,...slide.layers.filter(l=>l.type==='image'&&l.visible).map(l=>l.src)].filter(Boolean);
  const loaded=new Map(await Promise.all(sources.map(async src=>[src,await loadImage(src)])));
  if(drawVersion.get(canvas)!==version)return;
  canvas.width=Math.round(width);canvas.height=Math.round(width*slide.height/slide.width);
  const ctx=canvas.getContext('2d');ctx.scale(canvas.width/slide.width,canvas.height/slide.height);
  ctx.fillStyle=slide.bg;ctx.fillRect(0,0,slide.width,slide.height);
  if(slide.bgImage)cover(ctx,loaded.get(slide.bgImage),0,0,slide.width,slide.height);
  for(const l of slide.layers){
    if(!l.visible)continue;
    ctx.save();ctx.globalAlpha=l.opacity??1;const lh=layerHeight(ctx,l);if(l.rotation){ctx.translate(l.x+l.w/2,l.y+lh/2);ctx.rotate(l.rotation*Math.PI/180);ctx.translate(-l.x-l.w/2,-l.y-lh/2);}
    if(l.type==='image')cover(ctx,loaded.get(l.src),l.x,l.y,l.w,l.h,l.zoom,l.offsetX,l.offsetY,l.flip,l.radius||0);
    else if(l.type==='vector')ctx.drawImage(loaded.get(vectorSrc(l)),l.x,l.y,l.w,l.h);
    else if(l.type==='shape')drawShape(ctx,l);
    else {
      const lines=textLayout(ctx,l);ctx.textBaseline='top';ctx.fillStyle=l.color;ctx.textAlign=l.align;
      const x=l.x+(l.align==='center'?l.w/2:l.align==='right'?l.w:0);
      lines.forEach((line,i)=>{const y=l.y+i*l.size*l.lineHeight;ctx.fillText(line,x,y);if(l.underline){const tw=ctx.measureText(line).width;ctx.fillRect(x-(l.align==='center'?tw/2:l.align==='right'?tw:0),y+l.size,tw,Math.max(1,l.size/22));}});
    }
    ctx.restore();
    if(l.id===selection){
      const h=layerHeight(ctx,l);ctx.save();if(l.rotation){ctx.translate(l.x+l.w/2,l.y+h/2);ctx.rotate(l.rotation*Math.PI/180);ctx.translate(-l.x-l.w/2,-l.y-h/2);}ctx.lineWidth=2.5*slide.width/canvas.width;ctx.strokeStyle='#bd8aff';ctx.setLineDash([8,5]);ctx.strokeRect(l.x-5,l.y-5,l.w+10,h+10);ctx.setLineDash([]);
      for(const [x,y]of [[l.x-5,l.y-5],[l.x+l.w+5,l.y-5],[l.x-5,l.y+h+5],[l.x+l.w+5,l.y+h+5]]){ctx.fillStyle='#f1dfff';ctx.fillRect(x-4,y-4,8,8);}ctx.restore();
    }
  }
  return canvas;
}
export async function pngBlob(slide) {const canvas=document.createElement('canvas');await drawSlide(canvas,slide);return new Promise((resolve,reject)=>canvas.toBlob(b=>b?resolve(b):reject(new Error('Falha ao exportar a imagem.')),'image/png'));}
export async function readImage(file) {
  if(!file||!['image/png','image/jpeg','image/webp'].includes(file.type))throw new Error('Escolha uma imagem PNG, JPG ou WebP.');
  if(file.size>20*1024*1024)throw new Error('A imagem deve ter até 20 MB.');
  const src=await new Promise((resolve,reject)=>{const r=new FileReader();r.onload=()=>resolve(r.result);r.onerror=()=>reject(new Error('Falha ao ler o arquivo.'));r.readAsDataURL(file);});
  const img=await loadImage(src);if(img.width*img.height>60e6)throw new Error('Imagem muito grande. Use uma imagem de até 60 megapixels.');
  const ratio=Math.min(1,2200/Math.max(img.width,img.height)),canvas=document.createElement('canvas');canvas.width=Math.max(1,Math.round(img.width*ratio));canvas.height=Math.max(1,Math.round(img.height*ratio));canvas.getContext('2d').drawImage(img,0,0,canvas.width,canvas.height);
  const data=canvas.toDataURL(file.type==='image/png'?'image/png':'image/jpeg',.9);if(data.length>8e6)throw new Error('A imagem ainda é muito pesada. Reduza o arquivo antes de importar.');
  return {src:data,width:canvas.width,height:canvas.height};
}
export function drawShape(ctx,l){
 ctx.beginPath();if(l.shape==='ellipse')ctx.ellipse(l.x+l.w/2,l.y+l.h/2,l.w/2,l.h/2,0,0,Math.PI*2);else if(l.radius)ctx.roundRect(l.x,l.y,l.w,l.h,Math.min(l.radius,l.w/2,l.h/2));else ctx.rect(l.x,l.y,l.w,l.h);
 let fill=l.fill;if(l.gradient){const a=l.gradient.angle*Math.PI/180,dx=Math.sin(a),dy=-Math.cos(a),n=(Math.abs(l.w*dx)+Math.abs(l.h*dy))/2,cx=l.x+l.w/2,cy=l.y+l.h/2;fill=ctx.createLinearGradient(cx-dx*n,cy-dy*n,cx+dx*n,cy+dy*n);for(const s of l.gradient.stops)fill.addColorStop(s.offset,s.color);}
 if(fill){ctx.fillStyle=fill;ctx.fill();}if(l.stroke&&l.strokeWidth){ctx.strokeStyle=l.stroke;ctx.lineWidth=l.strokeWidth;ctx.stroke();}
}
