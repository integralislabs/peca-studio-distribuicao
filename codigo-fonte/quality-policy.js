const HASH_KEYS=['slideHash','referenceHash','blocksHash','reportHash'];
const normalized=text=>String(text??'').normalize('NFC').replace(/\s+/g,' ').trim();
const fraction=n=>Number.isFinite(n)&&n>=0&&n<=1;
export function evaluateQuality({metrics,blocks=[],slide,warnings=[],exceptions=[],hashes={}}={}){
 const failures=[],ids=new Set(),texts=(slide?.layers||[]).filter(l=>l.type==='text').map(l=>normalized(l.text));
 for(const block of blocks){
  const reasons=[],id=String(block.id),region=metrics?.regions?.filter(r=>String(r.id)===id);
  if(ids.has(id))reasons.push('Identificador de região duplicado');ids.add(id);
  if(region?.length!==1)reasons.push('Métricas da região ausentes ou duplicadas');
  else {const m=region[0];if(!fraction(m.foregroundIoU)||m.foregroundIoU<.85)reasons.push('IoU da máscara < 0,85 ou ausente');if(!fraction(m.pixelsWithin20)||m.pixelsWithin20<.90)reasons.push('Pixels dentro de 20 < 90% ou ausentes');}
  const at=texts.indexOf(normalized(block.text));if(!normalized(block.text)||at<0)reasons.push('Texto obrigatório ausente ou alterado');else texts.splice(at,1);
  for(const warning of warnings)if(warning?.regionId===id)reasons.push(warning.message||String(warning));
  if(reasons.length)failures.push({id,reasons});
 }
 const global=[];
 if(!blocks.length)global.push('Nenhuma região validável');
 if(metrics?.regions?.some(r=>!ids.has(String(r.id))))global.push('Métricas de regiões desconhecidas');
 for(const warning of warnings)if(!warning?.regionId||!ids.has(String(warning.regionId)))global.push(warning.message||String(warning));
 if(global.length)failures.push({id:'$global',reasons:global});
 const bound=exception=>exception&&typeof exception.reason==='string'&&exception.reason.trim().length>=8&&HASH_KEYS.every(k=>typeof hashes[k]==='string'&&hashes[k]&&exception[k]===hashes[k]);
 const unresolved=failures.filter(f=>!exceptions.some(e=>e.id===f.id&&bound(e)));
 const measurementsComplete=blocks.length>0&&blocks.every(b=>{const regions=metrics?.regions?.filter(r=>String(r.id)===String(b.id));return regions?.length===1&&fraction(regions[0].foregroundIoU)&&fraction(regions[0].pixelsWithin20);});
 const strictPass=failures.length===0&&measurementsComplete,allowed=unresolved.length===0&&measurementsComplete;
 return {allowed,strictPass,status:allowed?(strictPass?'passed':'exception-approved'):'blocked',failures,unresolved};
}
export function validateQualityReceipt(qa,currentHashes,context){
 if(qa?.schemaVersion!==2||!qa.reviewedAt||!HASH_KEYS.every(k=>currentHashes[k]&&qa[k]===currentHashes[k]))return false;
 const result=evaluateQuality({...context,metrics:qa.metrics,exceptions:qa.exceptions,hashes:currentHashes});
 return result.allowed&&qa.status===result.status;
}
