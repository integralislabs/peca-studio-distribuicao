/** Local fonts only. Data is carried in backups and piece manifests. */
export const BASE_FONTS=['Arial','Georgia','Trebuchet MS','Verdana','Impact','Courier New'];
export const fontKey=name=>String(name).normalize('NFKC').toLowerCase();
const reservedFonts=new Set(BASE_FONTS.map(fontKey));
const MAX=5*1024*1024;
export function validateFonts(fonts=[]){
 if(!Array.isArray(fonts)||fonts.length>32)throw new Error('Use até 32 fontes locais.');
 let total=0;const names=new Set();
 for(const f of fonts){
  if(!f||typeof f.name!=='string'||! /^[\p{L}\p{N}][\p{L}\p{N} _-]{0,79}$/u.test(f.name.normalize('NFKC'))||reservedFonts.has(fontKey(f.name))||names.has(fontKey(f.name)))throw new Error('Nome de fonte inválido ou duplicado.');names.add(fontKey(f.name));
  const m=/^data:font\/(ttf|otf|woff|woff2);base64,([A-Za-z0-9+/]+={0,2})$/.exec(f.data||'');
  if(!m||m[2].length%4||m[2].length>MAX*4/3+4)throw new Error('Dados da fonte inválidos ou maiores que 5 MB.');
  const b=Uint8Array.from(atob(m[2]),c=>c.charCodeAt(0));total+=b.length;
  const signature=String.fromCharCode(...b.slice(0,4));
  if(b.length<12||!(m[1]==='ttf'&&b[0]===0&&b[1]===1&&b[2]===0&&b[3]===0||m[1]==='otf'&&signature==='OTTO'||m[1]==='woff'&&signature==='wOFF'||m[1]==='woff2'&&signature==='wOF2'))throw new Error('Assinatura de fonte inválida.');
  if(total>20*1024*1024)throw new Error('Fontes limitadas a 20 MB por coleção.');
 }return structuredClone(fonts);
}
export const fontNames=(fonts=[])=>[...BASE_FONTS,...validateFonts(fonts).map(f=>f.name)];
export async function readFont(file){
 const ext=file?.name?.split('.').pop().toLowerCase();if(!['ttf','otf','woff','woff2'].includes(ext)||file.size>MAX)throw new Error('Escolha fonte TTF, OTF, WOFF ou WOFF2 de até 5 MB.');
 const bytes=new Uint8Array(await file.arrayBuffer());let binary='';for(let i=0;i<bytes.length;i+=32768)binary+=String.fromCharCode(...bytes.subarray(i,i+32768));
 const font={name:file.name.normalize('NFKC').replace(/\.[^.]+$/,'').replace(/[^\p{L}\p{N} _-]/gu,' ').trim().slice(0,80),data:`data:font/${ext};base64,${btoa(binary)}`};validateFonts([font]);return font;
}
const loaded=new Map();
export async function loadFonts(fonts=[]){
 validateFonts(fonts);if(typeof FontFace==='undefined')return fontNames(fonts);
 for(const f of fonts){const key=fontKey(f.name);if(loaded.get(key)?.data===f.data)continue;const face=new FontFace(f.name,`url("${f.data}")`);await face.load();const old=loaded.get(key);if(old)document.fonts.delete(old.face);document.fonts.add(face);loaded.set(key,{data:f.data,face});}
 return fontNames(fonts);
}
