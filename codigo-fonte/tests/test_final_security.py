import unittest,tempfile,json
from pathlib import Path
from types import SimpleNamespace
from local_api import LocalAPI
from server import Handler
class FinalSecurity(unittest.TestCase):
 def test_every_application_module_is_public(self):
  root=Path(__file__).resolve().parents[1]
  for module in root.glob('*.js'):
   with self.subTest(module=module.name):self.assertTrue(Handler.public_static(root,module))
 def test_reject_public_subdirectory_workspace(self):
  with tempfile.TemporaryDirectory() as d:
   root=Path(d);api=LocalAPI(SimpleNamespace(server_port=123),root)
   for child in ['custom','docs/work','tests/work','evidencias/work']:
    with self.subTest(child=child),self.assertRaises(ValueError):api.dispatch('/api/local/workspace',{'action':'activate','mode':'open','path':str(root/child)})
 def test_static_policy_independent_of_api(self):
  with tempfile.TemporaryDirectory() as d:
   root=Path(d)
   for folder in ['customA','customB','workspace-data','docs/old']:
    p=root/folder;p.mkdir(parents=True);(p/'workspace.json').write_text('{}');(p/'secret.png').write_bytes(b'private')
    self.assertFalse(Handler.public_static(root,p/'workspace.json'))
    self.assertFalse(Handler.public_static(root,p/'secret.png'))
   self.assertTrue(Handler.public_static(root,root/'app.js'))
   self.assertTrue(Handler.public_static(root,root))

class StaticHTTPRegression(unittest.TestCase):
 def test_legacy_workspace_a_b_and_restart_remain_private(self):
  import http.client,threading
  from http.server import ThreadingHTTPServer
  from unittest.mock import patch
  import server
  from workspace_service import StudioService
  with tempfile.TemporaryDirectory() as d:
   root=Path(d);a=root/'legacyA';b=root/'legacyB'
   StudioService(a).store.write({'version':1,'projects':[],'pieces':[]},0);StudioService(b).store.write({'version':1,'projects':[],'pieces':[]},0)
   with patch.object(server,'ROOT',root):
    for restart in range(2):
     httpd=ThreadingHTTPServer(('127.0.0.1',0),Handler);httpd.local_config_dir=root/'.config';thread=threading.Thread(target=httpd.serve_forever,daemon=True);thread.start()
     try:
      def request(path):
       c=http.client.HTTPConnection('127.0.0.1',httpd.server_port);c.request('GET',path);r=c.getresponse();r.read();c.close();return r.status
      for folder in ('legacyA','legacyB'):self.assertEqual(request('/'+folder+'/workspace.json'),404)
      api=LocalAPI(httpd,root);httpd.studio_local_api=api
      for folder in (a,b):
       api.service=StudioService(folder);api._configure(str(folder))
       for name in ('legacyA','legacyB'):self.assertEqual(request('/'+name+'/workspace.json'),404)
     finally:httpd.shutdown();httpd.server_close();thread.join()
