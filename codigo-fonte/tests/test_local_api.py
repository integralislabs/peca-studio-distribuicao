import unittest,threading,tempfile,json,http.client,importlib.util
from pathlib import Path
from http.server import ThreadingHTTPServer
from server import Handler

class LocalHTTPTests(unittest.TestCase):
 def test_revision_poll_has_no_library_payload_and_caches_unchanged_file(self):
  from local_api import LocalAPI
  from unittest.mock import patch
  api=LocalAPI(self.server,Path(self.tmp.name)/'app')
  state={'version':1,'projects':[],'pieces':[]};path=str(Path(self.tmp.name)/'poll')
  api.dispatch('/api/local/workspace',{'action':'activate','path':path,'mode':'migrate','data':state})
  with patch.object(api.service.store,'read',wraps=api.service.store.read) as read:
   for _ in range(10):
    status=api.dispatch('/api/local/workspace-status');self.assertEqual(status['revision'],1);self.assertNotIn('data',status)
   self.assertLessEqual(read.call_count,1)
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.server=ThreadingHTTPServer(('127.0.0.1',0),Handler);self.server.local_config_dir=Path(self.tmp.name)/'config';self.thread=threading.Thread(target=self.server.serve_forever,daemon=True);self.thread.start()
 def tearDown(self):self.server.shutdown();self.server.server_close();self.thread.join();self.tmp.cleanup()
 def request(self,path,method='GET',data=None,headers=None):
  port=self.server.server_port;h={'Origin':f'http://127.0.0.1:{port}','Content-Type':'application/json','X-Peca-Request':'1',**(headers or {})};c=http.client.HTTPConnection('127.0.0.1',port);c.request(method,path,body=None if data is None else json.dumps(data),headers=h);r=c.getresponse();body=r.read();c.close();return r.status,json.loads(body)
 def test_explicit_migration_revisions_and_no_silent_replace(self):
  status,body=self.request('/api/local/workspace');self.assertEqual(status,200);self.assertFalse(body['active'])
  state={'version':1,'projects':[],'pieces':[]};path=str(Path(self.tmp.name)/'acervo')
  status,body=self.request('/api/local/workspace','POST',{'action':'activate','path':path,'mode':'migrate','data':state});self.assertEqual(status,200);self.assertEqual(body['revision'],1)
  status,body=self.request('/api/local/workspace','POST',{'action':'write','data':state,'expectedRevision':0,'expectedPath':path});self.assertEqual(status,409)
  status,body=self.request('/api/local/workspace','POST',{'action':'activate','path':path,'mode':'migrate','data':state});self.assertEqual(status,409)
 def test_mcp_requires_local_token_or_same_origin_and_hidden_files(self):
  status,body=self.request('/api/local/mcp','POST',{'name':'projects_list'},headers={'Origin':'https://evil.invalid','X-Peca-Request':'0'});self.assertEqual(status,403)
  status,body=self.request('/api/local/config');self.assertEqual(status,200);self.assertIn('mcpConfig',body);self.assertNotIn('token',json.dumps(body).lower().replace('token-file','file').replace('mcp-token','file'))
 def test_pdf_route_returns_real_document(self):
  p={'title':'P','slides':[{'width':100,'height':100,'bg':'#ffffff','layers':[]}]}
  status,body=self.request('/api/local/export/pdf','POST',{'piece':p});self.assertEqual(status,200);self.assertEqual(body['mime'],'application/pdf')

if __name__=='__main__':unittest.main()
