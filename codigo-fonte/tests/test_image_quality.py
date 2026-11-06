import unittest
from image_quality import assert_image_quality, image_qa_hash
class ImageQualityTests(unittest.TestCase):
 def piece(self):
  p={'slides':[{'layers':[{'type':'text','text':'Preço'}]}],'imageConversion':{'reference':{'image':'data:original'},'report':{'blocks':[{'id':'a','text':'Preço'}],'warnings':[]}}};r=p['imageConversion'];q={'schemaVersion':2,'status':'passed','reviewedAt':'now','metrics':{'regions':[{'id':'a','foregroundIoU':.85,'pixelsWithin20':.9}]},'exceptions':[]};r['qa']=q
  for k,v in [('slideHash',{'slide':p['slides'][0],'fonts':p.get('fonts',[])}),('referenceHash',r['reference']),('blocksHash',r['report']['blocks']),('reportHash',r['report'])]:q[k]=image_qa_hash(v)
  return p
 def test_thresholds_and_edits(self):
  p=self.piece();assert_image_quality(p);p['imageConversion']['reference']['image']='edit'
  with self.assertRaises(ValueError):assert_image_quality(p)
 def test_replacing_font_bytes_invalidates_approval(self):
  p=self.piece();assert_image_quality(p);p['fonts']=[{'name':'Fonte','data':'bytes changed'}]
  with self.assertRaises(ValueError):assert_image_quality(p)
 def test_legacy_review_rejected(self):
  p=self.piece();p['imageConversion']['qa']['status']='reviewed'
  with self.assertRaises(ValueError):assert_image_quality(p)
 def test_bound_exception_and_missing_metrics(self):
  p=self.piece();q=p['imageConversion']['qa'];q['metrics']['regions'][0]['foregroundIoU']=.2
  with self.assertRaises(ValueError):assert_image_quality(p)
  q['exceptions']=[dict(id='a',reason='Alteração intencional',**{k:q[k] for k in ['slideHash','referenceHash','blocksHash','reportHash']})];q['status']='exception-approved';assert_image_quality(p);q['metrics']['regions']=[]
  with self.assertRaises(ValueError):assert_image_quality(p)
 def test_missing_duplicate_text(self):
  p=self.piece();r=p['imageConversion'];r['report']['blocks'].append({'id':'b','text':'Preço'});r['qa']['metrics']['regions'].append({'id':'b','foregroundIoU':1,'pixelsWithin20':1});r['qa']['blocksHash']=image_qa_hash(r['report']['blocks']);r['qa']['reportHash']=image_qa_hash(r['report'])
  with self.assertRaises(ValueError):assert_image_quality(p)
 def test_integer_float_canonical(self):self.assertEqual(image_qa_hash({'b':1.0,'a':'Preço'}),image_qa_hash({'a':'Preço','b':1}))
 def test_unconverted(self):assert_image_quality({'slides':[]})
 def test_hash_vectors_from_javascript(self):
  self.assertEqual(image_qa_hash({'b':1.0,'a':'Preço'}),'e7c4b8d265a22cbf14e08a9db9823ea05953bd098add0e422f4f88c138b9b34e')
  self.assertEqual(image_qa_hash({'n':.000001,'t':1e21,'z':1e-7}),'a51fdc4e7b3b111e1a7c2279c0f2b9413c24455c080c6ffd3a6060d69269c07a')
 def test_blocking_warning_and_informational_notice(self):
  p=self.piece();r=p['imageConversion'];r['report']['notices']=['Aproximado'];r['qa']['reportHash']=image_qa_hash(r['report']);assert_image_quality(p)
  r['report']['warnings']=['Fonte ausente'];r['qa']['reportHash']=image_qa_hash(r['report'])
  with self.assertRaises(ValueError):assert_image_quality(p)
