import http.client
import json
import sys
import threading
import unittest
from http.server import ThreadingHTTPServer
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from server import Handler

class TestHandler(Handler):
    ai_keys={'openai':'','claude':'','gemini':''}
    ai_lock=threading.Lock()
    def log_message(self,*args): pass

class HTTPTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server=ThreadingHTTPServer(('127.0.0.1',0),TestHandler)
        cls.thread=threading.Thread(target=cls.server.serve_forever,daemon=True);cls.thread.start()
        cls.port=cls.server.server_port
    @classmethod
    def tearDownClass(cls): cls.server.shutdown();cls.server.server_close();cls.thread.join()
    def request(self,path,method='GET',data=None,headers=None):
        conn=http.client.HTTPConnection('127.0.0.1',self.port,timeout=3)
        h={'Origin':f'http://127.0.0.1:{self.port}','X-Peca-Request':'1','Content-Type':'application/json'}
        h.update(headers or {})
        conn.request(method,path,body=json.dumps(data) if data is not None else None,headers=h)
        result=conn.getresponse();status=result.status;body=result.read();conn.close();return status,body
    def test_key_not_echoed_or_served(self):
        status,body=self.request('/api/ai/config','POST',{'key':'sk-test-secret-value'})
        self.assertEqual(status,200);self.assertNotIn(b'sk-test',body)
        self.assertNotIn(b'sk-test',self.request('/api/ai/config')[1])
        self.request('/api/ai/config','POST',{'key':''})
        for path in ['/.git/config','/.env','/server.py','/tests/qa_server.py','/%2egit/config']:
            self.assertEqual(self.request(path)[0],404)
            self.assertEqual(self.request(path,'HEAD')[0],404)
    def test_origin_header_and_consent_required(self):
        for headers in [{'Origin':'https://evil.example'},{'X-Peca-Request':'0'},{'Host':'evil.example'}]:
            self.assertEqual(self.request('/api/ai/content','POST',{},headers)[0],403)
        self.assertEqual(self.request('/api/ai/content','POST',{})[0],400)
    def test_missing_key_and_oversize(self):
        TestHandler.ai_keys={'openai':'','claude':'','gemini':''}
        self.assertEqual(self.request('/api/ai/image','POST',{'consent':True,'prompt':'planta','format':'feed'})[0],409)
        self.assertEqual(self.request('/api/ai/config','POST',{'key':'x'*33000})[0],413)
    def test_server_busy_does_not_call_provider(self):
        TestHandler.ai_lock.acquire()
        try:
            with patch('server.generate_content') as call:
                self.assertEqual(self.request('/api/ai/content','POST',{'consent':True})[0],409);call.assert_not_called()
        finally: TestHandler.ai_lock.release()
    def test_provider_keys_are_independent(self):
        for p,key in [('openai','sk-test-openai'),('claude','sk-ant-test-claude'),('gemini','gemini-test-value')]:
            self.assertEqual(self.request('/api/ai/config','POST',{'provider':p,'key':key})[0],200)
        with patch('server.generate_content',return_value={'draft':{}}) as call:
            for p,key in [('openai','sk-test-openai'),('claude','sk-ant-test-claude'),('gemini','gemini-test-value')]:
                self.assertEqual(self.request('/api/ai/content','POST',{'provider':p,'consent':True})[0],200)
                self.assertEqual(call.call_args.args[1],key)
        self.request('/api/ai/config','POST',{'provider':'claude','key':''})
        value=json.loads(self.request('/api/ai/config')[1])['providers']
        self.assertFalse(value['claude']['configured']);self.assertTrue(value['gemini']['configured'])
        for p in ['openai','gemini']:self.request('/api/ai/config','POST',{'provider':p,'key':''})
    def test_transcribe_route_requires_consent_and_uses_only_openai(self):
        def send(consent,extra=None):
            conn=http.client.HTTPConnection('127.0.0.1',self.port,timeout=3)
            headers={'Origin':f'http://127.0.0.1:{self.port}','X-Peca-Request':'1','X-Peca-Consent':consent,'Content-Type':'application/octet-stream','X-Peca-Filename':'fixture.wav'};headers.update(extra or {})
            conn.request('POST','/api/ai/transcribe',body=b'fixture',headers=headers);r=conn.getresponse();status=r.status;r.read();conn.close();return status
        with patch('server.transcribe_media',return_value={'cues':[{'start':0,'end':1,'text':'Teste'}]}) as call:
            self.assertEqual(send('0'),400);call.assert_not_called()
            TestHandler.ai_keys={'openai':'openai-fixture','claude':'claude-fixture','gemini':'gemini-fixture'}
            self.assertEqual(send('1'),200);self.assertEqual(call.call_args.args[2],'openai-fixture')
            call.reset_mock();self.assertEqual(send('1',{'Content-Length':'25000001'}),413);call.assert_not_called()
        TestHandler.ai_keys={'openai':'','claude':'','gemini':''}

if __name__=='__main__':unittest.main()
