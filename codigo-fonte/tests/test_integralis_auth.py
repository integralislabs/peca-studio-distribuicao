import base64, hashlib, importlib.util, json, tempfile, time, unittest
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

class IntegralisTests(unittest.TestCase):
 def setUp(self):
  self.assertIsNotNone(importlib.util.find_spec('integralis_auth'), 'native OIDC service is missing')
  from integralis_auth import IntegralisAuth
  import jwt
  from cryptography.hazmat.primitives.asymmetric import rsa
  self.key=rsa.generate_private_key(public_exponent=65537,key_size=2048)
  self.jwk=json.loads(jwt.algorithms.RSAAlgorithm.to_jwk(self.key.public_key()));self.jwk.update(kid='fixture',alg='RS256',use='sig')
  self.vault={};self.calls=[];self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
  class Vault:
   def get(_,k,d=None):return self.vault.get(k,d)
   def set(_,k,v):self.vault[k]=v
   def delete(_,k):self.vault.pop(k,None)
  self.config={'mode':'commercial','issuer':'https://identity.example/api/oidc','client_id':'fixture-client','product':'fixture-product'}
  self.claim_changes={};self.entitled=True;self.remote_error=False
  def transport(method,url,headers=None,data=None,form=False):
   self.calls.append((method,url,headers,data))
   if self.remote_error:raise OSError('offline')
   if url.endswith('openid-configuration'):return {'issuer':self.config['issuer'],**{k:self.config['issuer']+'/'+v for k,v in [('authorization_endpoint','auth'),('token_endpoint','token'),('jwks_uri','jwks'),('revocation_endpoint','revoke')]}}
   if url.endswith('/jwks'):return {'keys':[self.jwk]}
   if url.endswith('/token'):
    claims={'iss':self.config['issuer'],'aud':self.config['client_id'],'sub':'fixture-account','iat':int(time.time()),'exp':int(time.time())+600,'nonce':self.nonce,**self.claim_changes}
    return {'access_token':'fixture-access','id_token':jwt.encode(claims,self.key,algorithm='RS256',headers={'kid':'fixture'}),'token_type':'Bearer','expires_in':600}
   if url.endswith('/entitlements'):return {'entitlements':[{'product':self.config['product'],'active':self.entitled,'expires_at':None}]}
   if url.endswith('/close') or url.endswith('/revoke'):return {'ok':True}
   return {'ok':True,'use_session':{'id':'fixture-session','state':'current','product':self.config['product'],**({'token':'fixture-use'} if url.endswith('/use-sessions') else {})},'lease':{'expires_at':'2099-01-01T00:00:00Z','interval_seconds':30,'max_offline_seconds':90}}
  self.auth=IntegralisAuth(Path(self.tmp.name),8765,config=self.config,vault=Vault(),transport=transport)
 def login(self):
  info=self.auth.login();q=parse_qs(urlsplit(info['url']).query);self.nonce=q['nonce'][0];self.state=q['state'][0];return q
 def finish(self):self.login();return self.auth.callback({'state':self.state,'code':'fixture-code'})
 def test_unconfigured_and_development_are_distinct(self):
  from integralis_auth import IntegralisAuth
  auth=IntegralisAuth(Path(self.tmp.name),8765,config={})
  self.assertFalse(auth.status()['allowed']);self.assertFalse(auth.status()['configured'])
  dev=IntegralisAuth(Path(self.tmp.name),8765,config={'mode':'development'})
  self.assertEqual(dev.status()['mode'],'development');self.assertTrue(dev.status()['allowed'])
 def test_pkce_state_nonce_and_loopback(self):
  q=self.login();self.assertEqual(q['code_challenge_method'],['S256']);self.assertEqual(q['redirect_uri'],['http://127.0.0.1:8765/api/local/integralis/callback'])
  self.assertNotIn('client_secret',q);self.assertGreaterEqual(len(q['state'][0]),32)
  self.auth.callback({'state':self.state,'code':'fixture-code'})
  call=next(c for c in self.calls if c[1].endswith('/token'))
  self.assertEqual(q['code_challenge'][0],base64.urlsafe_b64encode(hashlib.sha256(call[3]['code_verifier'].encode()).digest()).rstrip(b'=').decode())
 def test_success_backend_tokens_only(self):
  result=self.finish();self.assertTrue(result['allowed']);self.assertNotIn('fixture-access',json.dumps(result));self.assertIn('integralis.tokens',self.vault)
  self.assertTrue(self.auth.require_access()['allowed'])
 def test_state_replay_and_wrong_state(self):
  self.login()
  with self.assertRaises(ValueError):self.auth.callback({'state':'wrong','code':'x'})
  self.assertTrue(self.auth.callback({'state':self.state,'code':'fixture-code'})['allowed'])
  with self.assertRaises(ValueError):self.auth.callback({'state':self.state,'code':'fixture-code'})
  self.assertTrue(self.auth.status()['allowed'])
 def test_stale_callback_preserves_newer_pending_login(self):
  self.login();older=self.state;self.auth.pending['expires']=0
  self.login();current=dict(self.auth.pending);calls=len(self.calls)
  with self.assertRaises(ValueError):self.auth.callback({'state':older,'code':'stale-code'})
  self.assertEqual(self.auth.pending,current);self.assertEqual(len(self.calls),calls)
  self.assertTrue(self.auth.callback({'state':self.state,'code':'fixture-code'})['allowed'])
 def test_replayed_callback_preserves_verified_session_and_vault(self):
  self.finish();saved=dict(self.vault);session=dict(self.auth.session);calls=len(self.calls)
  for state in (self.state,'unrelated'):
   with self.assertRaises(ValueError):self.auth.callback({'state':state,'code':'old-code'})
   self.assertEqual(self.vault,saved);self.assertEqual(self.auth.session,session)
   self.assertEqual(len(self.calls),calls);self.assertTrue(self.auth.require_access()['allowed']);calls=len(self.calls)
 def test_reopening_pending_login_reuses_the_same_flow(self):
  first=self.auth.login();pending=dict(self.auth.pending);calls=len(self.calls)
  self.assertEqual(self.auth.login(),first);self.assertEqual(self.auth.pending,pending)
  self.assertEqual(len(self.calls),calls)
  exposed=json.dumps(self.auth.status())
  for secret in (pending['state'],pending['nonce'],pending['verifier'],first['url']):self.assertNotIn(secret,exposed)
 def test_login_failure_diagnostic_contains_only_safe_stage_and_code(self):
  from integralis_auth import OAuthError
  self.login()
  def fail(*args,**kwargs):raise OAuthError('fixture-access-private-provider-message',401)
  self.auth.transport=fail
  with self.assertRaises(ValueError):self.auth.callback({'state':self.state,'code':'fixture-code'})
  status=self.auth.status();self.assertFalse(status['signedIn']);self.assertFalse(status['allowed'])
  self.assertEqual(status['lastLoginFailure'],{'stage':'token_exchange','httpStatus':401,'code':'unknown'})
  exposed=json.dumps(status)
  for secret in ('fixture-access','private-provider-message','fixture-code',self.state,self.nonce):self.assertNotIn(secret,exposed)
 def test_matched_callback_failures_still_clear_credentials(self):
  self.login();self.claim_changes={'nonce':'wrong'}
  with self.assertRaises(ValueError):self.auth.callback({'state':self.state,'code':'fixture-code'})
  self.assertFalse(self.auth.status()['signedIn']);self.assertIsNone(self.auth.pending)
  self.assertNotIn('integralis.tokens',self.vault)
  self.assertEqual(self.auth.status()['lastLoginFailure']['stage'],'id_token_validation')
 def test_documented_platform_error_codes_remain_finite(self):
  from integralis_auth import OAuthError
  original=self.auth.transport
  for code in ('product_not_entitled','product_not_linked','use_session_closed'):
   with self.subTest(code=code):
    self.auth.transport=original;self.login()
    def fail(*args,**kwargs):raise OAuthError(code,403)
    self.auth.transport=fail
    with self.assertRaises(ValueError):self.auth.callback({'state':self.state,'code':'fixture-code'})
    self.assertEqual(self.auth.status()['lastLoginFailure'],{'stage':'token_exchange','httpStatus':403,'code':code})
 def test_invalid_claims_rejected(self):
  for changes in [{'nonce':'wrong'},{'iss':'https://evil.example'},{'aud':'other'},{'exp':1},{'azp':'other'},{'sub':''}]:
   with self.subTest(changes=changes):
    self.claim_changes=changes;self.login()
    with self.assertRaises(ValueError):self.auth.callback({'state':self.state,'code':'x'})
    self.assertFalse(self.auth.status()['allowed'])
 def test_entitlement_revocation_and_network_fail_closed(self):
  self.finish();self.entitled=False
  with self.assertRaises(PermissionError):self.auth.require_access()
  self.assertFalse(self.auth.status()['allowed'])
  self.entitled=True;self.finish();self.remote_error=True
  with self.assertRaises(PermissionError):self.auth.require_access()
  self.assertFalse(self.auth.status()['allowed'])
 def test_logout_clears_local_secrets_even_offline(self):
  self.finish();self.remote_error=True;self.auth.logout();self.assertFalse(self.auth.status()['allowed']);self.assertNotIn('integralis.tokens',self.vault)
 def test_expired_access_token_never_uses_lease(self):
  self.finish();self.auth.token_deadline=0
  with self.assertRaises(PermissionError):self.auth.require_access()
 def test_replaced_session_rejected(self):
  self.finish();self.auth.session['id']='replaced'
  with self.assertRaises(PermissionError):self.auth.heartbeat()
  self.assertFalse(self.auth.status()['allowed'])
 def test_tampered_signature_rejected(self):
  self.login();self.jwk['n']=('w' if self.jwk['n'][0]!='w' else 'x')+self.jwk['n'][1:]
  with self.assertRaises(ValueError):self.auth.callback({'state':self.state,'code':'x'})
 def test_discovery_cannot_redirect_tokens_to_another_origin(self):
  original=self.auth.transport
  def altered(*args,**kwargs):
   result=original(*args,**kwargs)
   if args[1].endswith('openid-configuration'):result['token_endpoint']='https://evil.example/token'
   return result
  self.auth.transport=altered
  with self.assertRaises(ValueError):self.auth.login()
  self.assertFalse(any(c[1].startswith('https://evil.example') for c in self.calls))
 def test_login_expiration_and_no_secret_echo(self):
  self.login();self.auth.pending['expires']=0
  with self.assertRaises(ValueError):self.auth.callback({'state':self.state,'code':'x'})
  self.assertNotIn('fixture-code',json.dumps(self.auth.status()))

if __name__=='__main__':unittest.main()
