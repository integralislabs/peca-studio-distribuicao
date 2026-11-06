"""Independent, self-contained HTML artwork contract. No scripts, navigation or remote assets."""
import base64, copy, hashlib, html, json, math, os, re, shutil, subprocess, tempfile, time
from html.parser import HTMLParser
from pathlib import Path

CSP="default-src 'none'; script-src 'none'; style-src 'unsafe-inline'; img-src data:; font-src data:; connect-src 'none'; frame-src 'none'; object-src 'none'; base-uri 'none'; form-action 'none'"
TAGS=set('html head body title meta style div section article main header footer aside h1 h2 h3 h4 h5 h6 p span b strong em i u s small sup sub br hr img figure figcaption ul ol li table tbody thead tr td th svg g path rect circle ellipse line polyline polygon text tspan defs lineargradient radialgradient stop clippath mask pattern use'.split())
VOID={'br','hr','img','meta'}
KEY=re.compile(r'[A-Za-z0-9_.:-]{1,100}\Z')
DATA=re.compile(r'data:(?:image/(?:png|jpeg|webp)|font/(?:ttf|otf|woff2?));base64,[A-Za-z0-9+/=\s]+\Z')

def _asset(value):
 try:
  import io
  header,payload=value.split(',',1);raw=base64.b64decode(re.sub(r'\s','',payload),validate=True)
  if len(raw)>8_000_000:raise ValueError('Ativo HTML maior que 8 MB.')
  if header.startswith('data:font/'):
   from font_pdf import _decode
   _decode(raw)
  else:
   from PIL import Image
   with Image.open(io.BytesIO(raw)) as image:
    if image.width*image.height>60_000_000:raise ValueError('Imagem HTML acima de 60 megapixels.')
    expected={'data:image/png;base64':'PNG','data:image/jpeg;base64':'JPEG','data:image/webp;base64':'WEBP'}
    if image.format!=expected[header]:raise ValueError('Tipo de imagem HTML divergente.')
    image.verify()
 except Exception as exc:raise ValueError('Imagem ou fonte incorporada inválida no HTML.') from exc

def _css(value):
 if re.search(r'@import|expression\s*\(|image-set\s*\(|-moz-binding|behavior\s*:|[\\\x00-\x08]',value,re.I):raise ValueError('CSS ativo ou importação externa não permitido.')
 for item in re.findall(r'url\(\s*[\"\']?([^\)\"\']+)',value,re.I):
  if not DATA.fullmatch(item.strip()) and not re.fullmatch(r'#[A-Za-z_][\w-]*',item.strip()):raise ValueError('Use apenas imagens/fontes locais incorporadas no HTML.')
  if DATA.fullmatch(item.strip()):_asset(item.strip())

def _number(value,lo,hi):
 try:n=float(value)
 except (TypeError,ValueError):raise ValueError('Número de controle inválido.')
 if not math.isfinite(n) or not lo<=n<=hi:raise ValueError('Valor fora dos limites do controle.')
 return n

