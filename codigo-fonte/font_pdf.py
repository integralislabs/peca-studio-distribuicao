"""Local font decoding and vector glyph outlines (TTF/CFF/WOFF); no remote fonts."""
import base64,hashlib,io,math,struct,unicodedata
from pathlib import Path
from functools import lru_cache

SYSTEM={'Arial':('arial','arialbd','ariali','arialbi'),'Georgia':('georgia','georgiab','georgiai','georgiaz'),'Trebuchet MS':('trebuc','trebucbd','trebucit','trebucbi'),'Verdana':('verdana','verdanab','verdanai','verdanaz'),'Courier New':('cour','courbd','couri','courbi'),'Impact':('impact',)*4}

def resolve_font(layer,fonts,warnings):
 from fontTools.ttLib import TTFont
 family=layer.get('font','Arial');bold=bool(layer.get('bold'));italic=bool(layer.get('italic'));custom=next((f for f in fonts if f.get('name',f.get('family'))==family),None)
 if custom:
  data=custom.get('data',custom.get('src',''))
  if not isinstance(data,str) or len(data)>8_000_000 or not data.startswith('data:font/') or ';base64,' not in data:raise ValueError('Fonte incorporada inválida.')
  try:raw=base64.b64decode(data.split(',',1)[1],validate=True)
  except Exception as e:raise ValueError('Fonte inválida.') from e
 else:
  if family not in SYSTEM:raise ValueError('Fonte local não incorporada: '+family)
  path=Path('C:/Windows/Fonts')/(SYSTEM[family][int(bold)+2*int(italic)]+'.ttf')
  if not path.is_file():raise ValueError('Fonte Windows indisponível: '+family)
  raw=path.read_bytes()
 try:font=_decode(raw)
 except Exception as e:raise ValueError('Fonte sem suporte vetorial; use prévia raster.') from e
 cmap=font.getBestCmap();text=layer.get('text','')
 if any(ch not in '\n\t\r' and ord(ch) not in cmap for ch in text):raise ValueError('A fonte não cobre todos os caracteres; use outra face ou prévia raster.')
 if any(unicodedata.bidirectional(ch) in ('R','AL','AN') or unicodedata.combining(ch) for ch in text):raise ValueError('Texto requer shaping complexo; use prévia raster.')
 style=font['head'].macStyle;sb=bold and not bool(style&1);si=italic and not bool(style&2)
 if (not bold and style&1) or (not italic and style&2):raise ValueError('O arquivo contém estilo diferente do solicitado; use face correta ou prévia raster.')
 if sb or si:
  msg=f'Fonte {family}: estilo sintetizado por curvas vetoriais; confira a aparência.'
  if msg not in warnings:warnings.append(msg)
 return {'font':font,'glyphs':font.getGlyphSet(),'cmap':font.getBestCmap(),'units':font['head'].unitsPerEm,'bold':sb,'italic':si}

@lru_cache(maxsize=40)
def _decode(raw):
 from fontTools.ttLib import TTFont
 if len(raw)<12:raise ValueError('Fonte truncada.')
 signature=raw[:4]
 if signature in (b'wOFF',b'wOF2'):
  if len(raw)<48 or struct.unpack_from('>I',raw,16)[0]>30_000_000:raise ValueError('Fonte descomprimida excede limite.')
 elif signature not in (b'OTTO',b'\x00\x01\x00\x00'):raise ValueError('Assinatura de fonte inválida.')
 if struct.unpack_from('>H',raw,12 if signature in (b'wOFF',b'wOF2') else 4)[0]>4096:raise ValueError('Tabelas demais na fonte.')
 f=TTFont(io.BytesIO(raw),lazy=False)
 if len(f.getGlyphOrder())>65536 or f['head'].unitsPerEm<=0:raise ValueError('Fonte inválida.')
 return f

def measure(face,text,size,spacing=0):
 f=face['font'];cmap=face['cmap'];width=sum(f['hmtx'].metrics[cmap.get(ord(ch),'.notdef')][0] for ch in text)*size/face['units']
 return width+max(0,len(text)-1)*spacing

def draw_text(c,face,text,x,y,size,spacing=0):
 """Baseline in canvas px, bottom-left coordinates. Uses current fill/stroke colors."""
 from fontTools.pens.basePen import BasePen
 class Pen(BasePen):
  def __init__(self,gs,path):super().__init__(gs);self.path=path
  def _moveTo(self,p):self.path.moveTo(*p)
  def _lineTo(self,p):self.path.lineTo(*p)
  def _curveToOne(self,p1,p2,p3):self.path.curveTo(*p1,*p2,*p3)
  def _qCurveToOne(self,p1,p2):
   p0=self._getCurrentPoint();a=(p0[0]+2*(p1[0]-p0[0])/3,p0[1]+2*(p1[1]-p0[1])/3);b=(p2[0]+2*(p1[0]-p2[0])/3,p2[1]+2*(p1[1]-p2[1])/3);self.path.curveTo(*a,*b,*p2)
  def _closePath(self):self.path.close()
  def _endPath(self):pass
 scale=size/face['units'];advance=0
 for ch in text:
  name=face['cmap'].get(ord(ch),'.notdef');c.saveState();c.translate(x+advance,y);c.scale(scale,scale)
  if face['italic']:c.transform(1,0,.21256,1,0,0)
  p=c.beginPath();face['glyphs'][name].draw(Pen(face['glyphs'],p))
  if face['bold']:c.setLineWidth(face['units']*.025);c.setLineJoin(1)
  c.drawPath(p,fill=1,stroke=int(face['bold']),fillMode=1);c.restoreState();advance+=face['font']['hmtx'].metrics[name][0]*scale+spacing
