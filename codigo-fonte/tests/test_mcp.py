import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

class MCPTests(unittest.TestCase):
    def test_stdio_local_protocol(self):
        with tempfile.TemporaryDirectory() as d:
            requests=[{'jsonrpc':'2.0','id':1,'method':'initialize','params':{}},{'jsonrpc':'2.0','method':'notifications/initialized'},{'jsonrpc':'2.0','id':2,'method':'tools/list'},{'jsonrpc':'2.0','id':3,'method':'tools/call','params':{'name':'projects_create','arguments':{'name':'Fixture','expectedRevision':0}}}]
            p=subprocess.run([sys.executable,'mcp_server.py','--workspace',d],input=''.join(json.dumps(r)+'\n' for r in requests),text=True,capture_output=True,timeout=10)
            self.assertEqual(p.returncode,0,p.stderr)
            replies=[json.loads(x) for x in p.stdout.splitlines()]
            self.assertEqual(len(replies),3)
            self.assertEqual(replies[0]['result']['protocolVersion'],'2024-11-05')
            self.assertIn('pieces_resize',[x['name'] for x in replies[1]['result']['tools']])
            self.assertFalse(replies[2]['result'].get('isError',False))
            self.assertTrue((Path(d)/'workspace.json').exists())


class BridgeTests(unittest.TestCase):
    def test_bridge_loopback_token(self):
        from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
        import threading
        from mcp_server import Bridge
        class Handler(BaseHTTPRequestHandler):
            def do_POST(self):
                self.server.received=(self.path,self.headers.get('Authorization'),json.loads(self.rfile.read(int(self.headers['Content-Length']))))
                self.send_response(200); self.end_headers(); self.wfile.write(b'{"revision":0,"result":[]}')
            def log_message(self,*args): pass
        with tempfile.TemporaryDirectory() as d:
            token=Path(d)/'token'; token.write_text('fixture-token')
            server=ThreadingHTTPServer(('127.0.0.1',0),Handler)
            thread=threading.Thread(target=server.serve_forever,daemon=True); thread.start()
            try:
                b=Bridge('http://127.0.0.1:'+str(server.server_port),token)
                self.assertEqual(b.dispatch('projects_list',{})['revision'],0)
                self.assertEqual(server.received,('/api/local/mcp','Bearer fixture-token',{'name':'projects_list','arguments':{}}))
                with self.assertRaises(ValueError): Bridge('https://example.com',token)
            finally: server.shutdown(); server.server_close(); thread.join()



class MCPCompositionTests(unittest.TestCase):
    def test_composition_schemas_alias_and_stdio_import(self):
        from workspace_service import StudioService
        from mcp_server import tools_list
        with tempfile.TemporaryDirectory() as d:
            service=StudioService(d)
            project=service.dispatch('projects_create',{'name':'Fixture','expectedRevision':0})['result']
            piece=service.dispatch('pieces_create',{'projectId':project['id'],'expectedRevision':1})['result']
            layer=piece['slides'][0]['layers'][0]
            piece['slides'][0]['layers']=[{**layer,'id':'text-'+str(i),'text':str(i)} for i in range(3)]
            tools={t['name']:t['inputSchema'] for t in tools_list()}
            self.assertIn('piece',tools['pieces_import']['required'])
            self.assertIn('pieceId',tools['pieces_replace']['required'])
            request={'jsonrpc':'2.0','id':1,'method':'tools/call','params':{'name':'studio_pieces_import','arguments':{'piece':piece,'projectId':project['id'],'operationId':'import-stdio','expectedRevision':2}}}
            completed=subprocess.run([sys.executable,'mcp_server.py','--workspace',d],input=json.dumps(request)+'\n',text=True,capture_output=True,timeout=10)
            self.assertEqual(completed.returncode,0,completed.stderr)
            response=json.loads(completed.stdout)['result']
            self.assertFalse(response['isError'],response)
            result=json.loads(response['content'][0]['text'])['result']
            self.assertEqual(len(result['slides'][0]['layers']),3)
            self.assertNotEqual(result['id'],piece['id'])

if __name__=='__main__': unittest.main()
