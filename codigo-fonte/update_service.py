"""Explicit private GitHub Release updates; assets authenticated by gh, verified before execution."""
import hashlib,json,os,re,subprocess,shutil,sys,ntpath,base64
from pathlib import Path
from urllib.parse import urlsplit,urljoin
from urllib.request import Request,build_opener,HTTPRedirectHandler
REPOSITORY='PauloCambraia/peca-studio-codigo'

def own_mcp_processes(rows,executable,current_pid):
 expected=ntpath.normcase(ntpath.abspath(str(executable)))
 return [int(row['ProcessId']) for row in rows if type(row.get('ProcessId')) is int and row['ProcessId']!=current_pid and isinstance(row.get('ExecutablePath'),str) and ntpath.normcase(ntpath.abspath(row['ExecutablePath']))==expected and re.search(r'(?i)(?:^|\s)--mcp(?:\s|$)',row.get('CommandLine') or '')]

def close_update_blockers():
 """Close only background MCP hosts running this exact frozen installation."""
 if os.name!='nt' or not getattr(sys,'frozen',False):return []
 executable=str(Path(sys.executable).resolve())
 if Path(executable).name.lower()!='pecastudio.exe':raise ValueError('Executável de atualização não reconhecido.')
 flags=getattr(subprocess,'CREATE_NO_WINDOW',0)
 def run(script,process_id=''):
  environment={**os.environ,'PECA_UPDATE_EXECUTABLE':executable,'PECA_UPDATE_PROCESS_ID':str(process_id)}
  encoded=base64.b64encode(script.encode('utf-16le')).decode()
  return subprocess.run(['powershell.exe','-NoProfile','-NonInteractive','-EncodedCommand',encoded],capture_output=True,timeout=15,creationflags=flags,env=environment)
 script="Get-CimInstance Win32_Process | Where-Object { $_.ExecutablePath -eq $env:PECA_UPDATE_EXECUTABLE } | Select-Object ProcessId,ExecutablePath,CommandLine | ConvertTo-Json -Compress"
 result=run(script)
 if result.returncode:raise ValueError('Não foi possível conferir processos MCP antes da atualização.')
 rows=json.loads(result.stdout.decode('utf-8-sig').strip() or '[]');rows=[rows] if isinstance(rows,dict) else rows
 pids=own_mcp_processes(rows,executable,os.getpid())
 stop=r"$ErrorActionPreference='Stop'; $processIdentifier=[int]$env:PECA_UPDATE_PROCESS_ID; $p=Get-CimInstance Win32_Process -Filter ('ProcessId='+$processIdentifier); if($p -and $p.ExecutablePath -eq $env:PECA_UPDATE_EXECUTABLE -and $p.CommandLine -match '(?i)(^|\s)--mcp(\s|$)'){ Stop-Process -Id $processIdentifier -Force; Start-Sleep -Milliseconds 150; $remaining=Get-CimInstance Win32_Process -Filter ('ProcessId='+$processIdentifier); if($remaining -and $remaining.ExecutablePath -eq $env:PECA_UPDATE_EXECUTABLE){throw 'MCP remains open'} }; exit 0"
 for pid in pids:
  result=run(stop,pid)
  if result.returncode:raise ValueError('Feche o MCP do Peça Studio antes de atualizar; nenhum outro aplicativo foi encerrado.')
 return pids
def verify_installer(path,expected):
 if not re.fullmatch('[a-fA-F0-9]{64}',str(expected)):raise ValueError('Manifesto SHA256 inválido.')
 with Path(path).open('rb') as file:digest=hashlib.file_digest(file,'sha256').hexdigest()
 if digest.lower()!=expected.lower():raise ValueError('Integridade do instalador inválida; instalação bloqueada.')
 return digest
