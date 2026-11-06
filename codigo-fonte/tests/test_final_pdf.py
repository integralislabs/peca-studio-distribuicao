import unittest,base64,io
from pathlib import Path
from PIL import Image,ImageDraw,ImageFont
from print_service import export_pdf,PrintError
from test_print_export import piece
class StyledFonts(unittest.TestCase):
 def test_custom_regular_preserves_synthetic_style_as_vector_with_warning(self):
  raw=Path('C:/Windows/Fonts/arial.ttf').read_bytes();p=piece();p['fonts']=[{'name':'Custom','data':'data:font/ttf;base64,'+base64.b64encode(raw).decode()}];l=p['slides'][0]['layers'][0];l.update(font='Custom',bold=True,italic=True)
  result=export_pdf({'piece':p});self.assertTrue(result['vectorText']);self.assertTrue(any('sintetizado' in w for w in result['warnings']))
  from pypdf import PdfReader
  stream=PdfReader(io.BytesIO(base64.b64decode(result['base64']))).pages[0].get_contents().get_data()
  self.assertIn(b' c',stream);self.assertNotIn(b'/Subtype /Image',stream)
  l.update(bold=False,italic=False);regular=export_pdf({'piece':p});self.assertNotEqual(result['base64'],regular['base64'])
