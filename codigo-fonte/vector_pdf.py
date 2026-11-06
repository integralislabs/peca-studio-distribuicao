"""Bounded SVG subset and ReportLab vector shapes. No external SVG resources."""
import io,math,re,xml.etree.ElementTree as ET
TAGS={'svg','g','path','rect','circle','ellipse','line','polyline','polygon','defs','linearGradient','radialGradient','stop','clipPath'}
ATTRS=set('viewBox width height x y x1 x2 y1 y2 cx cy r rx ry d points fill stroke stroke-width stroke-linecap stroke-linejoin stroke-miterlimit fill-rule clip-rule opacity fill-opacity stroke-opacity transform id offset stop-color stop-opacity gradientUnits gradientTransform spreadMethod fx fy clip-path'.split())
def sanitize_svg(value):
 if not isinstance(value,str) or len(value)>200000 or re.search(r'<!|<\?|&|[\x00-\x08\x0b\x0c\x0e-\x1f]',value):raise ValueError('SVG inválido ou ativo.')
 try:root=ET.fromstring(value)
 except ET.ParseError as e:raise ValueError('SVG malformado.') from e
 nodes=list(root.iter())
 if len(nodes)>2000 or root.tag.split('}')[-1]!='svg':raise ValueError('SVG excede limites.')
 for node in nodes:
  if node.tag.split('}')[-1] not in TAGS or node.tag.startswith('{') and not node.tag.startswith('{http://www.w3.org/2000/svg}'):raise ValueError('Elemento SVG não permitido.')
  if node.text and node.text.strip():raise ValueError('Texto SVG não suportado.')
  for key,v in node.attrib.items():
   if key not in ('id','fill','stroke','stop-color','fill-rule','clip-rule','stroke-linecap','stroke-linejoin','gradientUnits','spreadMethod','clip-path') and (re.search(r'NaN|Infinity',v,re.I) or any(not math.isfinite(float(n)) or abs(float(n))>1e6 for n in re.findall(r'[-+]?(?:\d*\.)?\d+(?:e[-+]?\d+)?',v,re.I))):raise ValueError('Geometria SVG fora do limite.')
   if key not in ATTRS or len(v)>100000 or re.search(r'[<>\\]|javascript|data:|https?:|file:|@|expression',v,re.I):raise ValueError('Atributo/recurso SVG bloqueado.')
   if re.search(r'url\s*\(',v,re.I) and not re.fullmatch(r'url\(#[A-Za-z][\w-]{0,63}\)',v):raise ValueError('URL SVG bloqueada.')
 return value

def draw_layer(c,slide,layer,color=None):
 from reportlab.lib.colors import HexColor
 color=color or HexColor
 x,y,w,h=(layer[k] for k in ('x','y','w','h'));y=slide['height']-y-h
 for v in (x,y,w,h):
  if type(v) not in (int,float) or not math.isfinite(v):raise ValueError('Geometria inválida.')
 if not 1<=w<=8192 or not 1<=h<=8192:raise ValueError('Dimensão vetorial inválida.')
 c.saveState()
 try:
  if layer['type']=='vector':
   from svglib.svglib import svg2rlg
   from reportlab.graphics import renderPDF
   drawing=svg2rlg(io.BytesIO(sanitize_svg(layer['svg']).encode()))
   if not drawing or drawing.width<=0 or drawing.height<=0:raise ValueError('SVG sem dimensões.')
   if color is not HexColor or layer.get('opacity',1)!=1:
    def convert(obj):
     for key in ('fillOpacity','strokeOpacity'):
      if hasattr(obj,key):setattr(obj,key,getattr(obj,key)*layer.get('opacity',1))
     for key in ('fillColor','strokeColor'):
      old=getattr(obj,key,None)
      if old is not None and hasattr(old,'hexval'):setattr(obj,key,color(old.hexval().replace('0x','#')))
     if hasattr(obj,'_rl_colors'):obj._rl_colors=[color(v.hexval().replace('0x','#')) for v in obj._rl_colors]
     for child in getattr(obj,'contents',[]):convert(child)
    convert(drawing)
   c.translate(x,y);c.scale(w/drawing.width,h/drawing.height);renderPDF.draw(drawing,c,0,0);return
  p=c.beginPath()
  if layer.get('shape')=='ellipse':p.ellipse(x,y,w,h)
  elif layer.get('shape')=='rect':p.roundRect(x,y,w,h,min(layer.get('radius',0),w/2,h/2))
  else:raise ValueError('Forma inválida.')
  g=layer.get('gradient');fill=layer.get('fill');stroke=layer.get('stroke');sw=layer.get('strokeWidth',0)
  if g:
   if not isinstance(g.get('stops'),list) or not 2<=len(g['stops'])<=16:raise ValueError('Gradiente inválido.')
   a=math.radians(g['angle']);dx=math.sin(a);dy=math.cos(a);n=(abs(w*dx)+abs(h*dy))/2;cx=x+w/2;cy=y+h/2
   c.saveState();c.clipPath(p,stroke=0);c.linearGradient(cx-dx*n,cy-dy*n,cx+dx*n,cy+dy*n,[color(s['color']) for s in g['stops']],[s['offset'] for s in g['stops']],extend=True);c.restoreState()
  elif fill:c.setFillColor(color(fill));c.drawPath(p,fill=1,stroke=0)
  if stroke and sw:c.setStrokeColor(color(stroke));c.setLineWidth(sw);c.drawPath(p,fill=0,stroke=1)
 finally:c.restoreState()
