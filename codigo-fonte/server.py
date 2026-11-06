"""Local studio server; paid providers are called only by explicit requests."""
from http.server import ThreadingHTTPServer, SimpleHTTPRequestHandler
from pathlib import Path
import argparse
import json
import os
import threading
from urllib.parse import urlsplit, unquote
from ai_service import AIError, PROVIDERS, provider_id, public_config, generate_content, generate_image, transcribe_media
from local_api import get_api,handle_local

ROOT = Path(__file__).resolve().parent

PUBLIC_FILES=['integralis-theme.css','html-document-ui.js','quality-policy.js','integralis-ui.js','youtube-source.js','geometry.js','art-ui.js','media-ui.js','publishing-ui.js','desktop-ui.js','trash.js','trash-ui.js','INICIO-1.6.md', 'BARRA-1.6.md', 'BARRA.md', 'MCP-LOCAL.md', 'MEMORIA.md', 'QA-R002.md', 'QA-R003.md', 'QA-R004.md', 'QA-R005.md', 'QA-R006.md', 'QA-R007.md', 'README.md', 'VERIFICACAO.md', 'ai-ui.js', 'ai.js', 'app.js', 'brand-ui.js', 'brand.js', 'directory.js', 'font-ui.js', 'fonts.js', 'image-conversion-ui.js', 'image-review.js', 'index.html', 'library-ui.js', 'library.js', 'model.js', 'package-ui.js', 'packages.js', 'print-export.js', 'reference.js', 'render.js', 'resize.js', 'rich-html.js', 'seed.js', 'sources-ui.js', 'sources.js', 'storage.js', 'studio-contracts.js', 'studio-style.js', 'style-ui.js', 'style.css', 'templates-ui.js', 'templates.js', 'visual-qa.js', 'workspace-ui.js']

