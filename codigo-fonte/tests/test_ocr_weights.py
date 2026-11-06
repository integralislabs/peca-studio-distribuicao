import base64,io,unittest
from pathlib import Path
from fontTools.ttLib import TTFont
from image_conversion import portable_ocr_fonts

class OCRWeightTests(unittest.TestCase):
 def test_variable_font_produces_portable_real_weight_instances(self):
  path=Path('C:/Windows/Fonts/bahnschrift.ttf')
  if not path.exists():self.skipTest('Windows variable font fixture unavailable')
  source={'name':'Fonte propria','data':'data:font/ttf;base64,'+base64.b64encode(path.read_bytes()).decode()}
  fonts=portable_ocr_fonts([source]);self.assertEqual(len(fonts),5)
  self.assertEqual([f['name'] for f in fonts],['Fonte propria W300','Fonte propria W400','Fonte propria W500','Fonte propria W600','Fonte propria W700'])
  for weight,font in zip(range(300,701,100),fonts):
   face=TTFont(io.BytesIO(base64.b64decode(font['data'].split(',')[1])))
   self.assertNotIn('fvar',face);self.assertEqual(face['OS/2'].usWeightClass,weight)

if __name__=='__main__':unittest.main()
