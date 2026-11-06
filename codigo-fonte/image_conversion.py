"""Local line OCR and approximate editable reconstruction; no network requests."""
from functools import lru_cache
import base64
import csv
import hashlib
import io
import json
import math
import os
import re
import shutil
import subprocess
import tempfile
import uuid
from pathlib import Path
TESSERACT = shutil.which('tesseract') or r'C:\Program Files\Tesseract-OCR\tesseract.exe'

def capabilities():
    try:
        import PIL
        pillow = True
    except ImportError:
        pillow = False
    return {'ocr': Path(TESSERACT).is_file() and pillow, 'pillow': pillow,
            'languages': ['por', 'eng'], 'local': True, 'maxBytes': 20 * 1024 * 1024,
            'maxDimension': 4096}

def _image(data):
    from PIL import Image, ImageOps, UnidentifiedImageError
    value = data.get('image') if isinstance(data, dict) else None
    if not isinstance(value, str) or len(value) > 28 * 1024 * 1024:
        raise ValueError('Escolha uma imagem PNG/JPEG/WebP de até 20 MB.')
    match = re.fullmatch(r'data:image/(png|jpeg|webp);base64,([A-Za-z0-9+/=\s]+)', value)
    if not match:
        raise ValueError('Formato de imagem inválido: use PNG/JPEG/WebP local.')
    try:
        raw = base64.b64decode(re.sub(r'\s', '', match[2]), validate=True)
        if len(raw) > 20 * 1024 * 1024:
            raise ValueError('A imagem deve ter até 20 MB.')
        with Image.open(io.BytesIO(raw)) as source:
            if source.format not in ('PNG', 'JPEG', 'WEBP'):
                raise ValueError('Conteúdo de imagem inválido.')
            if not (100 <= source.width <= 4096 and 100 <= source.height <= 4096):
                raise ValueError('A arte deve ter entre 100 e 4096 pixels em cada dimensão.')
            source.load()
            im = ImageOps.exif_transpose(source).convert('RGB')
    except (UnidentifiedImageError, OSError, SyntaxError) as exc:
        raise ValueError('Não foi possível ler a imagem.') from exc
    return im, raw, value

def _hash(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(',', ':')).encode()).hexdigest()

