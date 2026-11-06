import {youtubeURL} from './studio-contracts.js';
export const MAX_REFERENCE_CHARS=200000;
const safeText=value=>String(value??'').replace(/data:image\/[^\s"']+/gi,'[imagem local]');
const pick=(item,keys)=>Object.fromEntries(keys.filter(k=>item?.[k]!==undefined).map(k=>[k,typeof item[k]==='string'?safeText(item[k]):item[k]]).filter(([,v])=>v===null||['string','number','boolean'].includes(typeof v)));

export function referenceData(piece,project,folder){
 if(!piece||!Array.isArray(piece.slides)||!piece.slides.length||piece.slides.length>30)throw new Error('Referência inválida: confira os slides.');
 const data={version:1,purpose:'Referência editável para IA; nenhum envio automático.',project:pick(project||{id:piece.projectId},['id','name']),folder:pick(folder||project?.folders?.find(f=>f.id===piece.folderId)||{id:piece.folderId},['id','name']),piece:pick(piece,['id','projectId','folderId','parentPieceId','variationGroupId','versionLabel','title','channel','format','status','caption','angle']),slides:[]};
 for(const slide of piece.slides){
  if(!Array.isArray(slide.layers)||slide.layers.length>100)throw new Error('Referência excede o limite de elementos.');
  data.slides.push({...pick(slide,['id','width','height','bg']),backgroundImage:!!slide.bgImage,layers:slide.layers.map(layer=>({...pick(layer,['id','type','name','role','visible','x','y','w','h','text','font','size','color','bold','italic','underline','align','lineHeight','letterSpacing','zoom','offsetX','offsetY','flip','mask','radius','opacity']),...(layer.type==='image'?{localImage:true}:{})}))});
 }
 if(piece.source){let url='';try{url=youtubeURL(piece.source.url||'');}catch{}data.source={...pick(piece.source,['id','title','start','end','text']),url};}
 if(JSON.stringify(data).length>MAX_REFERENCE_CHARS)throw new Error('Referência excede o limite de 200 mil caracteres. Reduza o texto ou divida a peça.');
 return data;
}
export function referenceJSON(piece,project,folder){
 const json=JSON.stringify(referenceData(piece,project,folder),null,2);
 if(json.length>MAX_REFERENCE_CHARS)throw new Error('Referência excede o limite de 200 mil caracteres.');
 return json;
}
export function referenceText(piece,project,folder){
 const d=referenceData(piece,project,folder),p=d.piece;
 const lines=['REFERÊNCIA DA PEÇA',`Projeto: ${d.project.name||'Sem nome'} | ID: ${d.project.id||'—'}`,`Pasta: ${d.folder.name||'Sem pasta'} | ID: ${d.folder.id||'—'}`,`Peça: ${p.title} | ID: ${p.id}`,`Família: ${p.variationGroupId||p.parentPieceId||p.id} | Variação: ${p.versionLabel||'Original'}`,`Canal: ${p.channel} | Formato: ${p.format} | Estado: ${p.status}`,`Legenda / copy: ${p.caption||'Não informada'}`];
 for(const [i,s] of d.slides.entries()){
  lines.push('',`Slide ${i+1} | ID: ${s.id} | ${s.width} × ${s.height}px | Fundo: ${s.bg}${s.backgroundImage?' + imagem local':''}`);
  for(const l of s.layers)lines.push(`- ${l.type==='image'?'Imagem local':`Texto: ${l.text}`} | ${l.name} (${l.id}) | ${l.visible?'visível':'oculto'} | x=${l.x}, y=${l.y}, largura=${l.w}, opacidade=${l.opacity??1}${l.h!==undefined?', altura='+l.h:''}${l.type==='text'?` | ${l.font}, ${l.size}px, ${l.color}, ${l.align}, entrelinha=${l.lineHeight}, espaço=${l.letterSpacing}${l.bold?', negrito':''}${l.italic?', itálico':''}${l.underline?', sublinhado':''}`:` | máscara=${l.radius>0?(l.w===l.h&&l.radius>=l.w/2?'circular':'arredondada'):'retangular'}, zoom=${l.zoom}, deslocamento=${l.offsetX}/${l.offsetY}, espelhar=${l.flip}, raio=${l.radius||0}`}`);
 }
 if(d.source)lines.push('','FONTE',`${d.source.title} (${d.source.id})`,d.source.url,`Trecho: ${d.source.start??'sem tempo'} a ${d.source.end??'sem tempo'}`,d.source.text);
 lines.push('','INSTRUÇÃO EDITÁVEL','Use esta composição como referência. Preserve o sentido, confira a fonte e descreva as mudanças desejadas antes de produzir novas versões. Imagens locais devem ser fornecidas separadamente, quando desejado.');
 const text=lines.join('\n');if(text.length>MAX_REFERENCE_CHARS)throw new Error('Referência excede o limite de 200 mil caracteres.');return text;
}
