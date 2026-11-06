"""Explicit generic CMYK or user-supplied press ICC; no guessed press profile."""
import base64,io
class PrintColor:
 def __init__(self,options,warnings):
  self.mode=options.get('colorSpace','rgb');self.profile=None;self.raw=None
  if self.mode not in ('rgb','cmyk'):raise ValueError('Espaço de cor inválido.')
  if options.get('iccBase64'):
   from PIL import ImageCms
   if self.mode!='cmyk':raise ValueError('Selecione CMYK para aplicar um perfil de impressão.')
   try:
    self.raw=base64.b64decode(options['iccBase64'],validate=True)
    if not 128<=len(self.raw)<=5_000_000 or self.raw[16:20]!=b'CMYK' or self.raw[36:40]!=b'acsp':raise ValueError()
    self.profile=ImageCms.ImageCmsProfile(io.BytesIO(self.raw))
    self.transform=ImageCms.buildTransform(ImageCms.createProfile('sRGB'),self.profile,'RGB','CMYK',renderingIntent=0)
   except Exception:raise ValueError('Perfil ICC CMYK inválido ou incompatível.') from None
  if self.mode=='cmyk' and not self.profile:warnings.append('CMYK genérico: sem perfil da gráfica. Solicite o ICC e confira uma prova de cor.')
 def image(self,im):
  if self.mode=='rgb':return im
  from PIL import Image,ImageCms
  im=im.convert('RGB')
  return ImageCms.applyTransform(im,self.transform) if self.profile else im.convert('CMYK')
 def reader(self,im):
  from reportlab.lib.utils import ImageReader
  alpha=im.convert('RGBA').getchannel('A') if self.mode=='cmyk' and (im.mode in ('RGBA','LA') or 'transparency' in im.info) else None
  reader=ImageReader(self.image(im))
  if alpha is not None:
   reader.getRGBData();reader._dataA=ImageReader(alpha)
  return reader
 def color(self,value):
  from reportlab.lib.colors import HexColor,CMYKColor
  if self.mode=='rgb':return HexColor(value)
  from PIL import Image
  rgb=tuple(bytes.fromhex(value[1:]));pixel=self.image(Image.new('RGB',(1,1),rgb)).getpixel((0,0));return CMYKColor(*(v/255 for v in pixel))
 def finalize(self,raw):
  if not self.profile:return raw
  from pypdf import PdfReader,PdfWriter
  from pypdf.generic import DecodedStreamObject,NameObject,NumberObject,DictionaryObject,TextStringObject,ArrayObject
  reader=PdfReader(io.BytesIO(raw));writer=PdfWriter();writer.clone_document_from_reader(reader)
  stream=DecodedStreamObject();stream.set_data(self.raw);stream[NameObject('/N')]=NumberObject(4)
  intent=DictionaryObject({NameObject('/Type'):NameObject('/OutputIntent'),NameObject('/S'):NameObject('/GTS_PDFX'),NameObject('/OutputConditionIdentifier'):TextStringObject('Perfil CMYK fornecido pelo operador'),NameObject('/DestOutputProfile'):writer._add_object(stream)})
  writer._root_object[NameObject('/OutputIntents')]=ArrayObject([writer._add_object(intent)]);out=io.BytesIO();writer.write(out);return out.getvalue()
