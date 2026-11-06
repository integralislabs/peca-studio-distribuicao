"""Same-origin local tools. Filesystem workspace is opt-in; no paid operations here."""
import base64,hmac,json,os,re,secrets,sys,threading
from pathlib import Path
from urllib.parse import urlsplit,parse_qs,unquote
from workspace_service import StudioService,ConflictError

_init=threading.Lock()
class LocalAPI:
 def __init__(self,server,app_root):
  self.server=server;self.app_root=Path(app_root);self.lock=threading.RLock();self.service=None
  self.config_dir=Path(getattr(server,'local_config_dir',None) or getattr(server,'studio_data_root',None) or os.environ.get('PECA_STUDIO_DATA_ROOT') or self.app_root/'.local');self.config_dir.mkdir(parents=True,exist_ok=True)
  from local_secrets import SecretStore
  from media_service import MediaService
  from publishing_service import PublicationService
  from update_service import UpdateService
  from integralis_auth import IntegralisAuth,installation_config
  install_config=installation_config(self.app_root)
  self.secrets=SecretStore(self.config_dir)
  self.integralis=IntegralisAuth(self.config_dir,server.server_port,config=install_config,vault=self.secrets)
  self.media=MediaService(self.config_dir/'media');self.publishing=PublicationService(self.config_dir/'publishing',self.secrets);self.publishing.media=self.media;self.updater=UpdateService(self.config_dir,'1.9.1',distribution=install_config.get('updates'))
  self.publishing.access_guard=self.integralis.require_access
  self.config_file=self.config_dir/f'workspace-{server.server_port}.json';self.token_file=self.config_dir/f'mcp-token-{server.server_port}.txt'
  if not self.token_file.exists():
   fd=os.open(self.token_file,os.O_CREAT|os.O_EXCL|os.O_WRONLY,0o600)
   with os.fdopen(fd,'w') as out:out.write(secrets.token_urlsafe(40))
  if self.config_file.exists():
   config=json.loads(self.config_file.read_text('utf-8'))
   if config.get('path'):self.service=StudioService(config['path'])
 def _configure(self,path):
  tmp=self.config_file.with_suffix('.tmp');tmp.write_text(json.dumps({'path':path},ensure_ascii=False),encoding='utf-8');os.replace(tmp,self.config_file)
 def cached_state(self):
  with self.lock:
   file=self.service.store.path
   stat=file.stat() if file.exists() else None
   stamp=(str(file),stat.st_mtime_ns,stat.st_size) if stat else (str(file),None)
   if getattr(self,'_cache_stamp',None)!=stamp:
    self._cache_state=self.service.store.read();self._cache_stamp=stamp
   return self._cache_state
 def snapshot(self):
  if not self.service:return {'active':False,'defaultPath':str(self.config_dir/'acervo')}
  return {'active':True,'path':str(self.service.root),**self.cached_state()}
 def config(self):
  from image_conversion import capabilities
  return {'active':bool(self.service),'capabilities':capabilities(),'mcpConfig':{'mcpServers':{'peca-studio':{'command':sys.executable,'args':(['--mcp'] if getattr(sys,'frozen',False) else [str(self.app_root/'mcp_server.py')])+['--url',f'http://127.0.0.1:{self.server.server_port}','--token-file',str(self.token_file)]}}}}
 def authorized(self,h,allow_token=False):
  if not h.local_host():return False
  host=h.headers.get('Host');origin=h.headers.get('Origin')
  if allow_token:
   supplied=h.headers.get('Authorization','')
   if supplied.startswith('Bearer ') and hmac.compare_digest(supplied[7:],self.token_file.read_text('utf-8').strip()):return True
  return h.headers.get('X-Peca-Request')=='1' and origin in (None,f'http://{host}') and h.headers.get('Sec-Fetch-Site') in (None,'same-origin','none')
 def dispatch(self,path,body=None):
  if path.startswith('/api/local/integralis/'):
   action=path.rsplit('/',1)[1]
   if action=='status':return self.integralis.status()
   if body is None:raise ValueError('Use POST para alterar a conta.')
   if action=='authorize':return self.integralis.require_access()
   if action not in ('login','logout','heartbeat'):raise ValueError('Ação de conta inválida.')
   return getattr(self.integralis,action)()
  readonly=body is None or path=='/api/local/workspace-status'
  if path=='/api/local/mcp' and isinstance(body,dict):readonly=body.get('name','').removeprefix('studio_') in ('projects_list','pieces_list','pieces_get','pieces_get_html','pieces_list_editables')
  if path=='/api/local/html/validate':readonly=True
  if not readonly:self.integralis.require_access()
  if path=='/api/local/config':return self.config()
  if path.startswith('/api/local/html/'):
   from html_document import prepare_document,update_document,render_document,validate_document
   action=path.rsplit('/',1)[1]
   if not isinstance(body,dict):raise ValueError('HTML requires POST JSON')
   if action=='validate':return validate_document(body.get('document'))
   if action=='prepare':return prepare_document(body.get('html'))
   if action=='update':return update_document(body.get('document'),body.get('texts'),body.get('controls'))
   if action=='render':
    payload,mime=render_document(body.get('document'),body.get('format','png'),body.get('frame',0))
    return {'base64':base64.b64encode(payload).decode(),'mime':mime}
   raise ValueError('Unknown HTML action')
  if path.startswith('/api/local/media/'):return self.media.dispatch(path.rsplit('/',1)[1],body)
  if path.startswith('/api/local/publishing/'):return self.publishing.dispatch(path.rsplit('/',1)[1],body)
  if path.startswith('/api/local/update/'):return self.updater.dispatch(path.rsplit('/',1)[1],body or {})
  if path=='/api/local/workspace-status':
   if not self.service:return {'active':False}
   return {'active':True,'path':str(self.service.root),'revision':self.cached_state()['revision']}
  if path=='/api/local/workspace':
   if body is None:return self.snapshot()
   action=body.get('action')
   with self.lock:
    if action=='inspect':
     path=Path(body.get('path','')).expanduser()
     if not path.is_absolute():raise ValueError('Informe o caminho completo da pasta.')
     service=StudioService(path);return {'path':str(service.root),**service.store.read()}
    if action=='activate':
     path=Path(body.get('path','')).expanduser()
     if not path.is_absolute() or path.resolve()==Path(path.anchor):raise ValueError('Escolha uma pasta específica para o acervo.')
     resolved=path.resolve()
     if resolved==self.app_root.resolve() or resolved==self.config_dir.resolve() or resolved in self.app_root.resolve().parents:raise ValueError('Escolha uma pasta de dados, separada da raiz do aplicativo.')
     if self.app_root.resolve() in resolved.parents and not (resolved==self.app_root.resolve()/'workspace-data' or self.app_root.resolve()/'workspace-data' in resolved.parents):raise ValueError('Dentro do aplicativo, use apenas workspace-data; escolha outra pasta fora do aplicativo.')
     service=StudioService(resolved);current=service.store.read();mode=body.get('mode')
     if mode=='migrate':
      if current['revision']!=0:raise ConflictError('A pasta já tem um acervo. Abra-o; a migração não substitui conteúdo existente.')
      service.store.write(body.get('data'),0)
     elif mode!='open':raise ValueError('Escolha migrar a biblioteca atual ou abrir o acervo da pasta.')
     self._configure(str(service.root));self.service=service;return self.snapshot()
    if action=='deactivate':self._configure(None);self.service=None;return self.snapshot()
    if action=='write':
     if not self.service:raise ConflictError('O acervo em pasta foi desconectado. Faça um backup desta aba antes de reconectar.')
     if body.get('expectedPath')!=str(self.service.root):raise ConflictError('A pasta ativa mudou em outra aba. Faça backup antes de recarregar.')
     return self.service.store.write(body.get('data'),body.get('expectedRevision'),body.get('operationId'))
    raise ValueError('Operação de acervo inválida.')
  if path=='/api/local/export/pdf':
   from print_service import export_pdf
   return export_pdf(body)
  if path=='/api/local/image/analyze':
   from image_conversion import analyze_image
   return analyze_image(body)
  if path=='/api/local/image/convert':
   from image_conversion import convert_image
   return convert_image(body)
  if not self.service:raise ConflictError('Ative o acervo em pasta no Peça Studio para usar o MCP.')
  if path=='/api/local/mcp':return self.service.dispatch(body.get('name',''),body.get('arguments',{}))
  if path=='/api/local/exports':
   state=self.cached_state();return {'revision':state['revision'],'jobs':[j for j in state['data'].get('exportJobs',[]) if j['status']=='pending']}
  match=re.fullmatch(r'/api/local/exports/([a-zA-Z0-9_-]+)',path)
  if match:return self.service.complete_export(match[1],body)
  raise ValueError('Rota local inexistente.')

