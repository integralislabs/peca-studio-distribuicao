"""Local print export: RGB, physical dimensions, embedded vector text where supported."""
import base64, hashlib, io, math, re, threading, struct
from pathlib import Path

class PrintError(ValueError):pass
_lock=threading.Lock()

def _number(value,low,high,label):
    if type(value) not in (int,float) or not math.isfinite(value) or not low<=value<=high:raise PrintError(f'{label} fora do limite.')
    return value

def _raster(value):
    if not isinstance(value,str) or len(value)>32_000_000:raise PrintError('Imagem inválida ou muito grande.')
    match=re.fullmatch(r'data:image/(?:png|jpeg|webp);base64,([A-Za-z0-9+/=\s]+)',value)
    if not match:raise PrintError('Use apenas imagens locais PNG/JPEG/WebP.')
    try:
        from PIL import Image
        data=base64.b64decode(match[1],validate=False)
        im=Image.open(io.BytesIO(data));
        if im.width*im.height>60_000_000:raise PrintError('Imagem acima de 60 megapixels.')
        im.load();return im
    except PrintError:raise
    except Exception as e:raise PrintError('Não foi possível ler a imagem.') from e

def _font(layer,fonts,warnings):
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont
    family=layer.get('font','Arial');bold=bool(layer.get('bold'));italic=bool(layer.get('italic'))
    custom=next((f for f in fonts if f.get('family')==family or f.get('name')==family),None)
    if custom:
        from font_pdf import resolve_font
        try:return resolve_font(layer,fonts,warnings)
        except ValueError as e:raise PrintError(str(e)) from e
    paths={'Arial':('arial','arialbd','ariali','arialbi'),'Georgia':('georgia','georgiab','georgiai','georgiaz'),'Trebuchet MS':('trebuc','trebucbd','trebucit','trebucbi'),'Verdana':('verdana','verdanab','verdanai','verdanaz'),'Courier New':('cour','courbd','couri','courbi'),'Impact':('impact',)*4}
    if family not in paths:raise PrintError(f'Fonte {family} não incorporada. Cadastre a fonte ou use PDF raster.');
    file=Path('C:/Windows/Fonts')/(paths[family][int(bold)+2*int(italic)]+'.ttf')
    if file.is_file():
        name='system_'+file.stem
        if name not in pdfmetrics.getRegisteredFontNames():pdfmetrics.registerFont(TTFont(name,str(file)))
        return name
    warning=f'Fonte {family} substituída no PDF; confira a prévia.'
    if warning not in warnings:warnings.append(warning)
    return ('Courier' if family=='Courier New' else 'Times-Roman' if family=='Georgia' else 'Helvetica')

def _wrap(text,width,measure):
    result=[]
    for para in text.split('\n'):
        line=''
        for word in para.split():
            candidate=(line+' '+word).strip()
            if measure(candidate)<=width:line=candidate;continue
            if line:result.append(line);line=''
            for char in word:
                if line and measure(line+char)>width:result.append(line);line=''
                line+=char
        result.append(line)
    return result