class ArtworkParser(HTMLParser):
 def __init__(self,texts=None,controls=None):
  super().__init__(convert_charrefs=True);self.out=[];self.stack=[];self.editables=[];self.controls=[];self.frames=[];self.keys=set();self.texts=texts or {};self.values=controls or {};self.css=[];self.nodes=0
 def handle_decl(self,decl):
  if decl.lower()!='doctype html':raise ValueError('Declaração HTML inválida.')
  # A single canonical doctype is emitted first, before the CSP/reset.
 def handle_comment(self,text):pass
 def handle_starttag(self,tag,attrs):
  self.nodes+=1
  if tag not in TAGS or self.nodes>3000:raise ValueError('HTML contém componente ativo/não suportado ou muitos elementos: '+tag)
  a=dict(attrs)
  if tag=='meta':
   if a.get('http-equiv','').lower()=='content-security-policy' and a.get('content')==CSP:return
   if set(a)=={'charset'} or a.get('name')=='viewport':return
   raise ValueError('Metadado HTML ativo ou não suportado.')
  if len(a)!=len(attrs):raise ValueError('Atributo HTML duplicado.')
  for k,v in attrs:
   if k.lower().startswith('on') or k in ('srcdoc','srcset','action','formaction','ping','target','background','contenteditable','autofocus'):raise ValueError('Atributo HTML ativo não permitido.')
   if k in ('src','href','xlink:href') and not (DATA.fullmatch(v or '') or tag in ('use',) and re.fullmatch(r'#[A-Za-z_][\w-]*',v or '')):raise ValueError('Ativo ausente ou URL externa: incorpore o arquivo local.')
   if k in ('src','href','xlink:href') and DATA.fullmatch(v or ''):_asset(v)
   if k=='style':
    _css(v or '');a[k]=self.adjust_css(v or '');self.css.append(a[k])
  key=a.get('data-editable');entry=None
  if key is not None:
   if not KEY.fullmatch(key) or key in self.keys or any(n.get('editable') for n in self.stack):raise ValueError('Chave editável inválida, repetida ou aninhada.')
   self.keys.add(key);entry={'key':key,'type':'image' if tag=='img' else 'text','value':a.get('src','') if tag=='img' else ''};self.editables.append(entry)
   if key in self.texts:
    value=self.texts[key]
    if not isinstance(value,str) or len(value)>8_000_000:raise ValueError('Conteúdo editável inválido.')
    if tag=='img':
     if not re.fullmatch(r'data:image/(png|jpeg|webp);base64,[A-Za-z0-9+/=\s]+',value):raise ValueError('Imagem editável deve ser PNG/JPEG/WebP incorporada.')
     _asset(value)
     a['src']=value;entry['value']=value
    elif len(value)>10000:raise ValueError('Texto limitado a 10000 caracteres.')
  if 'data-adjust' in a:
   variable=a['data-adjust']
   if not re.fullmatch(r'--[A-Za-z][\w-]{0,80}',variable or '') or any(c['variable']==variable for c in self.controls):raise ValueError('Use data-adjust="--variavel" único e ligado ao CSS.')
   unit=a.get('data-unit','px')
   if unit not in ('px','%','deg','em','rem',''):raise ValueError('Unidade CSS inválida.')
   lo=_number(a.get('data-min',-4096),-10000,10000);hi=_number(a.get('data-max',4096),lo,10000)
   self.controls.append({'variable':variable,'label':a.get('data-label',variable),'min':lo,'max':hi,'unit':unit})
  if 'data-export-frame' in a or 'data-slide' in a or 'slide' in a.get('class','').split():
   width=_number(a.get('data-width',a.get('width',1080)),100,4096);height=_number(a.get('data-height',a.get('height',1350)),100,4096)
   self.frames.append({'width':int(width),'height':int(height),'label':a.get('data-label','Frame '+str(len(self.frames)+1))})
   a['data-peca-frame-index']=str(len(self.frames)-1)
  if self.stack and self.stack[-1].get('editable') and self.stack[-1]['editable']['type']=='text':raise ValueError('Texto data-editable deve ser um elemento de texto sem filhos; use chaves separadas por trecho.')
  self.out.append('<'+tag+''.join(' '+k+('="'+html.escape(str(v),quote=True)+'"' if v is not None else '') for k,v in a.items())+'>')
  if tag not in VOID:self.stack.append({'tag':tag,'editable':entry})
  if entry and tag!='img' and key in self.texts:self.out.append(html.escape(self.texts[key]));entry['value']=self.texts[key]
 def handle_startendtag(self,tag,attrs):
  self.handle_starttag(tag,attrs)
  if tag not in VOID:self.handle_endtag(tag)
 def handle_endtag(self,tag):
  if tag in VOID:return
  if not self.stack or self.stack[-1]['tag']!=tag:raise ValueError('Fechamento HTML inconsistente: '+tag)
  self.stack.pop();self.out.append('</'+tag+'>')
 def handle_data(self,value):
  if self.stack and self.stack[-1]['tag']=='style':_css(value);value=self.adjust_css(value);self.css.append(value);self.out.append(value);return
  entry=self.stack[-1].get('editable') if self.stack else None
  if entry:
   if entry['key'] in self.texts:return
   entry['value']+=value
  self.out.append(html.escape(value))
 def adjust_css(self,value):
  for variable,n in self.values.items():
   if not re.fullmatch(r'--[A-Za-z][\w-]{0,80}',variable):raise ValueError('Controle inválido.')
   # Unit comes from the explicitly declared control, found anywhere in the source.
   spec=self.control_specs.get(variable,{})
   number=_number(n,float(spec.get('data-min',-4096)),float(spec.get('data-max',4096)))
   unit=spec.get('data-unit','px')
   if unit not in ('px','%','deg','em','rem',''):raise ValueError('Unidade CSS inválida.')
   value=re.sub(r'(?<![\w-])'+re.escape(variable)+r'\s*:\s*[^;}]+',variable+':'+format(number,'g')+unit+' !important',value)
  return value

