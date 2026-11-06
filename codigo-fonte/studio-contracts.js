export function checkBrand(kit,fonts){
 const fail=()=>{throw new Error('Kit de marca inválido: confira cores, fontes, logo e limites.');};
 if(!kit||typeof kit!=='object')fail();
 for(const [key,max]of [['name',120],['signature',160],['tone',300]])if(typeof kit[key]!=='string'||kit[key].length>max)fail();
 for(const key of ['bg','accent','text'])if(typeof kit[key]!=='string'||!/^#[a-f\d]{6}$/i.test(kit[key]))fail();
 if(!fonts.includes(kit.titleFont)||!fonts.includes(kit.bodyFont))fail();
 if(kit.logo!=null){const l=kit.logo;if(typeof l.src!=='string'||l.src.length>1_500_000||!/^data:image\/(png|jpeg|webp);base64,[a-z\d+/=\s]+$/i.test(l.src)||![l.width,l.height].every(n=>Number.isFinite(n)&&n>=1&&n<=2200))fail();}
 return {name:kit.name,signature:kit.signature,tone:kit.tone,bg:kit.bg,accent:kit.accent,text:kit.text,titleFont:kit.titleFont,bodyFont:kit.bodyFont,logo:kit.logo?{...kit.logo}:null};
}
export function youtubeURL(value){
 if(value==='')return '';if(typeof value!=='string'||value.length>600)throw new Error('Link de YouTube inválido.');
 let u;try{u=new URL(value);}catch{throw new Error('Informe um link completo do YouTube.');}
 if(u.protocol!=='https:'||u.username||u.password||u.port)throw new Error('Use um link HTTPS do YouTube.');
 const host=u.hostname.toLowerCase();let id;
 if(['youtu.be','www.youtu.be'].includes(host))id=u.pathname.slice(1);
 else if(['youtube.com','www.youtube.com','m.youtube.com'].includes(host))id=u.pathname==='/watch'?u.searchParams.get('v'):/^\/(shorts|embed)\/([^/]+)$/.exec(u.pathname)?.[2];
 if(!/^[a-zA-Z0-9_-]{11}$/.test(id||''))throw new Error('Link de vídeo do YouTube inválido.');return 'https://www.youtube.com/watch?v='+id;
}
export function checkCues(cues){
 if(!Array.isArray(cues)||!cues.length||cues.length>5000)throw new Error('A fonte deve ter de 1 a 5000 trechos.');let total=0,last=-1,mode=cues[0].start===null;
 for(const c of cues){if(!c||typeof c.text!=='string'||!c.text.trim()||c.text.length>3000)throw new Error('Trecho de transcrição inválido.');total+=c.text.length;if(total>150000)throw new Error('A transcrição deve ter até 150 mil caracteres de texto.');
  if(mode){if(c.start!==null||c.end!==null)throw new Error('Não misture trechos com e sem tempo.');}
  else{if(![c.start,c.end].every(n=>Number.isFinite(n)&&n>=0&&n<=86400)||c.end<c.start||c.start<last)throw new Error('Confira a ordem e os tempos dos trechos.');last=c.start;}
 }return cues;
}
export function checkReference(s){
 if(!s||typeof s.id!=='string'||!/^[a-z\d_-]{1,100}$/i.test(s.id)||typeof s.title!=='string'||!s.title.trim()||s.title.length>180||typeof s.text!=='string'||!s.text.trim()||s.text.length>10000)throw new Error('Referência de fonte inválida ou longa demais.');
 const url=youtubeURL(s.url);if(s.start===null&&s.end===null){}else if(![s.start,s.end].every(n=>Number.isFinite(n)&&n>=0&&n<=86400)||s.end<s.start)throw new Error('Tempo da referência inválido.');
 return {id:s.id,title:s.title,url,start:s.start,end:s.end,text:s.text};
}
