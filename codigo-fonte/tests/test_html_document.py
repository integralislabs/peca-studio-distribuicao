import unittest
from html_document import prepare_document, update_document, render_document,validate_document

SOURCE='''<!doctype html><html><head><style>:root{--size:32px}.frame{width:300px;height:400px;background:linear-gradient(red,blue)}h1{font-size:var(--size)}</style></head><body><section class="frame" data-export-frame data-width="300" data-height="400"><h1 data-editable="title">Oferta &amp; ação</h1><span data-adjust="--size" data-min="12" data-max="100" data-unit="px">Tamanho</span></section></body></html>'''

class HTMLDocumentTests(unittest.TestCase):
 def test_preserves_css_and_explicit_editable_contract(self):
  d=prepare_document(SOURCE)
  self.assertEqual(validate_document(d),d)
  self.assertEqual(d['editables'][0]['key'],'title')
  self.assertEqual(d['editables'][0]['value'],'Oferta & ação')
  self.assertEqual(d['controls'][0]['variable'],'--size')
  self.assertIn('linear-gradient(red,blue)',d['html'])
  self.assertEqual(d['frames'][0]['width'],300)
 def test_text_updates_escape_markup_and_controls_are_connected(self):
  d=update_document(prepare_document(SOURCE),texts={'title':'<script>alert(1)</script>'},controls={'--size':44})
  self.assertIn('&lt;script&gt;',d['html'])
  self.assertIn('--size:44px',d['html'])
  self.assertEqual(d['editables'][0]['value'],'<script>alert(1)</script>')
 def test_active_content_external_resources_duplicates_unwired_controls_rejected(self):
  for source in [SOURCE.replace('<h1','<h1 onclick="x()"'),SOURCE+'<script>alert(1)</script>',SOURCE+'<img src="https://example.com/x">',SOURCE.replace('--size)','--missing)'),SOURCE.replace('</section>','<p data-editable="title">dup</p></section>')]:
   with self.subTest(source=source[-90:]),self.assertRaises(ValueError):prepare_document(source)
 def test_unknown_changes_do_not_silently_succeed(self):
  d=prepare_document(SOURCE)
  with self.assertRaises(ValueError):update_document(d,texts={'missing':'x'})
  with self.assertRaises(ValueError):update_document(d,controls={'--size':1000})
 def test_invalid_embedded_font_and_image_are_blocked(self):
  for bad in ['<img src="data:image/png;base64,aGVsbG8=">','<style>@font-face{font-family:x;src:url(data:font/ttf;base64,aGVsbG8=)}</style>']:
   with self.assertRaises(ValueError):prepare_document(SOURCE+bad)
 def test_source_of_truth_cannot_be_replaced_by_forged_metadata(self):
  d=prepare_document(SOURCE);d['editables']=[]
  with self.assertRaises(ValueError):update_document(d,texts={'title':'x'})

if __name__=='__main__':unittest.main()
