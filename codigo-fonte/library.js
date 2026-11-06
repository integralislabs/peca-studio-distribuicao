import {clone,duplicatePiece} from './model.js';
export const familyId=p=>p.variationGroupId||p.id;
export function createVariation(piece,pieces){
 const group=familyId(piece),members=pieces.filter(p=>familyId(p)===group),next=1+Math.max(1,...members.map(p=>Number(/^v(\d+)$/i.exec(p.versionLabel||'')?.[1]||1)));
 const original={...clone(piece),variationGroupId:group,versionLabel:piece.versionLabel||'v1'},variation=duplicatePiece(piece);
 Object.assign(variation,{variationGroupId:group,parentPieceId:piece.id,versionLabel:'v'+next,title:(piece.title.replace(/ · v\d+$/,'')+' · v'+next).slice(0,180),status:'Rascunho'});delete variation.publishedAt;return {original,variation};
}
export function libraryStats(pieces){let published=0;const angles=new Set();for(const p of pieces){if(p.status==='Publicado')published++;if(p.angle?.trim())angles.add(p.angle.trim().normalize('NFD').replace(/[\u0300-\u036f]/g,'').toLowerCase());}return {total:pieces.length,published,pipeline:pieces.length-published,angles:angles.size};}