def detect_panels(im):
    """Conservative solid rectangle proposals; always opt-in and editable."""
    try:
        import cv2,numpy as np
    except ImportError:return []
    scale=min(1,1024/max(im.size));small=im.resize((max(1,round(im.width*scale)),max(1,round(im.height*scale))))
    arr=np.array(small);colors,counts=np.unique((arr//8).reshape(-1,3),axis=0,return_counts=True);result=[]
    for color in colors[np.argsort(counts)[-8:]]:
        mask=np.all(arr//8==color,axis=2).astype('uint8')*255
        for contour in cv2.findContours(mask,cv2.RETR_EXTERNAL,cv2.CHAIN_APPROX_SIMPLE)[0]:
            x,y,w,h=cv2.boundingRect(contour)
            if w<20 or h<12 or w*h>small.width*small.height*.85 or w*h<small.width*small.height*.01:continue
            crop=mask[y:y+h,x:x+w]
            if np.mean(crop>0)<.9:continue
            rgb=np.median(arr[y:y+h,x:x+w][crop>0],axis=0).astype(int)
            result.append({'x':round(x/scale),'y':round(y/scale),'w':min(im.width-round(x/scale),round(w/scale)),'h':min(im.height-round(y/scale),round(h/scale)),'color':'#%02x%02x%02x'%tuple(rgb),'selected':False})
            if len(result)==16:return result
    return result

def analyze_image(data):
    im, raw, _ = _image(data)
    language = data.get('language', 'por+eng')
    if language not in ('por', 'eng', 'por+eng', 'eng+por'):
        raise ValueError('Idioma inválido. Use por, eng ou por+eng.')
    if not capabilities()['ocr']:
        raise ValueError('OCR local indisponível: instale Tesseract e Pillow.')
    with tempfile.TemporaryDirectory(prefix='peca-ocr-') as temp:
        image_path = os.path.join(temp, 'image.png'); im.save(image_path)
        try:
            process = subprocess.run([TESSERACT, image_path, 'stdout', '-l', language, '--psm', '11', 'tsv'],
                                     capture_output=True, timeout=60, creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
        except (OSError, subprocess.TimeoutExpired) as exc:
            raise ValueError('Falha ou tempo limite do OCR local.') from exc
    if process.returncode:
        raise ValueError('Tesseract não concluiu o OCR. Confira os idiomas instalados.')
    lines = {}
    # Tesseract TSV uses literal quote characters, not CSV quoted fields.
    for row in csv.DictReader(io.StringIO(process.stdout.decode('utf-8', errors='replace')), delimiter='\t', quoting=csv.QUOTE_NONE):
        text = row.get('text', '').strip()
        if row.get('level') != '5' or not text:
            continue
        key = tuple(row[k] for k in ('page_num', 'block_num', 'par_num', 'line_num'))
        lines.setdefault(key, []).append((text, int(row['left']), int(row['top']), int(row['width']), int(row['height']), float(row['conf'])))
    blocks = []
    for words in lines.values():
        x = min(w[1] for w in words); y = min(w[2] for w in words)
        right = max(w[1] + w[3] for w in words); bottom = max(w[2] + w[4] for w in words)
        blocks.append({'id': 'block-' + str(len(blocks) + 1), 'text': ' '.join(w[0] for w in words),
                       'x': x, 'y': y, 'w': right-x, 'h': bottom-y,
                       'sourceText': ' '.join(w[0] for w in words), 'confidence': round(sum(w[5] for w in words)/len(words), 1), 'selected': True})
    warnings = ['OCR pode errar preços, acentos e CTA. Revise cada linha e a posição antes de converter.']
    if len(blocks) > 100:
        warnings.append('Selecione até 100 blocos para converter; os demais permanecem na imagem.')
    if not blocks:
        warnings.append('Nenhum texto localizado. Adicione blocos manualmente ou mantenha a imagem como fundo.')
    return {'width': im.width, 'height': im.height, 'blocks': blocks, 'warnings': warnings, 'panels':detect_panels(im),
            'referenceHash': hashlib.sha256(raw).hexdigest()}

def foreground_mask(im,b):
    """Contrast mask against a local border estimate; never erase the whole OCR box."""
    import numpy as np
    from PIL import Image
    x,y,w,h=[int(b[k]) for k in ('x','y','w','h')]
    crop=np.array(im.crop((x,y,x+w,y+h)),dtype=np.float32)
    outer=np.array(im.crop((max(0,x-3),max(0,y-3),min(im.width,x+w+3),min(im.height,y+h+3))),dtype=np.float32)
    ring=np.concatenate([outer[:3].reshape(-1,3),outer[-3:].reshape(-1,3),outer[:,:3].reshape(-1,3),outer[:,-3:].reshape(-1,3)])
    bg=np.median(ring,axis=0);dist=np.sqrt(((crop-bg)**2).sum(axis=2));threshold=max(18,float(np.percentile(dist,95))*.3)
    selected=dist>threshold
    if selected.mean()>.8: selected=dist>float(np.percentile(dist,65))
    pixels=crop[selected];color=tuple(int(v) for v in (np.median(pixels,axis=0) if len(pixels) else bg))
    # Restrict to pixels near the inferred ink hue, reducing photographic background loss.
    inkdist=np.sqrt(((crop-np.array(color))**2).sum(axis=2));selected &= inkdist < max(35,float(np.linalg.norm(np.array(color)-bg))*.7)
    return Image.fromarray((selected*255).astype('uint8')),color

def portable_fonts(value):
    from font_pdf import _decode, SYSTEM
    import unicodedata
    if not isinstance(value,list) or len(value)>32:raise ValueError('Use até 32 fontes locais.')
    result=[];seen=set();total=0
    for item in value:
        if not isinstance(item,dict):raise ValueError('Fonte inválida.')
        name=item.get('name','');data=item.get('data','')
        key=unicodedata.normalize('NFKC',name).casefold() if isinstance(name,str) else ''
        if not key or len(name)>80 or not name[0].isalnum() or any(not(c.isalnum() or c in ' _-') for c in name) or key in seen or key in {x.casefold() for x in SYSTEM}:raise ValueError('Nome de fonte inválido ou duplicado.')
        match=re.fullmatch(r'data:font/(ttf|otf|woff|woff2);base64,([A-Za-z0-9+/]+={0,2})',data) if isinstance(data,str) and len(data)<=7_000_000 else None
        if not match:raise ValueError('Fonte incorporada inválida.')
        try:
            raw=base64.b64decode(match[2],validate=True)
            if len(raw)>5*1024*1024:raise ValueError('Fonte excede 5 MB.')
            if raw[:4]!={'ttf':b'\x00\x01\x00\x00','otf':b'OTTO','woff':b'wOFF','woff2':b'wOF2'}[match[1]]:raise ValueError('Font signature mismatch.')
            _decode(raw)
        except Exception as exc:raise ValueError('Fonte inválida ou sem suporte.') from exc
        total+=len(raw)
        if total>20*1024*1024:raise ValueError('Fontes excedem 20 MB.')
        seen.add(key);result.append({'name':name,'data':data})
    return result

def portable_ocr_fonts(fonts):
    """Freeze supported variable weights into real portable faces, never synthesize missing weights."""
    from font_pdf import _decode
    from fontTools.varLib.instancer import instantiateVariableFont
    result=[]
    for font in portable_fonts(fonts):
        face=_decode(base64.b64decode(font['data'].split(',',1)[1]))
        if 'fvar' not in face or not any(a.axisTag=='wght' for a in face['fvar'].axes):result.append(font);continue
        axis=next(a for a in face['fvar'].axes if a.axisTag=='wght')
        weights=[w for w in range(300,901,100) if axis.minValue<=w<=axis.maxValue]
        if not weights:result.append(font);continue
        for weight in weights:
            values={a.axisTag:(weight if a.axisTag=='wght' else a.defaultValue) for a in face['fvar'].axes}
            instance=instantiateVariableFont(face,values,inplace=False);instance.flavor=None
            buffer=io.BytesIO();instance.save(buffer)
            result.append({'name':font['name'][:74]+' W'+str(weight),'data':'data:font/ttf;base64,'+base64.b64encode(buffer.getvalue()).decode()})
    return portable_fonts(result)

def match_font(im,b,mask,fonts=()):
    return dict(_match_font_cached(b.get('sourceText',b['text']),mask.size,mask.tobytes(),tuple((f['name'],f['data']) for f in fonts)))

@lru_cache(maxsize=256)
def _match_font_cached(text,dimensions,pixels,custom=()):
    from PIL import Image
    mask=Image.frombytes('L',dimensions,pixels);b={'text':text,'h':dimensions[1]}
    from PIL import Image,ImageDraw,ImageFont
    import numpy as np
    from font_pdf import SYSTEM
    target=np.array(mask)>0;box=mask.getbbox()
    if not box or not b['text'].strip():return {'font':'Arial','size':max(8,min(400,round(b['h']))),'bold':False,'italic':False,'score':0,'offsetX':0,'offsetY':0}
    target=target[box[1]:box[3],box[0]:box[2]];th,tw=target.shape;best=None
    # Compare actual local font glyph masks in their own ink boxes. Aspect ratio is scored,
    # not stretched away, so Georgia cannot tie Arial solely by box dimensions.
    candidates=[]
    from font_pdf import _decode
    for family,data in custom:
        raw=base64.b64decode(data.split(',',1)[1]);decoded=_decode(raw)
        style=decoded['head'].macStyle & 3
        # Pillow requires sfnt bytes for portable WOFF faces.
        buf=io.BytesIO();decoded.flavor=None;decoded.save(buf)
        candidates.append((family,style,buf.getvalue()))
    for family,files in SYSTEM.items():
      for style,name in enumerate(files):
       path=Path('C:/Windows/Fonts')/(name+'.ttf')
       if path.is_file():candidates.append((family,style,path.read_bytes()))
    for family,style,raw in candidates:
       path=io.BytesIO(raw)
       f=ImageFont.truetype(io.BytesIO(raw),100);bb=f.getbbox(b['text']);inkh=max(1,bb[3]-bb[1]);size=max(8,min(400,round(100*th/inkh)))
       for sz in range(max(8,size-4),min(400,size+4)+1):
        font=ImageFont.truetype(io.BytesIO(raw),sz);bb=font.getbbox(b['text']);ww=max(1,bb[2]-bb[0]);hh=max(1,bb[3]-bb[1]);canvas=Image.new('L',(ww,hh));ImageDraw.Draw(canvas).text((-bb[0],-bb[1]),b['text'],font=font,fill=255)
        # Small antialias tolerance through a common comparison grid.
        inkbox=canvas.getbbox();canvas=canvas.crop(inkbox) if inkbox else canvas;ww,hh=canvas.size
        pred=np.array(canvas.resize((tw,th)))>96;inter=(pred&target).sum();union=(pred|target).sum();iou=float(inter/max(1,union));aspect=math.exp(-abs(math.log((ww/hh)/(tw/th)))*2);score=iou*aspect
        result={'font':family,'size':sz,'bold':bool(style&1),'italic':bool(style&2),'fontFaceExact':family not in SYSTEM,'score':round(score,4),'offsetX':box[0]-bb[0]-(inkbox[0] if inkbox else 0),'offsetY':box[1]-bb[1]-(inkbox[1] if inkbox else 0),'inkWidth':ww,'inkHeight':hh}
        if best is None or score>best['score']:best=result
    return best or {'font':'Arial','size':max(8,min(400,round(b['h']))),'bold':False,'italic':False,'score':0,'offsetX':0,'offsetY':0}

def conversion_extras(im,data):
    from PIL import Image,ImageDraw
    panels=data.get('panels',[]);occlusions=data.get('occlusions',[])
    if not isinstance(panels,list) or len(panels)>16 or not isinstance(occlusions,list) or len(occlusions)>16:raise ValueError('Use até 16 painéis e 16 polígonos.')
    def number(v):return not isinstance(v,bool) and isinstance(v,(int,float)) and math.isfinite(v)
    layers=[]
    for p in panels:
        if not isinstance(p,dict):raise ValueError('Painel inválido.')
        x,y,w,h=[p.get(k) for k in ('x','y','w','h')];color=p.get('color')
        if not all(number(v) for v in (x,y,w,h)) or x<0 or y<0 or w<1 or h<1 or x+w>im.width or y+h>im.height or not isinstance(color,str) or not re.fullmatch('#[0-9a-fA-F]{6}',color):raise ValueError('Painel inválido ou fora da imagem.')
        if p.get('selected',True):layers.append({'id':str(uuid.uuid4()),'type':'shape','name':'Painel editável','shape':'rect','x':x,'y':y,'w':w,'h':h,'fill':color,'stroke':None,'strokeWidth':0,'radius':0,'rotation':0,'visible':True})
    alpha=Image.new('L',im.size)
    for p in occlusions:
        if not isinstance(p,dict):raise ValueError('Oclusão inválida.')
        points=p.get('points');opacity=p.get('alpha',1)
        if not isinstance(points,list) or not 3<=len(points)<=64 or not number(opacity) or not 0<opacity<=1:raise ValueError('Polígono ou alpha inválido.')
        for point in points:
            if not isinstance(point,list) or len(point)!=2 or not all(number(v) for v in point) or not 0<=point[0]<im.width or not 0<=point[1]<im.height:raise ValueError('Polígono fora da imagem.')
        if p.get('selected',True):ImageDraw.Draw(alpha).polygon([tuple(v) for v in points],fill=round(255*opacity))
    overlay=None
    if alpha.getbbox():
        foreground=im.convert('RGBA');foreground.putalpha(alpha);buf=io.BytesIO();foreground.save(buf,'PNG')
        src='data:image/png;base64,'+base64.b64encode(buf.getvalue()).decode()
        if len(src)>8_000_000:raise ValueError('Sobreposição excede 8 MB.')
        overlay={'id':str(uuid.uuid4()),'type':'image','name':'Primeiro plano preservado','src':src,'x':0,'y':0,'w':im.width,'h':im.height,'zoom':1,'offsetX':0,'offsetY':0,'flip':False,'visible':True}
    return layers,overlay

def convert_image(data):
    from PIL import ImageDraw, ImageStat
    im, raw, original = _image(data)
    fonts=portable_ocr_fonts(data.get('fonts',[]))
    panels,overlay=conversion_extras(im,data)
    incoming = data.get('blocks')
    if not isinstance(incoming, list) or len(incoming) > 500:
        raise ValueError('Envie os blocos revisados (até 500; selecione até 100).')
    blocks = []
    for item in incoming:
        if not isinstance(item, dict):
            raise ValueError('Bloco inválido.')
        values = [item.get(k) for k in ('x', 'y', 'w', 'h')]
        if any(isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v) for v in values):
            raise ValueError('Posição e tamanho do bloco inválidos.')
        x, y, w, h = values
        if x < 0 or y < 0 or w < 1 or h < 1 or x+w > im.width or y+h > im.height:
            raise ValueError('O bloco deve ficar inteiramente dentro da imagem.')
        text = item.get('text', '')
        if not isinstance(text, str) or len(text) > 10000:
            raise ValueError('Texto do bloco inválido.')
        if item.get('selected', True):
            blocks.append({'id': str(item.get('id', len(blocks)))[:100], 'text': text, 'x': x, 'y': y, 'w': w, 'h': h, 'sourceText': item.get('sourceText',text) if isinstance(item.get('sourceText',text),str) and len(item.get('sourceText',text))<=10000 else text})
    if len(blocks)+len(panels)+bool(overlay) > 100:
        raise ValueError('Selecione no máximo 100 blocos; desmarque os demais antes de converter.')
    notices = ['Reconstrução aproximada: fonte e estilo escolhidos por comparação de máscaras entre fontes Windows locais. Compare com a referência; a fonte original pode não estar instalada.',
                'Máscara seletiva por contraste/cor; limpeza pode alterar fotos, gradientes e desenhos. Revise cada região.']
    warnings=[]
    from PIL import Image,ImageFilter
    cleaned=im.copy();masks=[];matches=[];layers=panels.copy()
    fullmask=Image.new('L',im.size)
    for b in blocks:
        mask,color=foreground_mask(im,b);match=match_font(im,b,mask,fonts);masks.append(mask);matches.append({'id':b['id'],**match,'color':'#%02x%02x%02x'%color})
        fullmask.paste(mask.filter(ImageFilter.MaxFilter(3)),(int(b['x']),int(b['y'])))
        layers.append({'id':str(uuid.uuid4()),'type':'text','name':b['text'][:80] or 'Texto revisado','text':b['text'],
            'x':b['x']+match['offsetX'],'y':b['y']+match['offsetY'],'w':min(8192,max(b['w']+4,match.get('inkWidth',b['w'])+4)),
            'font':match['font'],'size':match['size'],'color':'#%02x%02x%02x'%color,'bold':match['bold'],'italic':match['italic'],'fontFaceExact':match.get('fontFaceExact',False),
            'underline':False,'align':'left','lineHeight':1.15,'letterSpacing':0,'visible':True})
    try:
        import cv2,numpy as np
        cleaned=Image.fromarray(cv2.inpaint(np.array(im),np.array(fullmask),3,cv2.INPAINT_TELEA));method='opencv-selective-inpaint'
    except ImportError:
        from PIL import ImageStat
        for b,mask in zip(blocks,masks):
            x,y,w,h=[int(b[k]) for k in ('x','y','w','h')];ring=im.crop((max(0,x-4),max(0,y-4),min(im.width,x+w+4),min(im.height,y+h+4)))
            color=tuple(int(v) for v in ImageStat.Stat(ring).median);cleaned.paste(color,(x,y,x+w,y+h),mask)
        method='pillow-selective-fill';warnings.append('OpenCV indisponível: preenchimento seletivo; fundo complexo precisa de correção manual.')
    low=sum(m['score']<.5 for m in matches)
    if low:warnings.append(f'{low} bloco(s) com baixa semelhança tipográfica; revise fonte/estilo manualmente.')
    output = io.BytesIO(); cleaned.save(output, 'PNG')
    bg = 'data:image/png;base64,' + base64.b64encode(output.getvalue()).decode()
    if len(bg) > 8e6:
        raise ValueError('O fundo convertido excede 8 MB. Reduza a imagem antes da conversão.')
    if overlay:layers.append(overlay)
    slide = {'id': str(uuid.uuid4()), 'width': im.width, 'height': im.height, 'bg': '#ffffff', 'bgImage': bg, 'layers': layers}
    report = {'warnings': warnings, 'notices':notices, 'method': method, 'referenceHash': hashlib.sha256(raw).hexdigest(),
              'slideHash': _hash(slide), 'blocksHash': _hash(blocks), 'blocks': blocks,
              'fontMatches': matches, 'maskPixels': sum(fullmask.histogram()[1:]),
              'qa': {'status': 'pending', 'regions': [{'id': b['id'], 'text': b['text'], 'approved': False} for b in blocks]}}
    return {'fonts':fonts,'slide': slide, 'report': report, 'reference': {'image': original, 'width': im.width, 'height': im.height}}
