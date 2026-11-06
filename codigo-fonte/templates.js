import {clone,uid,duplicatePiece,duplicateSlide,textLayer,validateState} from './model.js';
export const validateTemplate=t=>validateState({version:1,projects:[],pieces:[],templates:[t]}).templates[0];
export function saveTemplate(piece,name){
 if(typeof name!=='string'||!name.trim()||name.length>120)throw new Error('Dê um nome ao modelo, com até 120 caracteres.');
 const snapshot=clone(piece);delete snapshot.source;delete snapshot.ai;snapshot.caption='';
 return {id:uid(),name:name.trim(),snapshot,createdAt:new Date().toISOString()};
}
export function useTemplate(template,projectId){const p=duplicatePiece(template.snapshot);p.projectId=projectId;p.folderId=null;p.title=template.name;p.status='Rascunho';delete p.source;delete p.ai;return p;}
export function fillTemplate(template,draft,projectId,images=[]){
 const p=useTemplate(template,projectId);p.title=draft.title;p.caption=draft.caption;p.slides=draft.slides.map((copy,i)=>{
  const s=duplicateSlide(template.snapshot.slides[i%template.snapshot.slides.length]),texts=s.layers.filter(l=>l.type==='text'&&l.visible&&!l.role?.startsWith('brand')&&!['Marca','Assinatura','Numeração','Detalhe de cor'].includes(l.name));
  let title=texts.find(l=>l.role==='title'||/título/i.test(l.name))||texts[0],body=texts.find(l=>l!==title&&(l.role==='body'||/conteúdo|corpo/i.test(l.name)))||texts.find(l=>l!==title);
  if(!title){title=textLayer('',{name:'Título',x:s.width*.08,y:s.height*.25,w:s.width*.84,size:64});s.layers.push(title);}
  if(!body){body=textLayer('',{name:'Conteúdo',x:s.width*.08,y:s.height*.62,w:s.width*.84,size:36,bold:false});s.layers.push(body);}
  title.text=copy.title;title.role='title';body.text=copy.body;body.role='body';
  if(images[i]){const target=s.layers.find(l=>l.type==='image'&&l.role!=='brandLogo');if(target)target.src=images[i];else{s.layers.unshift({id:uid(),name:'Imagem do slide '+(i+1),type:'image',src:images[i],x:s.width*.08,y:s.height*.13,w:s.width*.84,h:s.height*.33,zoom:1,offsetX:0,offsetY:0,flip:false,visible:true});title.y=s.height*.51;body.y=s.height*.73;}}
  const number=s.layers.find(l=>l.type==='text'&&l.name==='Numeração');if(number)number.text=`${i+1} / ${draft.slides.length}`;
  if(s.layers.length>100)throw new Error('O modelo não tem espaço para adicionar os textos. Remova elementos antes de usá-lo com IA.');return s;
 });return p;
}
