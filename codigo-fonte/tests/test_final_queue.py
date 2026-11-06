import unittest,tempfile,base64,copy
from workspace_service import StudioService
F={'name':'Demo','data':'data:font/ttf;base64,AAEAAAAAAAAAAAAAAAAAAAAAAAA='}
class QueueTests(unittest.TestCase):
 def setup_service(self,d):
  s=StudioService(d);p=s.dispatch('projects_create',{'name':'P','expectedRevision':0})['result'];p=s.dispatch('pieces_create',{'projectId':p['id'],'expectedRevision':1})['result'];return s,p
 def test_global_fonts_snapshot_and_conflict(self):
  with tempfile.TemporaryDirectory() as d:
   s,p=self.setup_service(d);state=s.store.read();state['data']['fonts']=[F];state['data']['pieces'][0]['slides'][0]['layers'][0]['font']='Demo';s.store.write(state['data'],2)
   job=s.dispatch('pieces_export',{'pieceId':p['id'],'expectedRevision':3})['result'];self.assertEqual(job['piece']['fonts'],[F])
   state=s.store.read();state['data']['pieces'][0]['fonts']=[{**F,'data':'data:font/ttf;base64,AAEAAAAAAAAAAAAAAAAAAAAAAAE='}];s.store.write(state['data'],state['revision'])
   with self.assertRaisesRegex(ValueError,'[Ff]ont'):s.dispatch('pieces_export',{'pieceId':p['id'],'expectedRevision':state['revision']+1})
 def test_completion_discards_snapshot_and_limits_queue(self):
  with tempfile.TemporaryDirectory() as d:
   s,p=self.setup_service(d);job=s.dispatch('pieces_export',{'pieceId':p['id'],'expectedRevision':2})['result'];done=s.complete_export(job['id'],{'mime':'image/png','base64':base64.b64encode(b'\x89PNG\r\n\x1a\nfixture').decode()})['result'];self.assertNotIn('piece',done);self.assertIn('sha256',done)
   state=s.store.read();template={**job,'status':'pending'};state['data']['exportJobs']=[{**template,'id':str(i)} for i in range(32)];s.store.write(state['data'],state['revision'])
   with self.assertRaisesRegex(ValueError,'32'):s.dispatch('pieces_export',{'pieceId':p['id'],'expectedRevision':state['revision']+1})

 def test_history_pruning_keeps_export_files(self):
  with tempfile.TemporaryDirectory() as d:
   s,p=self.setup_service(d);job=s.dispatch('pieces_export',{'pieceId':p['id'],'expectedRevision':2})['result'];state=s.store.read();state['data']['exportJobs']=[{'id':str(i),'status':'complete','pieceId':p['id'],'sha256':'old'} for i in range(256)]+[job];s.store.write(state['data'],state['revision']);asset=s.store.asset_path('exports/old.png');asset.parent.mkdir();asset.write_bytes(b'old');s.complete_export(job['id'],{'mime':'image/png','base64':base64.b64encode(b'\x89PNG\r\n\x1a\nfixture').decode()});jobs=s.store.read()['data']['exportJobs'];self.assertEqual(len(jobs),256);self.assertFalse(any(j['id']=='0' for j in jobs));self.assertEqual(asset.read_bytes(),b'old')