class UpdateService:
 def __init__(self,data_root,app_version,distribution=None):
  self.distribution=distribution or {}
  if self.distribution.get('manifest_url'):self._channel_url(self.distribution['manifest_url'])
  self.root=Path(data_root)/'updates';self.root.mkdir(parents=True,exist_ok=True);self.version=app_version;self.state_file=self.root/'state.json'
 def _channel_url(self,url):
  u=urlsplit(url);base=urlsplit(self.distribution.get('manifest_url',''))
  release_base=self.distribution.get('download_base_url','');allowed=u.netloc==base.netloc
  if release_base:
   release=urlsplit(release_base)
   if release.scheme!='https' or release.hostname!='github.com' or release.query or release.fragment or release.username or release.password or not re.fullmatch(r'/[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+/releases/download/',release.path):raise ValueError('Canal GitHub de distribuição inválido.')
   allowed=allowed or u.netloc=='github.com' and url.startswith(release_base)
  if u.scheme!='https' or not u.hostname or u.username or u.password or u.fragment or u.query or not allowed:raise ValueError('O canal de atualização precisa usar as origens HTTPS configuradas.')
  return url
 def _allowed_asset_redirect(self,source,target):
  s=urlsplit(source);t=urlsplit(target);base=self.distribution.get('download_base_url','')
  return bool(base and source.startswith(base) and s.hostname=='github.com' and t.scheme=='https' and t.hostname=='release-assets.githubusercontent.com' and not t.username and not t.password and not t.fragment)
 def _https(self,url,limit):
  service=self
  class NoRedirect(HTTPRedirectHandler):
   def redirect_request(self,request,fp,code,message,headers,newurl):
    if service._allowed_asset_redirect(request.full_url,newurl):return Request(newurl,headers={'User-Agent':'PecaStudio-Updater/1'})
    raise ValueError('Redirecionamento externo não autorizado no canal de atualização.')
  with build_opener(NoRedirect).open(Request(self._channel_url(url),headers={'User-Agent':'PecaStudio-Updater/1'}),timeout=60) as response:
   parts=[];total=0
   while True:
    chunk=response.read(1024*1024)
    if not chunk:break
    total+=len(chunk)
    if total>limit:raise ValueError('Atualização excede o tamanho permitido.')
    parts.append(chunk)
   return b''.join(parts)
 def _read(self):
  return json.loads(self.state_file.read_text('utf-8')) if self.state_file.exists() else {}
 def _write(self,state):
  tmp=self.state_file.with_suffix('.tmp');tmp.write_text(json.dumps(state),encoding='utf-8');os.replace(tmp,self.state_file)
 def _gh(self,*args,binary=False):
  gh=shutil.which('gh')
  if not gh:raise ValueError('Atualizações privadas precisam do GitHub CLI autenticado neste computador (gh auth login).')
  result=subprocess.run([gh,*args],capture_output=True,timeout=180,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
  if result.returncode:raise ValueError('Não foi possível acessar a release privada. Verifique gh auth status, acesso ao repositório e se uma release foi publicada.')
  return result.stdout if binary else json.loads(result.stdout)
 def status(self):
  state=self._read();return {'version':self.version,'repository':None if self.distribution else REPOSITORY,'desktop':bool(getattr(__import__('sys'),'frozen',False)),'authentication':'Canal HTTPS do produto' if self.distribution else 'GitHub CLI autenticado','release':state.get('release'),'downloaded':bool(state.get('downloaded')),'automatic':False}
 def dispatch(self,action,data=None):
  data=data or {}
  if action=='status':return self.status()
  if action=='check':
   if self.distribution.get('manifest_url'):
    manifest=json.loads(self._https(self.distribution['manifest_url'],1024*1024));version=manifest.get('version','');name=manifest.get('installer','');sha=manifest.get('sha256','')
    if not re.fullmatch(r'\d+\.\d+\.\d+',version) or name!='PecaStudio-Setup-'+version+'.exe' or not re.fullmatch('[a-fA-F0-9]{64}',sha):raise ValueError('Manifesto do produto inválido.')
    url=self._channel_url(manifest.get('installer_url') or urljoin(self.distribution['manifest_url'],name))
    self._write({'release':{'version':version,'available':tuple(map(int,version.split('.')))>tuple(map(int,self.version.split('.')))},'installer':name,'sha256':sha,'assetUrl':url})
    return self.status()
   releases=self._gh('api',f'repos/{REPOSITORY}/releases?per_page=20')
   release=next((r for r in releases if not r.get('draft') and not r.get('prerelease')),None)
   if release is None:return {**self.status(),'message':'Nenhuma release estável publicada neste repositório. Sua instalação permanece disponível.'}
   assets={a['name']:a['id'] for a in release.get('assets',[])}
   if 'release-manifest.json' not in assets:raise ValueError('Release sem manifesto de integridade.')
   manifest=json.loads(self._gh('api',f'repos/{REPOSITORY}/releases/assets/{assets["release-manifest.json"]}','-H','Accept: application/octet-stream',binary=True))
   name=manifest.get('installer','');sha=manifest.get('sha256','');version=manifest.get('version','')
   if not re.fullmatch(r'PecaStudio-Setup-[0-9.]+\.exe',name) or name not in assets or not re.fullmatch('[a-fA-F0-9]{64}',sha) or not re.fullmatch(r'\d+\.\d+\.\d+',version):raise ValueError('Manifesto de atualização inválido.')
   state={'release':{'version':version,'tag':release['tag_name'],'available':tuple(map(int,version.split('.')))>tuple(map(int,self.version.split('.')))},'installer':name,'sha256':sha,'asset':assets[name]};self._write(state);return self.status()
  state=self._read()
  if action=='download':
   if not state.get('release',{}).get('available'):raise ValueError('Verifique uma nova versão primeiro.')
   payload=self._https(state['assetUrl'],800_000_000) if self.distribution.get('manifest_url') else self._gh('api',f'repos/{REPOSITORY}/releases/assets/{int(state["asset"])}','-H','Accept: application/octet-stream',binary=True)
   path=self.root/state['installer'];tmp=path.with_suffix('.part');tmp.write_bytes(payload)
   try:verify_installer(tmp,state['sha256']);os.replace(tmp,path)
   except Exception:tmp.unlink(missing_ok=True);raise
   state['downloaded']=True;self._write(state);return self.status()
  if action=='install':
   if data.get('confirm') is not True:raise ValueError('Confirme aplicar a atualização.')
   if not state.get('downloaded'):raise ValueError('Baixe uma atualização verificada primeiro.')
   path=self.root/state['installer'];verify_installer(path,state['sha256'])
   closed=close_update_blockers()
   subprocess.Popen([str(path),'/CLOSEAPPLICATIONS','/RESTARTAPPLICATIONS'],cwd=str(self.root));return {'started':True,'closedMcpHosts':len(closed),'message':'Instalador iniciado após conferir os processos MCP desta instalação. Seu acervo será preservado; reabra a conexão MCP depois da atualização.'}
  raise ValueError('Ação de atualização inválida.')
