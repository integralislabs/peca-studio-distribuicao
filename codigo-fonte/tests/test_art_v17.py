import unittest,io,base64
from pathlib import Path
from PIL import Image,ImageDraw,ImageFont
import image_conversion as ocr
class ArtTests(unittest.TestCase):
 def test_selective_color_font(self):
  im=Image.new('RGB',(600,220),'#e0e5ee');d=ImageDraw.Draw(im);f=ImageFont.truetype('C:/Windows/Fonts/georgiab.ttf',48);d.text((35,45),'Hello World',font=f,fill='#193c91',stroke_width=0);box=d.textbbox((35,45),'Hello World',font=f);b={'text':'Hello World','x':box[0],'y':box[1],'w':box[2]-box[0],'h':box[3]-box[1]};mask,color=ocr.foreground_mask(im,b);self.assertLess(abs(color[2]-145),8);self.assertLess(sum(mask.getdata())/255,b['w']*b['h']*.7);match=ocr.match_font(im,b,mask);self.assertEqual(match['font'],'Georgia');self.assertTrue(match['bold']);self.assertGreater(match['score'],.8);print('OCR match',match,'ink color',color,'mask coverage',round(sum(mask.getdata())/255/(b['w']*b['h']),4))
 def test_svg_pdf_security(self):
  from vector_pdf import sanitize_svg
  for bad in ['<svg><script/></svg>','<svg onload="x"/>','<svg><image href="https://x"/></svg>']:self.assertRaises(ValueError,sanitize_svg,bad)
 def test_woff_synthetic_vector(self):
  from fontTools.ttLib import TTFont
  from font_pdf import resolve_font,measure,draw_text
  from reportlab.pdfgen.canvas import Canvas
  f=TTFont('C:/Windows/Fonts/arial.ttf');f.flavor='woff';buf=io.BytesIO();f.save(buf)
  warnings=[];face=resolve_font({'font':'Custom','bold':True,'italic':True},[{'name':'Custom','data':'data:font/woff;base64,'+base64.b64encode(buf.getvalue()).decode()}],warnings)
  self.assertGreater(measure(face,'Hello',40),50);out=io.BytesIO();c=Canvas(out,pageCompression=0);draw_text(c,face,'Hello',10,10,40);c.save();self.assertNotIn(b'/Subtype /Image',out.getvalue());self.assertTrue(warnings)
 def test_svg_gradient_converts_all_inks_to_cmyk(self):
  from vector_pdf import draw_layer
  from reportlab.pdfgen.canvas import Canvas
  from reportlab.lib.colors import CMYKColor
  out=io.BytesIO();c=Canvas(out,pageCompression=0);svg='<svg xmlns="http://www.w3.org/2000/svg" width="100" height="100"><defs><linearGradient id="g"><stop offset="0" stop-color="#ff0000"/><stop offset="1" stop-color="#0000ff"/></linearGradient></defs><rect width="100" height="100" fill="url(#g)"/></svg>'
  draw_layer(c,{'height':100},{'type':'vector','svg':svg,'x':0,'y':0,'w':100,'h':100},color=lambda v:CMYKColor(0,1,1,0));c.save();pdf=out.getvalue();self.assertIn(b'/DeviceCMYK',pdf);self.assertNotIn(b'/DeviceRGB',pdf);self.assertNotIn(b'/Subtype /Image',pdf)
 @unittest.skipUnless(Path('C:/Windows/Fonts/DavidCLM-Medium.otf').is_file(),'CFF fixture David CLM not installed')
 def test_cff_actual_curves_and_rendered_pixels(self):
  import subprocess,tempfile
  from font_pdf import resolve_font,draw_text,measure
  from reportlab.pdfgen.canvas import Canvas
  fontpath=Path('C:/Windows/Fonts/DavidCLM-Medium.otf');raw=fontpath.read_bytes();warnings=[]
  face=resolve_font({'font':'CFF'},[{'name':'CFF','data':'data:font/otf;base64,'+base64.b64encode(raw).decode()}],warnings)
  self.assertIn('CFF ',face['font']);self.assertGreater(measure(face,'Hello',48),10)
  with tempfile.TemporaryDirectory() as tmp:
   pdf=Path(tmp)/'cff.pdf';c=Canvas(str(pdf),pagesize=(400,150),pageCompression=0);c.setFillColorRGB(0,0,0);draw_text(c,face,'Hello World',20,60,48);c.save()
   self.assertNotIn(b'/Subtype /Image',pdf.read_bytes());subprocess.run(['pdftoppm','-r','288','-singlefile','-png',str(pdf),str(Path(tmp)/'render')],check=True,capture_output=True)
   actual=Image.open(Path(tmp)/'render.png').convert('L');expected=Image.new('L',(1600,600),255);ImageDraw.Draw(expected).text((80,360),'Hello World',anchor='ls',font=ImageFont.truetype(str(fontpath),192),fill=0)
   import numpy as np
   a=np.array(actual)<128;b=np.array(expected)<128;iou=(a&b).sum()/max(1,(a|b).sum());print('CFF glyph pixel IoU',round(float(iou),4));self.assertGreater(iou,.9)
if __name__=='__main__':unittest.main()
