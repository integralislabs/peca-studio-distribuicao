import unittest,tempfile
from print_service import export_pdf
from publishing_service import PublicationService
class Secrets:
 def __init__(self):self.values={}
 def set(self,k,v):self.values[k]=v
 def get(self,k):return self.values.get(k)
 def delete(self,k):self.values.pop(k,None)
class PublicationQuality(unittest.TestCase):
 def test_worker_rechecks_commercial_access_before_external_call(self):
  class Adapter:
   calls=0
   def publish(self,*args):self.calls+=1;return {'ok':True}
  with tempfile.TemporaryDirectory() as root:
   adapter=Adapter();service=PublicationService(root,Secrets(),adapter);a=service.dispatch('connect',{'provider':'linkedin','target':'urn:li:person:test','token':'local-test','apiVersion':'202611'})
   service.dispatch('schedule',{'accountId':a['id'],'when':'2026-11-05T00:00:00+00:00','payload':{'text':'teste'}});j=service.state['queue'][0];j.update(status='scheduled',approved=True);service.state['enabled']=True
   def denied():raise PermissionError('revoked')
   service.access_guard=denied;service.run_due();self.assertEqual(j['status'],'blocked');self.assertEqual(adapter.calls,0)
 def test_print_rejects_unreviewed_conversion(self):
  p={'slides':[{'width':100,'height':100,'layers':[]}],'imageConversion':{}}
  with self.assertRaisesRegex(ValueError,'QA'):export_pdf({'piece':p})
 def test_draft_allowed_but_confirmation_rejects_unreviewed_conversion(self):
  with tempfile.TemporaryDirectory() as root:
   service=PublicationService(root,Secrets());a=service.dispatch('connect',{'provider':'linkedin','target':'urn:li:person:test','token':'local-test','apiVersion':'202611'})
   j=service.dispatch('schedule',{'accountId':a['id'],'when':'2026-11-05T00:00:00+00:00','payload':{'text':'rascunho'},'piece':{'slides':[],'imageConversion':{}}})
   self.assertEqual(j['status'],'draft')
   with self.assertRaisesRegex(ValueError,'QA'):service.dispatch('confirm',{'id':j['id'],'approved':True,'target':a['target']})
 def test_worker_rechecks_edited_queued_snapshot_before_external_call(self):
  class Adapter:
   calls=0
   def publish(self,*args):self.calls+=1;return {'ok':True}
  with tempfile.TemporaryDirectory() as root:
   adapter=Adapter();service=PublicationService(root,Secrets(),adapter);a=service.dispatch('connect',{'provider':'linkedin','target':'urn:li:person:test','token':'local-test','apiVersion':'202611'});j=service.dispatch('schedule',{'accountId':a['id'],'when':'2026-11-05T00:00:00+00:00','payload':{'text':'rascunho'},'piece':{'slides':[]}});service.dispatch('confirm',{'id':j['id'],'approved':True,'target':a['target']});service.state['queue'][0]['piece']['imageConversion']={};service.state['enabled']=True;service.run_due();self.assertEqual(service.state['queue'][0]['status'],'blocked');self.assertEqual(adapter.calls,0)
