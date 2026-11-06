import {importPackage,exportPackage} from '../packages.js';
const results=[];
async function test(name,fn){try{await fn();results.push({name,ok:true});}catch(e){results.push({name,ok:false,error:e.message});}}
const assert=(ok,msg)=>{if(!ok)throw Error(msg);};
const make=(html,assets=[])=>new Map([['index.html',new File([html],'index.html')],...assets]);
await test('external CSS, positioned text, local raster, circular mask, inert script',async()=>{
 globalThis.packageScriptExecuted=false;
 const html=`<title>Teste externo</title><style>.slide{width:1080px;height:1920px;background:#123456}.heading{left:40px;top:70px;width:800px;font-size:72px;color:#ff0000;font-family:Georgia}</style><section class="slide"><h1 class="heading">Olá &amp; texto</h1><img src="assets/picture.png" style="left:10px;top:20px;width:200px;height:200px;border-radius:50%"><script>globalThis.packageScriptExecuted=true<\/script></section>`;
 const {piece,warnings}=await importPackage(make(html,[['assets/picture.png',new File([Uint8Array.from(atob('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+aHnQAAAAASUVORK5CYII='),c=>c.charCodeAt(0))],'picture.png')]]),'project');
 assert(piece.format==='story','format');assert(piece.slides[0].bg==='#123456','background');const [text,image]=piece.slides[0].layers;
 assert(text.text==='Olá & texto'&&text.x===40&&text.size===72&&text.font==='Georgia'&&text.color==='#ff0000','text/style');assert(image.radius===100&&image.w===200,'image mask');assert(!globalThis.packageScriptExecuted,'script executed');assert(warnings.some(w=>w.includes('Scripts')),'script warning');
 const round=await importPackage(new Map((await exportPackage(piece)).map(f=>[f.name,new File([f.bytes],f.name)])),'project');assert(round.piece.slides[0].layers[1].radius===100,'roundtrip mask');
});
await test('missing image is visible warning',async()=>{const r=await importPackage(make('<div class="slide"><img src="missing.png"></div>'),'project');assert(r.warnings.some(w=>w.includes('ausente')),'missing asset warning');});
await test('external image scheme rejected without fetch',async()=>{let rejected=false;try{await importPackage(make('<div class="slide"><img src="https://example.invalid/a.png"></div>'),'project');}catch{rejected=true;}assert(rejected,'external path accepted');});
await test('traversal image rejected',async()=>{let rejected=false;try{await importPackage(make('<div class="slide"><img src="../secret.png"></div>'),'project');}catch{rejected=true;}assert(rejected,'traversal accepted');});
await test('incoherent dimensions rejected',async()=>{let rejected=false;try{await importPackage(make('<div class="slide" style="width:Infinity;height:500px"><p>Texto</p></div>'),'project');}catch{rejected=true;}assert(rejected,'infinite width accepted');});
await test('local linked CSS is read from selected files without network',async()=>{
 const r=await importPackage(make('<link rel="stylesheet" href="./theme.css"><div class="slide"><p>Local CSS</p></div>',[['theme.css',new File(['.slide{width:600px;height:600px;background:#123456} p{left:70px;font-size:42px;color:#abcdef}'],'theme.css')]]),'project');assert(r.piece.slides[0].width===600&&r.piece.slides[0].layers[0].x===70&&r.piece.slides[0].layers[0].size===42,'linked CSS ignored');
});
await test('linked CSS external URLs are rejected and missing CSS reported',async()=>{
 let rejected=false;try{await importPackage(make('<link rel="stylesheet" href="https://example.invalid/a.css"><div class="slide"><p>X</p></div>'),'project');}catch{rejected=true;}assert(rejected,'external CSS accepted');const r=await importPackage(make('<link rel="stylesheet" href="missing.css"><div class="slide"><p>X</p></div>'),'project');assert(r.warnings.some(w=>w.includes('Stylesheet ausente')),'missing CSS silent');
});
await test('browser rejects truncated raster despite a valid PNG signature',async()=>{
 const bytes=Uint8Array.of(137,80,78,71,13,10,26,10,...Array(16).fill(0));let rejected=false;try{await importPackage(make('<div class="slide"><img src="bad.png"></div>',[['bad.png',new File([bytes],'bad.png')]]),'project');}catch{rejected=true;}assert(rejected,'truncated image accepted');
});
await test('omitted HTML dimensions use safe defaults, including text/image attrs',async()=>{
 const r=await importPackage(make('<div class="slide"><p>Sem dimensões</p><img src="one.png"></div>',[['one.png',new File([Uint8Array.from(atob('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+aHnQAAAAASUVORK5CYII='),c=>c.charCodeAt(0))],'one.png')]]),'project');const s=r.piece.slides[0];assert(s.width===1080&&s.height===1350,'slide defaults');assert(s.layers[0].w===1080&&s.layers[0].x===0,'text defaults');assert(s.layers[1].w===1080&&s.layers[1].h===1080,'image defaults');
});
await test('HTML edited alongside manifest is read only after an explicit preference',async()=>{
 const original=await importPackage(make('<title>Fonte explícita</title><div class="slide"><p>Texto do manifesto</p></div>'),'project');
 const selected=new Map((await exportPackage(original.piece)).map(f=>[f.name,new File([f.bytes],f.name)]));
 selected.set('index.html',new File([(await selected.get('index.html').text()).replace('Texto do manifesto','HTML alterado pelo usuário')],'index.html'));
 const standard=await importPackage(selected,'project'),edited=await importPackage(selected,'project',{preferHTML:true});
 assert(standard.piece.slides[0].layers[0].text==='Texto do manifesto','default stopped preserving manifest');assert(edited.piece.slides[0].layers[0].text==='HTML alterado pelo usuário','explicit HTML edit ignored');assert(edited.warnings.some(w=>w.includes('limitada')),'conversion warning missing');
 selected.delete('index.html');let rejected=false;try{await importPackage(selected,'project',{preferHTML:true});}catch{rejected=true;}assert(rejected,'HTML mode accepted manifest without HTML');
});
globalThis.packageQA={passed:results.filter(x=>x.ok).length,total:results.length,results};document.querySelector('#result').textContent=JSON.stringify(globalThis.packageQA,null,2);
