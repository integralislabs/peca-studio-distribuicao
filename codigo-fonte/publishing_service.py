"""Official API publication; persistent queue is disabled until explicitly enabled."""
import datetime as dt, hashlib, json, re, threading, urllib.request, urllib.error, urllib.parse, uuid
from pathlib import Path
from image_quality import assert_image_quality

class OfficialAdapter:
 def request(self,method,url,token,body=None,headers=None):
  h={'Authorization':'Bearer '+token,**(headers or {})}
  if isinstance(body,dict):body=json.dumps(body).encode();h['Content-Type']='application/json'
  req=urllib.request.Request(url,data=body,headers=h,method=method)
  class NoRedirect(urllib.request.HTTPRedirectHandler):
   def redirect_request(self,req,fp,code,msg,headers,newurl):raise ValueError('Redirecionamento externo recusado.')
  with urllib.request.build_opener(NoRedirect).open(req,timeout=90) as r:
   raw=r.read();return {'status':r.status,'headers':dict(r.headers),'data':json.loads(raw) if raw else {}}
 def validate(self,account,token):
  p=account['provider'];target=account['target']
  if p=='youtube':return self.request('GET','https://www.googleapis.com/youtube/v3/channels?part=snippet&mine=true',token)['data']
  if p=='instagram':return self.request('GET','https://graph.facebook.com/'+account['apiVersion']+'/'+target+'?fields=id,username',token)['data']
  return self.request('GET','https://api.linkedin.com/v2/userinfo',token)['data']
 def publish(self,a,token,item,media):
  p=a['provider'];payload=item['payload']
  if p=='youtube':
   identity=self.validate(a,token)
   if not any(x.get('id')==a['target'] for x in identity.get('items',[])):raise ValueError('Canal do token difere do destino confirmado.')
   file=media.file_path(payload['assetId']);size=file.stat().st_size
   result=self.request('POST','https://www.googleapis.com/upload/youtube/v3/videos?uploadType=resumable&part=snippet,status',token,{'snippet':{'title':payload['title'],'description':payload.get('text','')},'status':{'privacyStatus':payload.get('privacy','private')}},{'X-Upload-Content-Type':'video/mp4','X-Upload-Content-Length':str(size)})
   location=result['headers'].get('Location') or result['headers'].get('location')
   parsed=urllib.parse.urlparse(location or '')
   if parsed.scheme!='https' or parsed.hostname not in ('www.googleapis.com','youtube.googleapis.com'):raise ValueError('URL de sessão de upload inválida.')
   # Single resumable session PUT; on interruption the queue becomes unknown, never blindly retries.
   with file.open('rb') as source:
    return self.request('PUT',location,token,source.read(),{'Content-Type':'video/mp4','Content-Length':str(size),'Content-Range':f'bytes 0-{size-1}/{size}'})['data']
  if p=='instagram':
   base='https://graph.facebook.com/'+a['apiVersion']+'/'+a['target']
   container=self.request('POST',base+'/media',token,{'image_url':payload['mediaUrl'],'caption':payload.get('text','')})['data']
   return self.request('POST',base+'/media_publish',token,{'creation_id':container['id']})['data']
  return self.request('POST','https://api.linkedin.com/rest/posts',token,{'author':a['target'],'commentary':payload.get('text',''),'visibility':'PUBLIC','distribution':{'feedDistribution':'MAIN_FEED','targetEntities':[],'thirdPartyDistributionChannels':[]},'lifecycleState':'PUBLISHED','isReshareDisabledByAuthor':False},{'LinkedIn-Version':a['apiVersion'],'X-Restli-Protocol-Version':'2.0.0'})

