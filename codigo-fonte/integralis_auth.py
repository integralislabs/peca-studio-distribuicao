"""Native public OIDC client. Configuration is installation data, never browser input.

No credentials are returned by this module. Tokens are account-local DPAPI data.
Commercial access always requires a live server entitlement and current use-session.
"""
import base64, hashlib, hmac, json, math, secrets, threading, time
from datetime import datetime
from pathlib import Path
from urllib.parse import urlencode, urlsplit
from urllib.request import Request, build_opener, HTTPRedirectHandler
from urllib.error import HTTPError

def installation_config(root):
 """A compiled commercial marker keeps a missing configuration fail-closed."""
 import importlib
 try:commercial=importlib.import_module('peca_commercial_build').COMMERCIAL is True
 except ImportError:commercial=False
 file=Path(root)/'integralis-config.json'
 config=json.loads(file.read_text('utf-8')) if file.exists() else {'mode':'commercial' if commercial else 'development'}
 if commercial and config.get('mode')!='commercial':raise ValueError('Pacote comercial não pode usar modo de desenvolvimento.')
 return config

class _NoRedirect(HTTPRedirectHandler):
 def redirect_request(self,*args,**kwargs):raise ValueError('Redirecionamento remoto recusado.')

class OAuthError(ValueError):
 def __init__(self,code,status):
  self.code=code;self.status=status
  super().__init__('A Integralis recusou a operação (%s).'%status)

def _request(method,url,headers=None,data=None,form=False):
 raw=None if data is None else (urlencode(data).encode() if form else json.dumps(data).encode())
 headers={**(headers or {}),'Accept':'application/json'}
 if raw is not None:headers['Content-Type']='application/x-www-form-urlencoded' if form else 'application/json'
 try:
  with build_opener(_NoRedirect).open(Request(url,raw,headers,method=method),timeout=15) as response:
   result=response.read(1024*1024+1)
   if len(result)>1024*1024:raise ValueError('Resposta remota excessiva.')
   return json.loads(result) if result else {}
 except HTTPError as exc:
  # Never log OAuth response bodies or a URL containing authorization codes.
  try:code=json.loads(exc.read(65536)).get('error','')
  except Exception:code=''
  raise OAuthError(code if isinstance(code,str) else '',exc.code) from None

def _timestamp(value):
 return datetime.fromisoformat(value.replace('Z','+00:00')).timestamp()

