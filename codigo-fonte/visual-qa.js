function finish(error,within,count){return {meanAbsoluteError:Math.round(error/(count*3)*10000)/10000,pixelsWithin20:within/count,pixelCount:count};}

export function comparePixels(reference,rendered){

 if(reference.length!==rendered.length||!reference.length||reference.length%4)throw new Error('Buffers RGBA incompatíveis.');

 let error=0,within=0;

 for(let i=0;i<reference.length;i+=4){let max=0;for(let c=0;c<3;c++){const delta=Math.abs(reference[i+c]-rendered[i+c]);error+=delta;max=Math.max(max,delta);}if(max<=20)within++;}

 return finish(error,within,reference.length/4);

}

const pause=()=>new Promise(resolve=>setTimeout(resolve,0));

async function regionMetrics(a,b,width,x,y,w,h){

 let error=0,within=0,processed=0;

 for(let row=y;row<y+h;row++){

  for(let col=x;col<x+w;col++){const i=(row*width+col)*4;let max=0;for(let c=0;c<3;c++){const delta=Math.abs(a[i+c]-b[i+c]);error+=delta;max=Math.max(max,delta);}if(max<=20)within++;}

  processed+=w;if(processed>=32768){processed=0;await pause();}

 }

 const crop=data=>{const out=new Uint8ClampedArray(w*h*4);for(let row=0;row<h;row++)out.set(data.subarray(((y+row)*width+x)*4,((y+row)*width+x+w)*4),row*w*4);return out;};

 return {...finish(error,within,w*h),...compareForegroundMasks(crop(a),crop(b),w,h)};

}



/** Pixel comparison is diagnostic only; it never grants manual approval. */

export async function compareVisualQA(reference,renderedCanvas,blocks){

 const image=await new Promise((resolve,reject)=>{const img=new Image();img.onload=()=>resolve(img);img.onerror=()=>reject(new Error('Não foi possível comparar a referência.'));img.src=reference.image;});

 const scale=Math.min(1,1024/Math.max(reference.width,reference.height));

 const width=Math.max(1,Math.round(reference.width*scale)),height=Math.max(1,Math.round(reference.height*scale));

 const raster=source=>{const c=document.createElement('canvas');c.width=width;c.height=height;const ctx=c.getContext('2d',{willReadFrequently:true});ctx.fillStyle='#ffffff';ctx.fillRect(0,0,width,height);ctx.drawImage(source,0,0,width,height);return ctx.getImageData(0,0,width,height).data;};

 const a=raster(image);await pause();const b=raster(renderedCanvas);await pause();

 const global=await regionMetrics(a,b,width,0,0,width,height),regions=[];

 for(const block of blocks){

  const x=Math.max(0,Math.min(width-1,Math.floor(block.x/reference.width*width))),y=Math.max(0,Math.min(height-1,Math.floor(block.y/reference.height*height)));

  const right=Math.max(x+1,Math.min(width,Math.ceil((block.x+block.w)/reference.width*width))),bottom=Math.max(y+1,Math.min(height,Math.ceil((block.y+block.h)/reference.height*height)));

  regions.push({id:block.id,text:block.text,sourceBox:{x:block.x,y:block.y,w:block.w,h:block.h},sampleBox:{x,y,w:right-x,h:bottom-y},...await regionMetrics(a,b,width,x,y,right-x,bottom-y)});await pause();

 }

 return {method:'RGB absolute difference, white alpha composite',resolution:{width,height,maxDimension:1024,sourceWidth:reference.width,sourceHeight:reference.height},threshold:20,pixelsWithin20Unit:'fraction 0..1 (all three RGB channels <=20)',global,regions,notice:'Amostragem redimensionada até 1024 px. Diferenças de fonte e antialiasing afetam os números; métricas não aprovam a arte.'};

}



/** Foreground is RGB distance >20 from the modal border color of each crop.

 * This is a measured heuristic, not OCR or a claim of exact segmentation. */

export function compareForegroundMasks(reference,rendered,width,height){

 if(reference.length!==width*height*4||rendered.length!==reference.length||width<1||height<1)throw Error('Caixa RGBA inválida');

 const mask=data=>{const counts=new Map();for(let y=0;y<height;y++)for(let x=0;x<width;x++)if(!x||!y||x===width-1||y===height-1){const i=(y*width+x)*4,key=[data[i],data[i+1],data[i+2]].join(',');counts.set(key,(counts.get(key)||0)+1);}const bg=[...counts].sort((a,b)=>b[1]-a[1])[0][0].split(',').map(Number);return Array.from({length:width*height},(_,n)=>Math.max(...bg.map((c,k)=>Math.abs(data[n*4+k]-c)))>20);};

 const a=mask(reference),b=mask(rendered);let intersection=0,union=0;for(let i=0;i<a.length;i++){if(a[i]&&b[i])intersection++;if(a[i]||b[i])union++;}

 return {foregroundIoU:union?intersection/union:0,foregroundIntersection:intersection,foregroundUnion:union,foregroundMethod:'modal-border RGB distance >20; empty union fails'};

}