class PublicationService:
 def __init__(self,root,secretStore,adapter=None):
  self.root=Path(root).resolve();self.root.mkdir(parents=True,exist_ok=True);self.path=self.root/'publishing.json';self.secrets=secretStore;self.adapter=adapter or OfficialAdapter();self.lock=threading.RLock();self.event=threading.Event();self.thread=None;self.media=None
  self.state=json.loads(self.path.read_text('utf-8')) if self.path.exists() else {'accounts':[],'queue':[],'enabled':False}
  # A fresh process requires renewed operator enable; interrupted external operations are unknown.
  self.state['enabled']=False
  for j in self.state['queue']:
   if j['status']=='sending':j['status']='unknown';j['error']='Processo interrompido; confira a rede antes de qualquer nova publicação.'
  self._save()
 def _save(self):
  with self.lock:
   p=self.path.with_suffix('.tmp');p.write_text(json.dumps(self.state,ensure_ascii=False),'utf-8');p.replace(self.path)
 def _account(self,id):
  a=next((a for a in self.state['accounts'] if a['id']==id),None)
  if not a:raise ValueError('Conta não encontrada.')
  return a
 def _job(self,id):
  j=next((j for j in self.state['queue'] if j['id']==id),None)
  if not j:raise ValueError('Agendamento não encontrado.')
  return j
 def start(self):
  if self.thread and self.thread.is_alive():return
  self.event.clear()
  def loop():
   while not self.event.wait(2):self.run_due()
  self.thread=threading.Thread(target=loop,daemon=True);self.thread.start()
 def stop(self):
  self.event.set()
  with self.lock:self.state['enabled']=False;self._save()
 def run_due(self):
  while True:
   with self.lock:
    if not self.state['enabled']:return
    now=dt.datetime.now(dt.timezone.utc)
    j=next((j for j in self.state['queue'] if j['status']=='scheduled' and j['approved'] and dt.datetime.fromisoformat(j['when'])<=now),None)
    if not j:return
    a=self._account(j['accountId']).copy();token=self.secrets.get('publishing.'+a['id'])
    if not token:
     j.update(status='blocked',error='Token ausente.');self._save();continue
    try:
     if j.get('piece') is not None:assert_image_quality(j['piece'])
    except ValueError as e:
     j.update(status='blocked',error='QA: '+str(e));self._save();continue
    j['status']='sending';self._save()
   # External calls never hold the state lock: status/cancellation of other items remain responsive.
   try:
    guard=getattr(self,'access_guard',None)
    if guard:guard()
    result=self.adapter.publish(a,token,j,self.media);outcome={'status':'published','result':result}
   except PermissionError:outcome={'status':'blocked','error':'Acesso Integralis não confirmado. Entre novamente e revise o envio.'}
   except urllib.error.HTTPError as e:
    outcome={'status':'failed' if 400<=e.code<500 else 'unknown','error':'API retornou HTTP '+str(e.code)+'. Confira o destino antes de criar novo envio.'}
   except Exception:outcome={'status':'unknown','error':'Resultado externo desconhecido. Confira o destino; não há repetição automática.'}
   with self.lock:j.update(outcome);self._save()
 def dispatch(self,action,data=None):
  d=data or {}
  with self.lock:
   if action in ('accounts','status','calendar'):return json.loads(json.dumps({**self.state,'accounts':[{**a,'tokenConfigured':bool(self.secrets.get('publishing.'+a['id']))} for a in self.state['accounts']]}))
   if action=='connect':
    p=d.get('provider');target=str(d.get('target','')).strip();token=str(d.get('token','')).strip();version=str(d.get('apiVersion',''))
    if p not in ('youtube','instagram','linkedin') or not target or not token:raise ValueError('Informe plataforma, destino e token autorizado.')
    if len(token)>16384 or '\n' in token or '\r' in token:raise ValueError('Token inválido.')
    if p=='instagram' and (not target.isdigit() or not re.fullmatch(r'v\d+\.\d+',version)):raise ValueError('Instagram requer ID profissional numérico e versão Graph do seu app (vNN.N).')
    if p=='linkedin' and (not re.fullmatch(r'urn:li:(person|organization):[A-Za-z0-9_-]+',target) or not re.fullmatch(r'\d{6}',version)):raise ValueError('LinkedIn requer URN de autor e versão mensal habilitada (AAAAMM).')
    a={'id':uuid.uuid4().hex,'provider':p,'target':target,'label':str(d.get('label') or target)[:180],'apiVersion':version};self.secrets.set('publishing.'+a['id'],token);self.state['accounts'].append(a);self._save();return a
   if action=='disconnect':
    a=self._account(d.get('accountId'));self.secrets.delete('publishing.'+a['id']);self.state['accounts'].remove(a)
    for j in self.state['queue']:
     if j['accountId']==a['id'] and j['status'] in ('draft','scheduled','blocked'):j['status']='cancelled'
    self._save();return {'disconnected':True}
   if action=='validate':
    a=self._account(d.get('accountId'));token=self.secrets.get('publishing.'+a['id'])
    if not token:return {'validated':False,'missing':['accessToken']}
    try:
     r=self.adapter.validate(a,token)
     if a['provider']=='youtube' and not any(x.get('id')==a['target'] for x in r.get('items',[])):raise ValueError('O canal do token difere do destino configurado.')
     return {'validated':True,'identity':r,'publicationTested':False}
    except Exception:raise ValueError('Validação não concluída: token, escopos, destino ou acesso do app indisponível.') from None
   if action=='schedule':
    a=self._account(d.get('accountId'));payload=d.get('payload',{})
    if not isinstance(payload,dict) or set(payload)-{'title','text','assetId','mediaUrl','privacy'}:raise ValueError('Campos de conteúdo não aceitos.')
    when=dt.datetime.fromisoformat(str(d.get('when','')))
    if not when.tzinfo:raise ValueError('Horário deve incluir fuso/offset.')
    if a['provider']=='youtube':
     if not payload.get('title') or not payload.get('assetId') or payload.get('privacy','private') not in ('private','unlisted','public'):raise ValueError('YouTube requer título, MP4 e privacidade válida.')
     if self.media:
      path=self.media.file_path(payload['assetId'])
      if path.suffix!='.mp4':raise ValueError('Selecione um render MP4.')
    if a['provider']=='instagram':
     u=urllib.parse.urlparse(str(payload.get('mediaUrl','')))
     if u.scheme!='https' or not u.hostname or u.username or u.password:raise ValueError('Instagram requer URL HTTPS pública de imagem hospedada pelo usuário.')
    if a['provider']=='linkedin' and not payload.get('text'):raise ValueError('LinkedIn requer texto.')
    if len(json.dumps(payload))>30000:raise ValueError('Conteúdo excede limite local.')
    key=hashlib.sha256(json.dumps([a['id'],payload,when.isoformat()],sort_keys=True).encode()).hexdigest()
    previous=next((j for j in self.state['queue'] if j['key']==key),None)
    if previous:return previous.copy()
    j={'id':uuid.uuid4().hex,'key':key,'accountId':a['id'],'target':a['target'],'provider':a['provider'],'payload':payload,'when':when.isoformat(),'approved':False,'status':'draft'};
    if d.get('piece') is not None:j['piece']=json.loads(json.dumps(d['piece']))
    self.state['queue'].append(j);self._save();return j.copy()
   if action=='confirm':
    j=self._job(d.get('id'))
    if d.get('approved') is not True or d.get('target')!=j['target']:raise ValueError('Confira o conteúdo e confirme o destino exato.')
    if j['status']!='draft':raise ValueError('Somente rascunho pode ser confirmado.')

    if j.get('piece') is not None:
     try:assert_image_quality(j['piece'])
     except ValueError as e:raise ValueError('QA: '+str(e)) from e
    j.update(approved=True,status='scheduled');self._save();return j.copy()
   if action=='cancel':
    j=self._job(d.get('id'))
    if j['status'] not in ('draft','scheduled','blocked'):raise ValueError('Envio iniciado ou concluído não pode ser cancelado localmente.')
    j['status']='cancelled';self._save();return j.copy()
   if action=='enable':
    self.state['enabled']=d.get('enabled') is True;self._save()
    if self.state['enabled']:self.start()
    return {'enabled':self.state['enabled']}
   raise ValueError('Ação de publicação desconhecida.')