class IntegralisAuth:
 def __init__(self,root,port,*,config=None,vault=None,transport=None):
  self.root=Path(root);self.lock=threading.RLock()
  if config is None:
   file=self.root/'integralis-config.json';config=json.loads(file.read_text('utf-8')) if file.exists() else {}
  self.config=dict(config);self.mode=self.config.get('mode','commercial')
  if self.mode not in ('commercial','development'):raise ValueError('Modo Integralis inválido.')
  self.issuer=self.config.get('issuer','').rstrip('/');self.client=self.config.get('client_id','');self.product=self.config.get('product','')
  if self.issuer:
   u=urlsplit(self.issuer)
   if u.scheme!='https' or not u.hostname or u.username or u.password or u.query or u.fragment:raise ValueError('Emissor OIDC HTTPS inválido.')
  self.redirect='http://127.0.0.1:%d/api/local/integralis/callback'%port
  from local_secrets import SecretStore
  self.vault=vault or SecretStore(root);self.transport=transport or _request
  self.pending=None;self.tokens=None;self.session=None;self.token_deadline=0;self.lease_deadline=0;self.next_heartbeat=0;self.allowed=False;self.reason='Entre com sua conta Integralis.';self.discovery=None
  self.subject=None;self.login_nonce=None;self.auth_time=None;self.last_login_failure=None
  self._restore()
 def _binding(self):
  return {'issuer':self.issuer,'client_id':self.client,'product':self.product,'installation':str(self.root.resolve()).casefold()}
 def _persist(self):
  self.vault.set('integralis.tokens',json.dumps({'version':2,'binding':self._binding(),'tokens':self.tokens,'subject':self.subject,'nonce':self.login_nonce,'auth_time':self.auth_time,'token_deadline':self.token_deadline,'session':self.session,'lease_deadline':self.lease_deadline}))
  self.vault.delete('integralis.use-session')
 def _restore(self):
  try:
   raw=self.vault.get('integralis.tokens')
   if not raw:return
   saved=json.loads(raw)
   if self.mode!='commercial' or saved.get('version')!=2 or saved.get('binding')!=self._binding():raise ValueError('Cofre incompatível.')
   tokens=saved['tokens'];session=saved['session']
   if not isinstance(tokens,dict) or tokens.get('token_type','').lower()!='bearer' or not isinstance(tokens.get('access_token'),str) or not tokens['access_token']:raise ValueError('Token inválido.')
   if not isinstance(saved['subject'],str) or not saved['subject'] or not isinstance(saved['nonce'],str) or not saved['nonce']:raise ValueError('Identidade inválida.')
   if not isinstance(session,dict) or not all(isinstance(session.get(k),str) and session[k] for k in ('id','token')) or session.get('product')!=self.product or session.get('state')!='current':raise ValueError('Sessão inválida.')
   token_deadline=float(saved['token_deadline']);lease_deadline=float(saved['lease_deadline'])
   if not math.isfinite(token_deadline) or not math.isfinite(lease_deadline) or token_deadline<=0 or lease_deadline<=0:raise ValueError('Validade inválida.')
   self.tokens=tokens;self.session=session;self.subject=saved['subject'];self.login_nonce=saved['nonce'];self.auth_time=saved.get('auth_time');self.token_deadline=token_deadline;self.lease_deadline=lease_deadline
   self.reason='Conta restaurada. Confirme o acesso pela conexão Integralis.'
  except Exception:self._clear()
 def status(self):
  with self.lock:
   if self.mode=='commercial' and (time.time()>=self.token_deadline or time.time()>=self.lease_deadline):self.allowed=False
   return {'mode':self.mode,'configured':bool(self.issuer and self.client and self.product),'signedIn':bool(self.tokens),'allowed':self.mode=='development' or self.allowed,'message':'Modo de desenvolvimento local — sem licença comercial validada.' if self.mode=='development' else self.reason,'product':self.product or None,'heartbeatSeconds':max(1,int(self.next_heartbeat-time.time())) if self.allowed else None,'lastLoginFailure':dict(self.last_login_failure) if self.last_login_failure else None}
 def _endpoint(self,url):
  u=urlsplit(url);base=urlsplit(self.issuer)
  if u.scheme!='https' or u.netloc!=base.netloc or u.username or u.password or u.fragment or u.query or not u.path.startswith(base.path+'/'):raise ValueError('Endpoint OIDC fora do emissor confiável.')
  return url
 def _discover(self):
  result=self.transport('GET',self.issuer+'/.well-known/openid-configuration')
  if result.get('issuer')!=self.issuer:raise ValueError('Emissor OIDC divergente.')
  for key in ('authorization_endpoint','token_endpoint','jwks_uri'):self._endpoint(result[key])
  if result.get('revocation_endpoint'):self._endpoint(result['revocation_endpoint'])
  self.discovery=result;return result
 def login(self):
  with self.lock:
   if not self.status()['configured']:raise ValueError('A instalação comercial ainda não foi configurada pelo administrador.')
   if self.pending and time.monotonic()<self.pending['expires']:return {'url':self.pending['url']}
   self._clear();d=self._discover();verifier=secrets.token_urlsafe(48);state=secrets.token_urlsafe(32);nonce=secrets.token_urlsafe(32)
   self.pending={'verifier':verifier,'state':state,'nonce':nonce,'expires':time.monotonic()+300}
   challenge=base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).rstrip(b'=').decode()
   self.pending['url']=d['authorization_endpoint']+'?'+urlencode({'client_id':self.client,'redirect_uri':self.redirect,'response_type':'code','scope':'openid email offline_access entitlements:read use_sessions','prompt':'consent','code_challenge':challenge,'code_challenge_method':'S256','state':state,'nonce':nonce})
   return {'url':self.pending['url']}
 def _validate_id(self,token,nonce,access,refresh=False):
  try:
   import jwt
   head=jwt.get_unverified_header(token)
   if head.get('alg')!='RS256' or not head.get('kid'):raise ValueError('Algoritmo OIDC inválido.')
   keys=self.transport('GET',self.discovery['jwks_uri']).get('keys',[])
   matches=[k for k in keys if k.get('kid')==head['kid'] and k.get('kty')=='RSA' and k.get('use','sig')=='sig' and k.get('alg','RS256')=='RS256']
   if len(matches)!=1:raise ValueError('Chave OIDC não reconhecida.')
   claims=jwt.decode(token,jwt.PyJWK(matches[0]).key,algorithms=['RS256'],issuer=self.issuer,audience=self.client,options={'require':['exp','iat','iss','aud','sub']+([] if refresh else ['nonce'])})
   if not isinstance(claims['sub'],str) or not claims['sub'] or ('nonce' in claims and (not isinstance(claims['nonce'],str) or not hmac.compare_digest(claims['nonce'],nonce))):raise ValueError('Nonce inválido.')
   if refresh and claims['sub']!=self.subject:raise ValueError('Conta divergente.')
   if refresh and 'auth_time' in claims and claims['auth_time']!=self.auth_time:raise ValueError('Autenticação divergente.')
   if claims.get('azp',self.client)!=self.client or isinstance(claims['aud'],list) and len(claims['aud'])>1 and claims.get('azp')!=self.client:raise ValueError('Parte autorizada inválida.')
   if 'at_hash' in claims:
    expected=base64.urlsafe_b64encode(hashlib.sha256(access.encode()).digest()[:16]).rstrip(b'=').decode()
    if not hmac.compare_digest(claims['at_hash'],expected):raise ValueError('Hash de token inválido.')
   return claims
  except ImportError:raise ValueError('Validador OIDC indisponível. Reinstale a distribuição comercial.') from None
  except Exception:raise ValueError('ID token inválido ou expirado.') from None
 def callback(self,query):
  with self.lock:
   pending=self.pending
   # An unrelated/replayed return must not consume a newer login or log out a verified session.
   if not pending or time.monotonic()>pending['expires'] or not isinstance(query.get('state'),str) or not hmac.compare_digest(query['state'],pending['state']):raise ValueError('Retorno de login inválido, expirado ou já utilizado.')
   self.pending=None;stage='authorization_return'
   try:
    if query.get('error') or not query.get('code'):raise ValueError('Retorno de login recusado ou incompleto.')
    stage='token_exchange'
    tokens=self.transport('POST',self.discovery['token_endpoint'],data={'grant_type':'authorization_code','client_id':self.client,'redirect_uri':self.redirect,'code':query['code'],'code_verifier':pending['verifier']},form=True)
    if tokens.get('token_type','').lower()!='bearer' or not tokens.get('access_token'):raise ValueError('Resposta OIDC inválida.')
    stage='id_token_validation'
    claims=self._validate_id(tokens['id_token'],pending['nonce'],tokens['access_token'])
    lifetime=float(tokens['expires_in'])
    if not math.isfinite(lifetime) or lifetime<=0:raise ValueError('Token expirado.')
    self.tokens=tokens;self.token_deadline=time.time()+lifetime;self.subject=claims['sub'];self.login_nonce=pending['nonce'];self.auth_time=claims.get('auth_time')
    stage='entitlement_check'
    self._check_entitlement()
    stage='session_activation'
    session=self._platform('POST','/use-sessions',{'product':self.product,'activation_key':secrets.token_urlsafe(32)})
    self.session=session['use_session'];self._accept_session(session,initial=True)
    stage='credential_storage'
    self._persist();self.reason='Conta e acesso Integralis confirmados.';return self.status()
   except Exception as exc:
    code=exc.code if isinstance(exc,OAuthError) and exc.code in ('invalid_request','invalid_grant','invalid_client','unauthorized_client','invalid_token','insufficient_scope','invalid_scope','access_denied','use_session_required','use_session_invalid','use_session_revoked','use_session_expired','use_session_replaced','use_session_closed','product_not_allowed','product_not_linked','product_not_entitled','not_entitled','product_inactive') else 'unknown'
    status=exc.status if isinstance(exc,OAuthError) and type(exc.status) is int and 100<=exc.status<=599 else None
    self._clear();self.last_login_failure={'stage':stage,'httpStatus':status,'code':code}
    raise ValueError('Não foi possível confirmar a conta e o acesso Integralis.') from None
 def _platform(self,method,path,data=None):
  if not self.tokens or time.time()>=self.token_deadline:raise PermissionError('Entre novamente na Integralis.')
  origin=urlsplit(self.issuer);url=origin.scheme+'://'+origin.netloc+'/api/platform/v1'+path
  headers={'Authorization':'Bearer '+self.tokens['access_token']}
  if self.session:headers['X-Integralis-Use-Session']=self.session['token']
  return self.transport(method,url,headers=headers,data=data)
 def _refresh(self):
  if not self.tokens:raise PermissionError('Entre novamente na Integralis.')
  if time.time()<self.token_deadline-60:return
  refresh=self.tokens.get('refresh_token')
  if not isinstance(refresh,str) or not refresh:raise PermissionError('Entre novamente na Integralis.')
  if not self.discovery:self._discover()
  try:
   tokens=self.transport('POST',self.discovery['token_endpoint'],data={'grant_type':'refresh_token','client_id':self.client,'refresh_token':refresh},form=True)
  except OAuthError as exc:
   if exc.code in ('invalid_grant','invalid_client','unauthorized_client'):self._clear()
   raise
  try:
   if tokens.get('token_type','').lower()!='bearer' or not isinstance(tokens.get('access_token'),str) or not tokens['access_token'] or not isinstance(tokens.get('refresh_token'),str) or not tokens['refresh_token'] or tokens['refresh_token']==refresh:raise ValueError('Resposta de rotação inválida.')
   lifetime=float(tokens['expires_in'])
   if not math.isfinite(lifetime) or lifetime<=0:raise ValueError('Token expirado.')
   if 'id_token' in tokens:self._validate_id(tokens['id_token'],self.login_nonce,tokens['access_token'],refresh=True)
   self.tokens=tokens;self.token_deadline=time.time()+lifetime
   self._persist()
  except Exception:
   # A consumed refresh token cannot safely be retried after malformed rotation.
   self._clear();raise
 def _check_entitlement(self):
  entries=self._platform('GET','/entitlements')['entitlements']
  for item in entries:
   if item.get('product')==self.product and item.get('active') is True and (item.get('expires_at') is None or _timestamp(item['expires_at'])>time.time()):return
  raise PermissionError('A conta não possui acesso ativo ao produto.')
 def _accept_session(self,result,initial=False):
  session=result['use_session'];lease=result['lease'];deadline=_timestamp(lease['expires_at']);interval=float(lease['interval_seconds'])
  if result.get('ok') is not True or not isinstance(session.get('id'),str) or not session['id'] or session.get('state')!='current' or session.get('product')!=self.product or not math.isfinite(deadline) or deadline<=time.time() or not math.isfinite(interval) or interval<=0:raise PermissionError('Sessão comercial inválida.')
  if initial and (not isinstance(session.get('token'),str) or not session['token']) or not initial and session.get('id')!=self.session.get('id'):raise PermissionError('Sessão comercial substituída.')
  self.lease_deadline=deadline;self.next_heartbeat=time.time()+min(interval,60);self.allowed=True
 def require_access(self):
  with self.lock:
   if self.mode=='development':return self.status()
   try:
    if not self.session or time.time()>=self.lease_deadline:raise PermissionError('Sessão expirada. Entre explicitamente na Integralis.')
    self._refresh()
    self._check_entitlement()
    self._accept_session(self._platform('POST','/use-sessions/heartbeat',{'product':self.product}))
    self._persist()
    return self.status()
   except Exception as exc:
    if isinstance(exc,OAuthError) and exc.code.startswith('use_session_'):
     self.session=None;self.lease_deadline=0
     self.vault.delete('integralis.tokens');self.vault.delete('integralis.use-session')
    self.allowed=False;self.reason='Acesso não confirmado. Entre novamente ou verifique sua conexão.'
    raise PermissionError(self.reason) from None
 def heartbeat(self):return self.require_access()
 def _clear(self):
  self.tokens=None;self.session=None;self.allowed=False;self.token_deadline=0;self.lease_deadline=0;self.pending=None;self.subject=None;self.login_nonce=None;self.auth_time=None;self.last_login_failure=None
  self.vault.delete('integralis.tokens');self.vault.delete('integralis.use-session')
 def logout(self):
  with self.lock:
   try:
    if self.tokens:
     try:self._refresh()
     except Exception:pass
     if not self.discovery:
      try:self._discover()
      except Exception:pass
     if self.session:
      try:self._platform('POST','/use-sessions/close',{})
      except Exception:pass
     if self.tokens and self.discovery and self.discovery.get('revocation_endpoint'):
      for key in ('refresh_token','access_token'):
       if self.tokens.get(key):
        try:self.transport('POST',self.discovery['revocation_endpoint'],data={'client_id':self.client,'token':self.tokens[key],'token_type_hint':key},form=True)
        except Exception:pass
   finally:self._clear();self.reason='Você saiu desta instalação. Revogue a conexão na Integralis se estava sem rede.'
   return self.status()
