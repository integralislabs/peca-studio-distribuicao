import json,tempfile,unittest
from pathlib import Path
from types import SimpleNamespace
from local_api import LocalAPI

class CommercialGateTests(unittest.TestCase):
 def test_commercial_unconfigured_cannot_use_mutations_ai_exports_or_mcp(self):
  with tempfile.TemporaryDirectory() as tmp:
   root=Path(tmp);app=root/'app';app.mkdir();(app/'integralis-config.json').write_text(json.dumps({'mode':'commercial'}))
   api=LocalAPI(SimpleNamespace(server_port=17866,local_config_dir=root/'data'),app)
   self.assertFalse(api.dispatch('/api/local/integralis/status')['allowed'])
   self.assertEqual(api.dispatch('/api/local/workspace-status'),{'active':False})
   for path,body in [('/api/local/integralis/authorize',{}),('/api/local/html/render',{}),('/api/local/export/pdf',{}),('/api/local/image/convert',{}),('/api/local/publishing/confirm',{}),('/api/local/mcp',{'name':'pieces_create','arguments':{}})]:
    with self.subTest(path=path),self.assertRaises(PermissionError):api.dispatch(path,body)
 def test_development_is_explicitly_identified_not_commercial_access(self):
  with tempfile.TemporaryDirectory() as tmp:
   api=LocalAPI(SimpleNamespace(server_port=17866,local_config_dir=Path(tmp)/'data'),Path(tmp)/'source')
   status=api.dispatch('/api/local/integralis/status');self.assertEqual(status['mode'],'development');self.assertIn('desenvolvimento',status['message'])

if __name__=='__main__':unittest.main()