def get_api(server,root):
 with _init:
  if not hasattr(server,'studio_local_api'):server.studio_local_api=LocalAPI(server,root)
 return server.studio_local_api

def handle_local(handler,root):
 api=get_api(handler.server,root);path=urlsplit(handler.path).path
 media_view=path=='/api/local/media/file' and handler.command=='GET' and handler.local_host() and handler.headers.get('Sec-Fetch-Site')=='same-origin' and urlsplit(handler.headers.get('Referer','')).netloc==handler.headers.get('Host')
 if not media_view and not api.authorized(handler,allow_token=path=='/api/local/mcp'):
  handler.send_json({'error':'Acesso local não autorizado.'},403);return
 try:
  body=None
  if path=='/api/local/media/file' and handler.command=='GET':
   import mimetypes,shutil
   asset=api.media.file_path(parse_qs(urlsplit(handler.path).query).get('id',[''])[0]);handler.send_response(200);handler.send_header('Content-Type',mimetypes.guess_type(asset.name)[0] or 'application/octet-stream');handler.send_header('Content-Length',str(asset.stat().st_size));handler.send_header('Cache-Control','no-store');handler.end_headers()
   with asset.open('rb') as source:shutil.copyfileobj(source,handler.wfile)
   return
  if path=='/api/local/media/upload' and handler.command=='POST':
   length=int(handler.headers.get('Content-Length','0'))
   if not 0<length<=250_000_000:handler.close_connection=True;handler.send_json({'error':'Arquivo limitado a 250 MB.'},413);return
   result=api.media.upload(handler.rfile.read(length),unquote(handler.headers.get('X-Peca-Filename','upload.mp4')));handler.send_json(result);return
  if handler.command=='POST':
   if handler.headers.get('Content-Type','').split(';')[0]!='application/json':handler.send_json({'error':'Use JSON nesta operação.'},415);return
   length=int(handler.headers.get('Content-Length','0'));limit=100_000_000
   if not 0<length<=limit:handler.close_connection=True;handler.send_json({'error':'Pedido limitado a 100 MB.'},413);return
   body=json.loads(handler.rfile.read(length))
   if not isinstance(body,dict):raise ValueError('Pedido JSON inválido.')
  # Expensive tools are serialized without blocking read-only status on another thread.
  if path in ('/api/local/image/analyze','/api/local/image/convert','/api/local/export/pdf'):
   if not handler.server.local_work_lock.acquire(blocking=False):handler.send_json({'error':'Uma conversão ou exportação já está em andamento.'},409);return
   try:result=api.dispatch(path,body)
   finally:handler.server.local_work_lock.release()
  else:result=api.dispatch(path,body)
  handler.send_json(result)
 except PermissionError as e:handler.send_json({'error':str(e)},403)
 except ConflictError as e:handler.send_json({'error':str(e)},409)
 except (ValueError,KeyError,TypeError,UnicodeError) as e:handler.send_json({'error':str(e) or 'Pedido local inválido.'},400)
 except Exception:handler.send_json({'error':'Não foi possível concluir a operação local. Seus dados não foram substituídos.'},500)
