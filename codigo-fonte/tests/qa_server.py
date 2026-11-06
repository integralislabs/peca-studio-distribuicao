"""QA origin: backup/restore and mobile tests cannot change the library on 17865."""
import sys
import argparse
from pathlib import Path
from http.server import ThreadingHTTPServer, SimpleHTTPRequestHandler

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from server import Handler

class QAHandler(Handler):
    def do_GET(self):
        if self.path.split('?')[0] == '/storage.js' and self.server.fail_save_once:
            source=(Path(__file__).resolve().parents[1]/'storage.js').read_text(encoding='utf-8')
            source=source.replace('let database,revision=0;','let database,revision=0,qaWrites=0;')
            source=source.replace('export function writeStore(data){', "export function writeStore(data){if(++qaWrites===2)return Promise.reject(new DOMException('Falha temporária de armazenamento simulada pelo QA.','QuotaExceededError'));")
            body=source.encode('utf-8')
            self.send_response(200)
            self.send_header('Content-Type','text/javascript; charset=utf-8')
            self.send_header('Content-Length',str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        else:
            super().do_GET()

    def end_headers(self):
        if self.path.split('?')[0] in ('/tests/responsive.html','/tests/integration-browser.html'):
            self.send_header('Cache-Control', 'no-cache')
            self.send_header('X-Content-Type-Options', 'nosniff')
            self.send_header('Content-Security-Policy', "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data: blob:; frame-src 'self'; object-src 'none'; base-uri 'none'")
            SimpleHTTPRequestHandler.end_headers(self)
        else:
            super().end_headers()

if __name__ == '__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--port',type=int,default=17866)
    parser.add_argument('--fail-save-once',action='store_true')
    args=parser.parse_args()
    server=ThreadingHTTPServer(('127.0.0.1',args.port),QAHandler)
    server.fail_save_once=args.fail_save_once
    print(f'QA isolado: http://127.0.0.1:{args.port}',flush=True)
    server.serve_forever()