def export_pdf(data):
    from image_quality import assert_image_quality
    try:assert_image_quality(data.get("piece"))
    except ValueError as e:raise PrintError("QA: "+str(e)) from e
    try:
        from reportlab.pdfgen import canvas
        from reportlab.pdfbase import pdfmetrics
        from reportlab.lib.colors import HexColor
        from reportlab.lib.utils import ImageReader
    except ImportError as e:raise PrintError('Prepare os recursos locais para exportar PDF (Preparar-recursos-locais.cmd).') from e
    piece=data.get('piece');options=data.get('options') or {}
    if not isinstance(piece,dict) or not isinstance(piece.get('slides'),list) or not 1<=len(piece['slides'])<=30:raise PrintError('Peça inválida: de 1 a 30 slides.')
    dpi=_number(options.get('dpi',300),72,1200,'DPI');paper=options.get('paper','art');bleed=_number(options.get('bleedMm',0),0,20,'Sangria')*72/25.4
    crop=options.get('cropMarks',False)
    if type(crop) is not bool or crop and paper!='art':raise PrintError('Marcas de corte só estão disponíveis no papel Tamanho da arte.')
    papers={'a4':(210,297),'a3':(297,420),'a5':(148,210),'letter':(215.9,279.4)}
    if paper=='custom':papers['custom']=(_number(options.get('paperWidthMm'),20,2000,'Largura do papel'),_number(options.get('paperHeightMm'),20,2000,'Altura do papel'))
    if paper!='art' and paper not in papers:raise PrintError('Papel desconhecido.')
    warnings=[]
    if piece.get('htmlDocument') and options.get('colorSpace','rgb')=='rgb':
        from html_document import print_document
        raw=print_document(piece['htmlDocument'],options)
        return {'base64':base64.b64encode(raw).decode(),'warnings':['HTML/CSS renderizado no Edge; confira o PDF e as fontes. A sangria não inventa conteúdo além do frame.'],'vectorText':True,'mime':'application/pdf'}
    if piece.get('htmlDocument'):
        from html_document import render_document
        import copy
        piece=copy.deepcopy(piece)
        for i,slide in enumerate(piece['slides']):slide['bgImage']='data:image/png;base64,'+base64.b64encode(render_document(piece['htmlDocument'],'png',i)[0]).decode();slide['layers']=[]
        warnings.append('HTML em CMYK usa raster renderizado do documento; o PDF RGB mantém o texto vetorial.')
    from print_color import PrintColor
    colors=PrintColor(options,warnings)
    sizes=[];raster_pages=data.get('rasterPages') or [];fonts=piece.get('fonts',[])
    if not isinstance(fonts,list) or len(fonts)>40:raise PrintError('Lista de fontes inválida.')
    output=io.BytesIO();c=canvas.Canvas(output,pageCompression=1,invariant=1);c.setTitle(str(piece.get('title','Peça Studio'))[:180]);vector=True
    def color(value):
        if not isinstance(value,str) or not re.fullmatch(r'#[a-fA-F0-9]{6}',value):raise PrintError('Cor inválida na composição.')
        return colors.color(value)
    def image(value,x,y,w,h,zoom=1,ox=0,oy=0,flip=False,radius=0):
        im=_raster(value);k=max(w/im.width,h/im.height)*zoom;iw=im.width*k;ih=im.height*k
        c.saveState();path=c.beginPath();path.roundRect(x,y,w,h,min(radius,w/2,h/2)) if radius else path.rect(x,y,w,h);c.clipPath(path,stroke=0,fill=0)
        c.translate(x+w/2+ox,y+h/2-oy)
        if flip:c.scale(-1,1)
        c.drawImage(colors.reader(im),-iw/2,-ih/2,iw,ih,mask='auto');c.restoreState()
    with _lock:
        for index,s in enumerate(piece['slides']):
            if not isinstance(s,dict):raise PrintError('Slide inválido.')
            w=_number(s.get('width'),100,4096,'Largura');h=_number(s.get('height'),100,4096,'Altura');layers=s.get('layers',[])
            if not isinstance(layers,list) or len(layers)>100:raise PrintError('Máximo de 100 camadas por slide.')
            factor=72/dpi;aw=w*factor;ah=h*factor;mark=12 if crop else 0;edge=bleed+mark
            if paper=='art':pw,ph=aw+2*edge,ah+2*edge
            else:
                pw,ph=(v*72/25.4 for v in papers[paper])
                if min(pw,ph)<=2*bleed:raise PrintError('Sangria não deixa área útil no papel escolhido.')
                factor=min(factor,(pw-2*bleed)/w,(ph-2*bleed)/h);aw=w*factor;ah=h*factor
            sizes.append([round(pw,4),round(ph,4)]);c.setPageSize((pw,ph));x0=(pw-aw)/2;y0=(ph-ah)/2
            c.setFillColor(color(s.get('bg','#ffffff')));c.rect(x0-bleed,y0-bleed,aw+2*bleed,ah+2*bleed,stroke=0,fill=1)
            fallback=False
            try:
                for l in layers:
                    if l.get('visible',True) and l.get('type')=='text':_font(l,fonts,warnings)
            except PrintError:
                if len(raster_pages)!=len(piece['slides']):raise
                fallback=True;vector=False;warnings.append(f'Slide {index+1}: fonte sem suporte vetorial; usada prévia raster em alta.')
            c.saveState();c.translate(x0,y0);c.scale(factor,factor);clip=c.beginPath();clip.rect(0,0,w,h);c.clipPath(clip,stroke=0,fill=0)
            if fallback:image(raster_pages[index],0,0,w,h)
            else:
                if s.get('bgImage'):image(s['bgImage'],0,0,w,h)
                for l in layers:
                    if not isinstance(l,dict) or not l.get('visible',True):continue
                    x=_number(l.get('x'),-8192,8192,'Posição');y=_number(l.get('y'),-8192,8192,'Posição');lw=_number(l.get('w'),1,8192,'Largura da camada')
                    c.saveState();alpha=_number(l.get('opacity',1),0,1,'Opacidade');c.setFillAlpha(alpha);c.setStrokeAlpha(alpha)
                    rotation=_number(l.get('rotation',0),-360,360,'Rotação')
                    if rotation:
                        lh=l.get('h',len(str(l.get('text','')).split('\n'))*l.get('size',32)*l.get('lineHeight',1.15));cx=x+lw/2;cy=h-y-lh/2;c.translate(cx,cy);c.rotate(-rotation);c.translate(-cx,-cy)
                    if l.get('type')=='image':
                        lh=_number(l.get('h'),1,8192,'Altura da imagem');image(l['src'],x,h-y-lh,lw,lh,_number(l.get('zoom',1),.2,5,'Zoom'),_number(l.get('offsetX',0),-4096,4096,'Enquadramento'),_number(l.get('offsetY',0),-4096,4096,'Enquadramento'),bool(l.get('flip')), _number(l.get('radius',0),0,4096,'Raio'))
                    elif l.get('type')=='text':
                        text=l.get('text','')
                        if not isinstance(text,str) or len(text)>10000:raise PrintError('Texto inválido.')
                        name=_font(l,fonts,warnings);size=_number(l.get('size'),8,400,'Fonte');spacing=_number(l.get('letterSpacing',0),-10,60,'Espaçamento');leading=_number(l.get('lineHeight',1.15),.6,3,'Entrelinha')*size
                        from font_pdf import measure as glyph_measure,draw_text
                        measure=lambda t:glyph_measure(name,t,size,spacing) if isinstance(name,dict) else pdfmetrics.stringWidth(t,name,size)+max(0,len(t)-1)*spacing
                        for line_index,line in enumerate(_wrap(text,lw,measure)):
                            line_w=measure(line);tx=x+(lw-line_w)/2 if l.get('align')=='center' else x+lw-line_w if l.get('align')=='right' else x;ty=h-y-size*.86-line_index*leading
                            c.setFillColor(color(l.get('color','#000000')));c.setStrokeColor(color(l.get('color','#000000')))
                            if isinstance(name,dict):draw_text(c,name,line,tx,ty,size,spacing)
                            else:
                                t=c.beginText(tx,ty);t.setFont(name,size);t.setCharSpace(spacing);t.setFillColor(color(l.get('color','#000000')));t.textOut(line);c.drawText(t)
                            if l.get('underline'):c.setStrokeColor(color(l.get('color','#000000')));c.setLineWidth(max(1,size/22));c.line(tx,ty-size*.1,tx+line_w,ty-size*.1)
                    elif l.get('type') in ('shape','vector'):
                        from vector_pdf import draw_layer
                        draw_layer(c,s,l,color)
                    else:raise PrintError('Tipo de camada não suportado.')
                    c.restoreState()
            c.restoreState()
            if crop:
                c.setStrokeColor(color('#000000'));c.setLineWidth(.3)
                for px,py in [(x0,y0),(x0+aw,y0),(x0,y0+ah),(x0+aw,y0+ah)]:
                    dx=-1 if px==x0 else 1;dy=-1 if py==y0 else 1;c.line(px+dx*(bleed+2),py,px+dx*(bleed+10),py);c.line(px,py+dy*(bleed+2),px,py+dy*(bleed+10))
            c.showPage()
        c.save()
    return {'base64':base64.b64encode(colors.finalize(output.getvalue())).decode(),'mime':'application/pdf','pages':len(sizes),'pageSizes':sizes,'vectorText':vector,'colorSpace':colors.mode,'iccEmbedded':bool(colors.profile),'warnings':warnings+(['PDF em RGB.'] if colors.mode=='rgb' else [])}
