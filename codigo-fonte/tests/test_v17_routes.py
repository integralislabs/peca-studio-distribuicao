"""Real loopback HTTP regressions; private temporary config, no external calls."""
import base64,datetime as dt,http.client,io,json,re,subprocess,tempfile,threading,unittest,zlib
from pathlib import Path
from unittest.mock import patch
from http.server import ThreadingHTTPServer
from server import Handler
from local_api import get_api
from workspace_service import validate_state
from print_service import export_pdf,PrintError

class Vault:
 def __init__(self,root):self.values={}
 def get(self,key,default=None):return self.values.get(key,default)
 def set(self,key,value):self.values[key]=value
 def delete(self,key):self.values.pop(key,None)
class FixtureAdapter:
 def __init__(self):self.published=[];self.validations=0
 def validate(self,a,token):self.validations+=1;return {'sub':'fixture-person'}
 def publish(self,a,token,item,media):self.published.append(item['id']);return {'fixture':True}
class QuietHandler(Handler):
 def log_message(self,*args):pass
class Routes(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.server=ThreadingHTTPServer(('127.0.0.1',0),QuietHandler);self.server.local_config_dir=Path(self.tmp.name);self.port=self.server.server_port
  with patch('local_secrets.SecretStore',Vault):self.api=get_api(self.server,Path(__file__).resolve().parents[1])
  self.adapter=FixtureAdapter();self.api.publishing.adapter=self.adapter
  self.thread=threading.Thread(target=self.server.serve_forever,daemon=True);self.thread.start()
 def tearDown(self):self.api.publishing.stop();self.server.shutdown();self.server.server_close();self.thread.join();self.tmp.cleanup()
 def request(self,path,data=None,headers=None,raw=None,method=None,default_auth=True):
  h={'Content-Type':'application/json'}
  if default_auth:h.update({'X-Peca-Request':'1','Origin':f'http://127.0.0.1:{self.port}'})
  h.update(headers or {});body=raw if raw is not None else json.dumps(data).encode() if data is not None else None
  c=http.client.HTTPConnection('127.0.0.1',self.port,timeout=5);c.request(method or ('POST' if body is not None else 'GET'),path,body=body,headers=h);r=c.getresponse();status=r.status;rh=dict(r.headers);content=r.read();c.close();return status,rh,content
 def json_request(self,path,data):
  status,_,body=self.request(path,data);return status,json.loads(body)
 def test_binary_upload_and_file_authorization(self):
  # Transport contract uses real upload storage/probe, with only codec detection stubbed.
  with patch.object(self.api.media,'_probe',return_value={'duration':1,'video':True,'audio':False}):
   status,_,raw=self.request('/api/local/media/upload',raw=b'private-fixture-bytes',headers={'Content-Type':'application/octet-stream','X-Peca-Filename':'v%C3%ADdeo%20teste.mp4'})
  self.assertEqual(status,200);asset=json.loads(raw);self.assertEqual(asset['name'],'vídeo teste.mp4')
  path='/api/local/media/file?id='+asset['assetId']
  self.assertEqual(self.request(path,default_auth=False)[0],403)
  self.assertEqual(self.request(path,default_auth=False,headers={'Sec-Fetch-Site':'cross-site','Referer':'https://evil.example/'})[0],403)
  self.assertEqual(self.request(path,default_auth=False,headers={'Sec-Fetch-Site':'same-origin','Referer':'http://localhost:'+str(self.port)+'/'})[0],403)
  status,h,body=self.request(path,default_auth=False,headers={'Sec-Fetch-Site':'same-origin','Referer':f'http://127.0.0.1:{self.port}/index.html'})
  self.assertEqual((status,body),(200,b'private-fixture-bytes'));self.assertEqual(h['Cache-Control'],'no-store');self.assertEqual(h['Content-Type'],'video/mp4')
  self.assertEqual(self.request('/api/local/media/file?id=..%2Fcredentials.dpapi')[0],400)
  self.assertEqual(self.request('/.local/media/'+asset['file'])[0],404)
 def test_upload_rejects_cross_origin_and_oversize_without_reading_body(self):
  with patch.object(self.api.media,'upload') as call:
   self.assertEqual(self.request('/api/local/media/upload',raw=b'abc',headers={'Origin':'https://evil.example'})[0],403)
   self.assertEqual(self.request('/api/local/media/upload',raw=b'',headers={'Content-Length':'250000001'})[0],413)
   call.assert_not_called()
 def test_publication_routes_do_not_publish_until_approved_and_enabled(self):
  self.assertEqual(self.request('/api/local/publishing/status',data={},headers={'X-Peca-Request':'0'})[0],403)
  status,a=self.json_request('/api/local/publishing/connect',{'provider':'linkedin','target':'urn:li:person:fixture-person','apiVersion':'202610','token':'fixture-secret','label':'Fixture only'})
  self.assertEqual(status,200);self.assertNotIn('fixture-secret',json.dumps(a))
  status,v=self.json_request('/api/local/publishing/validate',{'accountId':a['id']});self.assertEqual(status,200);self.assertTrue(v['validated']);self.assertFalse(v['publicationTested']);self.assertEqual(self.adapter.published,[])
  args={'accountId':a['id'],'when':(dt.datetime.now(dt.timezone.utc)-dt.timedelta(minutes=1)).isoformat(),'payload':{'text':'Fixture, never a real post'}}
  status,j=self.json_request('/api/local/publishing/schedule',args);self.assertEqual(status,200);self.assertEqual(j['status'],'draft');self.assertEqual(self.json_request('/api/local/publishing/schedule',args)[1]['id'],j['id'])
  self.assertEqual(self.json_request('/api/local/publishing/confirm',{'id':j['id'],'target':'wrong','approved':True})[0],400)
  self.api.publishing.run_due();self.assertEqual(self.adapter.published,[])
  self.assertEqual(self.json_request('/api/local/publishing/confirm',{'id':j['id'],'target':a['target'],'approved':True})[0],200)
  self.api.publishing.run_due();self.assertEqual(self.adapter.published,[])
  with patch.object(self.api.publishing,'start') as start:
   self.assertEqual(self.json_request('/api/local/publishing/enable',{'enabled':True})[0],200);start.assert_called_once()
  self.api.publishing.run_due();self.api.publishing.run_due();self.assertEqual(self.adapter.published,[j['id']])
  status,result=self.json_request('/api/local/publishing/status',{});self.assertEqual(status,200);self.assertEqual(result['queue'][0]['status'],'published');self.assertNotIn('fixture-secret',json.dumps(result))

class ReviewRegressions(unittest.TestCase):
 def test_print_rejects_nonpositive_printable_area(self):
  p={'title':'fixture','slides':[{'width':1080,'height':1350,'bg':'#ffffff','layers':[]}]}
  with self.assertRaises(PrintError):export_pdf({'piece':p,'options':{'paper':'custom','paperWidthMm':20,'paperHeightMm':20,'bleedMm':20}})
 def test_cmyk_crop_marks_emit_cmyk_operator(self):
  p={'title':'fixture','slides':[{'width':1080,'height':1350,'bg':'#ffffff','layers':[]}]};r=export_pdf({'piece':p,'options':{'colorSpace':'cmyk','cropMarks':True}});raw=base64.b64decode(r['base64']);streams=[]
  for stream in re.findall(rb'stream\r?\n(.*?)endstream',raw,re.S):
   try:streams.append(zlib.decompress(base64.a85decode(stream,adobe=True)))
   except Exception:pass
  joined=b'\n'.join(streams);self.assertIn(b' K',joined);self.assertNotRegex(joined,rb'\b(?:rg|RG)\b')
 def test_empty_trash_snapshot_rejected_python_and_js(self):
  invalid={'version':1,'projects':[],'pieces':[],'trash':[{'id':'trashfixture','kind':'piece','deletedAt':'2026-11-05T10:00:00.000Z','snapshot':{'version':1,'projects':[],'pieces':[]}}]}
  with self.assertRaises(ValueError):validate_state(invalid)
  code="import {validateState} from './model.js';try{validateState("+json.dumps(invalid)+");process.exit(1)}catch{process.exit(0)}"
  r=subprocess.run(['node','--input-type=module','-e',code],cwd=Path(__file__).resolve().parents[1],capture_output=True);self.assertEqual(r.returncode,0,r.stderr.decode())
if __name__=='__main__':unittest.main()