def prepare_document(source,texts=None,controls=None):
 if not isinstance(source,str) or not source.strip() or len(source)>20_000_000:raise ValueError('HTML deve ter até 20 MB.')
 parser=ArtworkParser(texts,controls)
 # Parse once without changes to collect the declared scope-independent control units.
 first=ArtworkParser();first.control_specs={};first.feed(source);first.close()
 parser.control_specs={c['variable']:{'data-unit':c['unit'],'data-min':c['min'],'data-max':c['max']} for c in first.controls}
 try:parser.feed(source);parser.close()
 except (RecursionError,AssertionError) as exc:raise ValueError('HTML inválido.') from exc
 if parser.stack:raise ValueError('Feche todos os elementos HTML.')
 if not parser.frames or len(parser.frames)>30:raise ValueError('Use de 1 a 30 elementos data-export-frame.')
 if set(texts or {})-parser.keys:raise ValueError('Chave editável desconhecida.')
 css='\n'.join(parser.css)
 for control in parser.controls:
  if not re.search(r'var\(\s*'+re.escape(control['variable'])+r'\s*[,)]',css):raise ValueError('Controle sem variável CSS conectada: '+control['variable'])
  values=re.findall(r'(?<![\w-])'+re.escape(control['variable'])+r'\s*:\s*([+-]?(?:\d*\.)?\d+)',css)
  control['value']=float(values[-1]) if values else None
 if set(controls or {})-{c['variable'] for c in parser.controls}:raise ValueError('Controle desconhecido.')
 output=''.join(parser.out)
 if controls:
  rules=[]
  for c in parser.controls:
   if c['variable'] in controls:
    value=_number(controls[c['variable']],c['min'],c['max']);rules.append(c['variable']+':'+format(value,'g')+c['unit']+' !important')
  style='<style>:root{'+ ';'.join(rules)+'}</style>'
  output=output.replace('</head>',style+'</head>',1) if '</head>' in output else style+output
 reset='<style>html,body{margin:0!important;padding:0!important}</style>'
 output=output.replace(reset,'')
 output='<!doctype html><meta http-equiv="Content-Security-Policy" content="'+html.escape(CSP,quote=True)+'">'+reset+output
 # Re-read final declarations after a changed control so metadata matches the saved HTML.
 if controls:
  for c in parser.controls:
   if c['variable'] in controls:c['value']=float(controls[c['variable']])
 return {'version':1,'html':output,'editables':parser.editables,'controls':parser.controls,'frames':parser.frames,'sha256':hashlib.sha256(output.encode()).hexdigest()}

def validate_document(doc):
 if not isinstance(doc,dict) or doc.get('version')!=1:raise ValueError('Documento HTML inválido.')
 actual=prepare_document(doc.get('html'))
 if actual!=doc:raise ValueError('Metadados ou hash HTML inconsistentes.')
 return actual

def update_document(doc,texts=None,controls=None):
 validate_document(doc)
 return prepare_document(doc['html'],texts,controls)

def sandbox_html(doc):
 validate_document(doc)
 return doc['html']

