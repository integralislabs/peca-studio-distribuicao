import base64,io,tempfile,unittest
from pathlib import Path
from pypdf import PdfReader
from print_service import export_pdf,PrintError
from local_secrets import SecretStore
from test_print_export import piece

class V17Print(unittest.TestCase):
 def test_cmyk_keeps_soft_alpha_mask(self):
  from PIL import Image
  p=piece();buf=io.BytesIO();im=Image.new('RGBA',(10,10),(255,0,0,0));im.putpixel((5,5),(0,255,0,127));im.save(buf,format='PNG');p['slides'][0]['bg']='#123456'
  p['slides'][0]['layers']=[{'type':'image','visible':True,'x':10,'y':20,'w':50,'h':50,'src':'data:image/png;base64,'+base64.b64encode(buf.getvalue()).decode()}]
  r=export_pdf({'piece':p,'options':{'colorSpace':'cmyk'}});pdf=PdfReader(io.BytesIO(base64.b64decode(r['base64'])));objects=[o.get_object() for o in pdf.pages[0]['/Resources']['/XObject'].values()];image=next(o for o in objects if o.get('/ColorSpace')=='/DeviceCMYK');self.assertEqual(image['/SMask'].get_object().get_data(),im.getchannel('A').tobytes())
 def test_cmyk_vectors_crop_and_image(self):
  from PIL import Image
  p=piece();buf=io.BytesIO();Image.new('RGB',(10,10),'red').save(buf,format='PNG')
  p['slides'][0]['layers'].append({'type':'image','visible':True,'x':10,'y':200,'w':50,'h':50,'src':'data:image/png;base64,'+base64.b64encode(buf.getvalue()).decode()})
  r=export_pdf({'piece':p,'options':{'colorSpace':'cmyk','cropMarks':True}});pdf=PdfReader(io.BytesIO(base64.b64decode(r['base64'])));stream=pdf.pages[0].get_contents().get_data()
  self.assertEqual(r['colorSpace'],'cmyk');self.assertFalse(r['iccEmbedded']);self.assertNotIn(b' RG',stream);self.assertIn(b' k',stream)
  images=pdf.pages[0]['/Resources']['/XObject'];self.assertTrue(any(x.get_object().get('/ColorSpace')=='/DeviceCMYK' for x in images.values()))
 def test_invalid_profile_and_no_printable_area(self):
  for opt in [{'colorSpace':'cmyk','iccBase64':'AAAA'},{'paper':'custom','paperWidthMm':20,'paperHeightMm':20,'bleedMm':20}]:
   with self.assertRaises(ValueError):export_pdf({'piece':piece(),'options':opt})
 def test_dpapi_persists_without_plaintext(self):
  with tempfile.TemporaryDirectory() as root:
   vault=SecretStore(root);vault.set('test','fixture-secret-value');self.assertNotIn(b'fixture-secret-value',vault.path.read_bytes());self.assertEqual(SecretStore(root).get('test'),'fixture-secret-value');vault.delete('test');self.assertIsNone(vault.get('test'))
