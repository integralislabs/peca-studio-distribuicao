import base64,io,unittest
from types import SimpleNamespace
from unittest.mock import patch
from PIL import Image
from image_conversion import analyze_image,convert_image

class OCRTSVQuotes(unittest.TestCase):
 def test_literal_quote_does_not_swallow_next_ocr_records(self):
  image=Image.new('RGB',(400,200),'white');buf=io.BytesIO();image.save(buf,format='PNG');uri='data:image/png;base64,'+base64.b64encode(buf.getvalue()).decode()
  header='level\tpage_num\tblock_num\tpar_num\tline_num\tword_num\tleft\ttop\twidth\theight\tconf\ttext\r\n'
  rows='5\t1\t1\t1\t1\t1\t10\t10\t10\t20\t90\t"\r\n5\t1\t1\t1\t2\t1\t10\t40\t90\t20\t95\tPreço\r\n'
  with patch('image_conversion.subprocess.run',return_value=SimpleNamespace(returncode=0,stdout=(header+rows).encode())):
   result=analyze_image({'image':uri})
  self.assertEqual([b['text'] for b in result['blocks']],['"','Preço'])
  self.assertFalse(any('\t' in b['text'] or '\n' in b['text'] for b in result['blocks']))
  converted=convert_image({'image':uri,'blocks':result['blocks']})
  self.assertEqual([l['text'] for l in converted['slide']['layers']],['"','Preço'])
 def test_one_hundred_quote_words_keep_one_hundred_lines(self):
  buf=io.BytesIO();Image.new('RGB',(400,400),'white').save(buf,format='PNG');uri='data:image/png;base64,'+base64.b64encode(buf.getvalue()).decode()
  header='level\tpage_num\tblock_num\tpar_num\tline_num\tword_num\tleft\ttop\twidth\theight\tconf\ttext\n'
  rows=''.join(f'5\t1\t1\t1\t{i+1}\t1\t10\t10\t10\t20\t90\t"\n' for i in range(100))
  with patch('image_conversion.subprocess.run',return_value=SimpleNamespace(returncode=0,stdout=(header+rows).encode())):result=analyze_image({'image':uri})
  self.assertEqual(len(result['blocks']),100);self.assertTrue(all(b['text']=='"' for b in result['blocks']))