def render_document(doc,format='png',frame=0):
 """Render actual HTML in installed Chromium; never execute the source as application code."""
 validate_document(doc)
 if format not in ('png','jpeg','pdf','html') or type(frame) is not int or not 0<=frame<len(doc['frames']):raise ValueError('Formato/frame HTML inválido.')
 if format=='html':return doc['html'].encode(),'text/html'
 edge=next((Path(p) for p in [r'C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe',r'C:\Program Files\Microsoft\Edge\Application\msedge.exe'] if Path(p).is_file()),None)
 if edge is None:raise ValueError('Render HTML precisa do Microsoft Edge instalado.')
 dimensions=doc['frames'][frame]
 with tempfile.TemporaryDirectory(prefix='peca-html-',ignore_cleanup_errors=True) as tmp:
  root=Path(tmp);page=root/'art.html';out=root/('art.pdf' if format=='pdf' else 'art.png')
  # Hide other frames without JavaScript. Same HTML remains the source for preview/export.
  css=f'<style>html,body{{margin:0!important;padding:0!important;background:transparent!important}}@page{{size:{dimensions["width"]}px {dimensions["height"]}px;margin:0}}'
  if format!='pdf':css+=f'[data-peca-frame-index]:not([data-peca-frame-index="{frame}"]){{display:none!important}}'
  else:
   css+='[data-peca-frame-index]{break-after:page;break-inside:avoid}'
   for i,f in enumerate(doc['frames']):css+=f'@page frame{i}{{size:{f["width"]}px {f["height"]}px;margin:0}}[data-peca-frame-index="{i}"]{{page:frame{i}}}'
  css+='</style>'
  page.write_text(sandbox_html(doc)+css,encoding='utf-8')
  command=[str(edge),'--headless=new','--disable-gpu','--no-first-run','--no-default-browser-check','--hide-scrollbars','--disable-extensions','--disable-background-networking','--allow-file-access-from-files','--user-data-dir='+str(root/'profile'),'--virtual-time-budget=1500','--run-all-compositor-stages-before-draw',f'--window-size={dimensions["width"]},{dimensions["height"]}']
  command+=['--print-to-pdf='+str(out),'--no-pdf-header-footer'] if format=='pdf' else ['--screenshot='+str(out)]
  try:result=subprocess.run(command+[page.as_uri()],capture_output=True,timeout=40,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
  except (OSError,subprocess.TimeoutExpired) as exc:raise ValueError('Render HTML não concluiu. Tente novamente.') from exc
  # Windows' Edge launcher may return before its Chromium child writes the result.
  deadline=time.monotonic()+30;previous=None;stable=0
  while result.returncode==0 and time.monotonic()<deadline:
   size=out.stat().st_size if out.exists() else 0
   stable=stable+1 if size and size==previous else 0
   if stable>=3:break
   previous=size;time.sleep(.1)
  if result.returncode or not out.is_file():raise ValueError('Microsoft Edge não gerou a exportação HTML.')
  if format=='jpeg':
   from PIL import Image
   import io
   buffer=io.BytesIO();Image.open(out).convert('RGB').save(buffer,'JPEG',quality=95);return buffer.getvalue(),'image/jpeg'
  return out.read_bytes(),'application/pdf' if format=='pdf' else 'image/png'

def print_document(doc,options):
 """Preserve Chromium vector text while applying physical paper, DPI, bleed and crop marks."""
 import io
 from pypdf import PdfReader,PdfWriter,Transformation
 from reportlab.pdfgen import canvas
 dpi=_number(options.get('dpi',300),72,1200);bleed=_number(options.get('bleedMm',0),0,20)*72/25.4
 paper=options.get('paper','art');crop=options.get('cropMarks',False)
 if type(crop) is not bool or crop and paper!='art':raise ValueError('Marcas de corte somente no tamanho da arte.')
 papers={'a4':(210,297),'a3':(297,420),'a5':(148,210),'letter':(215.9,279.4)}
 if paper=='custom':papers[paper]=(_number(options.get('paperWidthMm'),20,2000),_number(options.get('paperHeightMm'),20,2000))
 if paper!='art' and paper not in papers:raise ValueError('Papel desconhecido.')
 raw,_=render_document(doc,'pdf');source=PdfReader(io.BytesIO(raw));writer=PdfWriter()
 if len(source.pages)!=len(doc['frames']):raise ValueError('O HTML extravasa o número de frames. Confira alturas e quebras de página.')
 for page,frame in zip(source.pages,doc['frames']):
  artw,arth=frame['width']*72/dpi,frame['height']*72/dpi;marks=12 if crop else 0
  tw,th=(artw+2*(bleed+marks),arth+2*(bleed+marks)) if paper=='art' else tuple(v*72/25.4 for v in papers[paper])
  if paper=='art':scale=96/dpi;x=y=bleed+marks
  else:scale=min((tw-2*bleed)/float(page.mediabox.width),(th-2*bleed)/float(page.mediabox.height));x=(tw-float(page.mediabox.width)*scale)/2;y=(th-float(page.mediabox.height)*scale)/2
  if scale<=0:raise ValueError('Papel insuficiente para a sangria.')
  target=writer.add_blank_page(tw,th)
  target.merge_transformed_page(page,Transformation().scale(scale).translate(x,y))
  if crop:
   overlay=io.BytesIO();c=canvas.Canvas(overlay,pagesize=(tw,th));c.setLineWidth(.4)
   for left in (x,x+artw):
    for bottom in (y,y+arth):
     c.line(left-8,bottom,left-3,bottom);c.line(left+3,bottom,left+8,bottom);c.line(left,bottom-8,left,bottom-3);c.line(left,bottom+3,left,bottom+8)
   c.save();target.merge_page(PdfReader(io.BytesIO(overlay.getvalue())).pages[0])
 out=io.BytesIO();writer.write(out);return out.getvalue()
