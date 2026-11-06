"""Quality workflow receipts, not authentication or trusted pixel attestation."""
import hashlib
import json
import math
import unicodedata
from decimal import Decimal

HASH_KEYS=('slideHash','referenceHash','blocksHash','reportHash')
def _canonical(value):
 if value is None:return 'null'
 if isinstance(value,bool):return 'true' if value else 'false'
 if isinstance(value,str):return json.dumps(value,ensure_ascii=False,separators=(',',':'))
 if isinstance(value,(int,float)):
  if not math.isfinite(value):return 'null'
  if value==0:return '0'
  number=repr(float(value)).lower()
  if 1e-6<=abs(value)<1e21:return format(Decimal(number),'f').rstrip('0').rstrip('.') if '.' in format(Decimal(number),'f') else format(Decimal(number),'f')
  mantissa,exp=number.split('e') if 'e' in number else (number,'0');mantissa=mantissa.removesuffix('.0');return mantissa+'e'+('+' if int(exp)>=0 else '-')+str(abs(int(exp)))
 if isinstance(value,list):return '['+','.join(_canonical(v) for v in value)+']'
 if isinstance(value,dict):
  keys=sorted(value,key=lambda k:k.encode('utf-16-be','surrogatepass'));numeric=[k for k in keys if k.isascii() and k.isdigit() and str(int(k))==k and int(k)<4294967295];keys=sorted(numeric,key=int)+[k for k in keys if k not in numeric]
  return '{'+','.join(_canonical(k)+':'+_canonical(value[k]) for k in keys)+'}'
 raise ValueError('Valor não serializável no recibo QA')
def image_qa_hash(value):return hashlib.sha256(_canonical(value).encode('utf-8')).hexdigest()
def _text(value):return ' '.join(unicodedata.normalize('NFC',str(value or '')).split())
def _fraction(value):return type(value) in (int,float) and math.isfinite(value) and 0<=value<=1

def assert_image_quality(piece):
 if not isinstance(piece,dict):raise ValueError('Peça inválida')
 if 'imageConversion' not in piece:return
 try:
  receipt=piece['imageConversion'];qa=receipt['qa'];report=receipt['report'];blocks=report['blocks'];slide=piece['slides'][0]
  hashes={'slideHash':image_qa_hash({'slide':slide,'fonts':piece.get('fonts',[])}),'referenceHash':image_qa_hash(receipt['reference']),'blocksHash':image_qa_hash(blocks),'reportHash':image_qa_hash(report)}
  if qa.get('schemaVersion')!=2 or not qa.get('reviewedAt') or any(qa.get(k)!=v for k,v in hashes.items()):raise ValueError('Revisão QA ausente, antiga ou desatualizada')
  regions=qa['metrics']['regions'];warnings=report.get('warnings',[]);exceptions=qa.get('exceptions',[]);texts=[_text(l.get('text')) for l in slide.get('layers',[]) if l.get('type')=='text'];failures=[];ids=set()
  if not blocks:raise ValueError('Nenhuma região validável')
  for block in blocks:
   region_id=str(block['id']);matches=[r for r in regions if str(r.get('id'))==region_id]
   if len(matches)!=1 or not all(_fraction(matches[0].get(k)) for k in ('foregroundIoU','pixelsWithin20')):raise ValueError('Métricas incompletas não admitem exceção')
   m=matches[0];failed=region_id in ids or m['foregroundIoU']<.85 or m['pixelsWithin20']<.90;ids.add(region_id);text=_text(block.get('text'))
   if not text or text not in texts:failed=True
   else:texts.remove(text)
   if any(isinstance(w,dict) and w.get('regionId')==region_id for w in warnings):failed=True
   if failed:failures.append(region_id)
  if any(str(r.get('id')) not in ids for r in regions) or any(not isinstance(w,dict) or not w.get('regionId') or str(w['regionId']) not in ids for w in warnings):failures.append('$global')
  for region_id in failures:
   if not any(e.get('id')==region_id and isinstance(e.get('reason'),str) and len(e['reason'].strip())>=8 and all(e.get(k)==v for k,v in hashes.items()) for e in exceptions):raise ValueError('Região QA bloqueada: '+region_id)
  if qa.get('status')!=('exception-approved' if failures else 'passed'):raise ValueError('Status QA incompatível com os critérios')
 except (KeyError,IndexError,TypeError,AttributeError) as error:raise ValueError('Recibo QA malformado') from error