class Handler(SimpleHTTPRequestHandler):
    ai_keys = {p:os.environ.get(v['env'],'').strip() for p,v in PROVIDERS.items()}
    ai_lock = threading.Lock()

    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(ROOT), **kwargs)

    def log_request(self,code='-',size='-'):
        if urlsplit(self.path).path=='/api/local/integralis/callback':
            self.log_message('OAuth callback %s',str(code))
        else:super().log_request(code,size)

    def do_GET(self):
        if urlsplit(self.path).path=='/api/local/integralis/callback':
            if not self.local_host():self.send_error(403);return
            self.prepare_local()
            from urllib.parse import parse_qs
            try:
                params=parse_qs(urlsplit(self.path).query,keep_blank_values=True)
                if any(len(v)!=1 for v in params.values()):raise ValueError('Retorno de entrada inválido.')
                get_api(self.server,ROOT).integralis.callback({k:v[0] for k,v in params.items()})
                message='Entrada concluída. Volte ao Peça Studio.';status=200
            except Exception:message='Não foi possível concluir a entrada. Volte ao Peça Studio e tente novamente.';status=400
            body=('<!doctype html><meta charset="utf-8"><title>Peça Studio</title><p>'+message+'</p>').encode()
            self.send_response(status);self.send_header('Content-Type','text/html; charset=utf-8');self.send_header('Content-Length',str(len(body)));self.send_header('Cache-Control','no-store');self.send_header('Referrer-Policy','no-referrer');self.send_header('Content-Security-Policy',"default-src 'none'");self.end_headers();self.wfile.write(body);return
        if self.path.startswith('/api/local/'):
            self.prepare_local();handle_local(self,ROOT);return
        if not self.local_host():
            self.send_error(403); return
        parts=unquote(urlsplit(self.path).path).replace('\\','/').split('/')
        if any(p.startswith('.') or p=='__pycache__' or p.endswith(('.py','.pyc','.cmd')) for p in parts if p):
            self.send_error(404); return
        if self.path == '/api/ai/config':
            self.send_json(public_config(type(self).ai_keys)); return
        if self.path == '/api/health':
            body = json.dumps({'ok': True, 'app': 'peca-studio', 'version': '1.9.1'}).encode()
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Content-Length', str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        else:
            super().do_GET()

    def local_host(self):
        return self.headers.get('Host') in (f'127.0.0.1:{self.server.server_port}',f'localhost:{self.server.server_port}')

    @staticmethod
    def public_static(root,candidate):
        root=Path(root).resolve();candidate=Path(candidate).resolve()
        try: relative=candidate.relative_to(root)
        except ValueError:return False
        parts=relative.parts
        if not parts:return True  # SimpleHTTPRequestHandler resolves the public index.html.
        if any(p.startswith('.') or p=='__pycache__' for p in parts):return False
        # The public surface is independent of initialized/current workspace state.
        if len(parts)==1:return parts[0] in PUBLIC_FILES
        if parts[0]=='brand':return candidate.suffix.lower() in ('.css','.svg','.woff2','.txt') and candidate.is_file()
        if parts[0] not in ('tests','docs','evidencias'):return False
        if candidate.suffix.lower() not in ('.js','.mjs','.html','.css','.md','.png','.jpg','.jpeg','.webp','.svg','.pdf'):return False
        for parent in candidate.parents:
            if parent==root:break
            if (parent/'workspace.json').exists():return False
        return True

    def send_head(self):
        parts=unquote(urlsplit(self.path).path).replace('\\','/').split('/')
        if not self.local_host(): self.send_error(403); return None
        if any(p.startswith('.') or p=='__pycache__' or p.endswith(('.py','.pyc','.cmd')) for p in parts if p):
            self.send_error(404); return None
        candidate=Path(self.translate_path(self.path)).resolve()
        if not self.public_static(ROOT,candidate):self.send_error(404);return None
        api=getattr(self.server,'studio_local_api',None)
        if parts[1:2]==['workspace-data'] or api and (candidate==api.config_dir.resolve() or api.config_dir.resolve() in candidate.parents or api.service and (candidate==api.service.root or api.service.root in candidate.parents)):
            self.send_error(404); return None
        return super().send_head()

    def prepare_local(self):
        get_api(self.server,ROOT)
        if not hasattr(self.server,'local_work_lock'): self.server.local_work_lock=threading.Lock()

    def list_directory(self,path):
        self.send_error(404); return None

    def send_json(self,data,status=200):
        body=json.dumps(data,ensure_ascii=False).encode()
        self.send_response(status)
        self.send_header('Content-Type','application/json; charset=utf-8')
        self.send_header('Content-Length',str(len(body)))
        self.end_headers(); self.wfile.write(body)

    def do_POST(self):
        if self.path.startswith('/api/local/'):
            self.prepare_local();handle_local(self,ROOT);return
        host=self.headers.get('Host')
        origin=self.headers.get('Origin')
        if not self.local_host() or origin!=f'http://{host}' or self.headers.get('X-Peca-Request')!='1':
            self.send_json({'error':'Origem local inválida.'},403); return
        self.prepare_local()
        try:get_api(self.server,ROOT).integralis.require_access()
        except PermissionError as exc:self.send_json({'error':str(exc)},403);return
        media=self.path=='/api/ai/transcribe'
        expected='application/octet-stream' if media else 'application/json'
        if self.headers.get('Content-Type','').split(';')[0]!=expected:
            self.send_json({'error':'Tipo de conteúdo inválido para esta operação.'},415); return
        if not type(self).ai_lock.acquire(blocking=False):
            self.send_json({'error':'Já existe uma solicitação em andamento. Aguarde.'},409); return
        try:
            length=int(self.headers.get('Content-Length','0'))
            limit=25_000_000 if media else 32_000
            if not 0 < length <= limit:
                self.close_connection=True
                raise AIError('Mídia limitada a 25 MB.' if media else 'Pedido acima do limite de 32 KB.',413)
            if media:
                if self.headers.get('X-Peca-Consent')!='1':raise AIError('Autorize o envio da mídia à OpenAI antes de transcrever.')
                result=transcribe_media(self.rfile.read(length),unquote(self.headers.get('X-Peca-Filename','')),type(self).ai_keys.get('openai',''))
                self.send_json(result);return
            data=json.loads(self.rfile.read(length))
            if not isinstance(data,dict): raise AIError('Pedido JSON inválido.')
            if self.path=='/api/ai/config':
                provider=provider_id(data)
                key=data.get('key')
                prefix={'openai':'sk-','claude':'sk-ant-','gemini':''}[provider]
                if not isinstance(key,str) or len(key)>500 or (key and (len(key)<8 or not key.startswith(prefix) or any(c.isspace() or ord(c)>126 or ord(c)<33 for c in key))): raise AIError('Confira o formato da chave do serviço selecionado.')
                type(self).ai_keys={**type(self).ai_keys,provider:key}
                result=public_config(type(self).ai_keys)
            elif self.path in ('/api/ai/content','/api/ai/image'):
                if data.get('consent') is not True: raise AIError('Confirme o envio e o uso cobrado da API.')
                action=generate_content if self.path.endswith('content') else generate_image
                provider=provider_id(data)
                result=action(data,type(self).ai_keys.get(provider,''))
            else: raise AIError('Rota inexistente.',404)
            self.send_json(result)
        except AIError as err: self.send_json({'error':str(err)},err.status)
        except (ValueError,UnicodeError): self.send_json({'error':'Pedido JSON inválido.'},400)
        except Exception: self.send_json({'error':'Não foi possível concluir. Nenhuma nova tentativa automática foi feita.'},500)
        finally: type(self).ai_lock.release()

    def end_headers(self):
        self.send_header('Cache-Control', 'no-cache')
        self.send_header('X-Content-Type-Options', 'nosniff')
        self.send_header('Content-Security-Policy', "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data: blob:; font-src 'self' data: blob:; connect-src 'self'; object-src 'none'; base-uri 'none'; frame-src 'self' blob:")
        super().end_headers()

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--port', type=int, default=17865)
    args = parser.parse_args()
    server = ThreadingHTTPServer(('127.0.0.1', args.port), Handler)
    print(f'Peca Studio: http://127.0.0.1:{args.port}', flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        server.server_close()
