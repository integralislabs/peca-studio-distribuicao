import base64,io,unittest
from pathlib import Path
from PIL import Image,ImageDraw,ImageFont
from image_conversion import convert_image

def data(im):
 out=io.BytesIO();im.save(out,'PNG');return 'data:image/png;base64,'+base64.b64encode(out.getvalue()).decode()

class OCRParity(unittest.TestCase):
 def test_custom_face_name_and_portable_bytes_survive_matching(self):
  raw=Path('C:/Windows/Fonts/georgiab.ttf').read_bytes()
  face={'name':'Minha Georgia Bold','data':'data:font/ttf;base64,'+base64.b64encode(raw).decode()}
  im=Image.new('RGB',(400,150),'white');ImageDraw.Draw(im).text((20,20),'Oferta',font=ImageFont.truetype(io.BytesIO(raw),48),fill='black')
  box=im.convert('L').point(lambda p:255-p).getbbox()
  result=convert_image({'image':data(im),'fonts':[face],'blocks':[dict(id='a',text='Oferta',x=box[0],y=box[1],w=box[2]-box[0],h=box[3]-box[1])]})
  self.assertEqual(result['slide']['layers'][0]['font'],'Minha Georgia Bold')
  self.assertTrue(result['slide']['layers'][0]['bold'])
  self.assertTrue(result['slide']['layers'][0]['fontFaceExact'])
  self.assertEqual(result['fonts'],[face])
 def test_invalid_font_rejected_before_empty_conversion(self):
  with self.assertRaises(ValueError):convert_image({'image':data(Image.new('RGB',(100,100))),'blocks':[],'fonts':[{'name':'Bad','data':'data:font/ttf;base64,AAAA'}]})
 def test_panels_below_text_and_original_polygon_pixels_above_it(self):
  im=Image.new('RGB',(120,120),'white');ImageDraw.Draw(im).rectangle((30,30,50,50),fill='red')
  result=convert_image({'image':data(im),'blocks':[],'panels':[dict(x=10,y=10,w=80,h=80,color='#ffffff')],'occlusions':[{'points':[[30,30],[50,30],[50,50],[30,50]],'alpha':1}]})
  layers=result['slide']['layers'];self.assertEqual([x['type'] for x in layers],['shape','image'])
  overlay=Image.open(io.BytesIO(base64.b64decode(layers[-1]['src'].split(',')[1])))
  self.assertEqual(overlay.getpixel((40,40)),(255,0,0,255));self.assertEqual(overlay.getpixel((0,0))[3],0)
  self.assertEqual(result['reference']['image'],data(im))
 def test_out_of_bounds_polygon_rejected(self):
  with self.assertRaises(ValueError):convert_image({'image':data(Image.new('RGB',(100,100))),'blocks':[],'occlusions':[{'points':[[0,0],[101,0],[0,20]]}]})

class PanelDetection(unittest.TestCase):
 def test_solid_panel_proposal_does_not_select_whole_background(self):
  from image_conversion import detect_panels
  im=Image.new('RGB',(200,150),'white');ImageDraw.Draw(im).rectangle((30,40,150,110),fill='#224466')
  result=detect_panels(im)
  self.assertTrue(any(p['x']==30 and p['y']==40 and p['w']==121 and p['h']==71 and p['color']=='#224466' for p in result))
  self.assertTrue(all(p['selected'] is False for p in result))

class FontBounds(unittest.TestCase):
 def test_font_mime_must_match_actual_signature(self):
  raw=Path('C:/Windows/Fonts/arial.ttf').read_bytes()
  face={'name':'Wrong OTF','data':'data:font/otf;base64,'+base64.b64encode(raw).decode()}
  with self.assertRaises(ValueError):convert_image({'image':data(Image.new('RGB',(100,100))),'blocks':[],'fonts':[face]})
