import json, time, unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import test_integralis_auth as auth_tests

class RefreshTests(unittest.TestCase):
 login=auth_tests.IntegralisTests.login
 finish=auth_tests.IntegralisTests.finish
 def setUp(self):
  auth_tests.IntegralisTests.setUp(self)
  original=self.auth.transport
  self.refresh_changes={}; self.refresh_error=None; self.refresh_count=0
  def transport(method,url,headers=None,data=None,form=False):
   if url.endswith('/token') and data.get('grant_type')=='refresh_token':
    self.refresh_count+=1
    if self.refresh_error:raise self.refresh_error
    import jwt
    claims={'iss':self.config['issuer'],'aud':self.config['client_id'],'sub':'fixture-account','iat':int(time.time()),'exp':int(time.time())+300,**self.refresh_changes}
    return {'access_token':'rotated-access','refresh_token':'rotated-refresh','token_type':'Bearer','expires_in':3600,'id_token':jwt.encode(claims,self.key,algorithm='RS256',headers={'kid':'fixture'})}
   result=original(method,url,headers,data,form)
   if url.endswith('/token'):result['refresh_token']='initial-refresh'
   return result
  self.auth.transport=transport
 def restore(self,config=None,root=None):
  from integralis_auth import IntegralisAuth
  return IntegralisAuth(root or Path(self.tmp.name),8766,config=config or self.config,vault=self.auth.vault,transport=self.auth.transport)
 def test_offline_consent_is_requested(self):
  q=self.login();self.assertIn('offline_access',q['scope'][0].split());self.assertEqual(q['prompt'],['consent'])
 def test_refresh_rotates_and_survives_restart_without_replacing_session(self):
  self.finish();self.auth.token_deadline=time.time()-1
  self.assertTrue(self.auth.require_access()['allowed']);self.assertEqual(self.auth.tokens['refresh_token'],'rotated-refresh')
  restored=self.restore();self.assertTrue(restored.status()['signedIn']);self.assertFalse(restored.status()['allowed'])
  self.assertTrue(restored.require_access()['allowed'])
  self.assertEqual(sum(c[1].endswith('/use-sessions') for c in self.calls),1)
 def test_id_token_expiry_does_not_shorten_access_token(self):
  self.finish();self.auth.token_deadline=0;self.auth.require_access()
  self.assertGreater(self.auth.token_deadline,time.time()+3500)
 def test_changed_subject_during_refresh_clears_credentials(self):
  self.finish();self.auth.token_deadline=0;self.refresh_changes={'sub':'other-account'}
  with self.assertRaises(PermissionError):self.auth.require_access()
  self.assertFalse(self.auth.status()['signedIn']);self.assertNotIn('integralis.tokens',self.vault)
 def test_transient_network_failure_keeps_refresh_but_blocks_actions(self):
  self.finish();self.auth.token_deadline=0;self.refresh_error=OSError('offline')
  with self.assertRaises(PermissionError):self.auth.require_access()
  self.assertFalse(self.auth.status()['allowed']);self.assertEqual(self.auth.tokens['refresh_token'],'initial-refresh')
  self.refresh_error=None;self.assertTrue(self.auth.require_access()['allowed'])
 def test_invalid_grant_clears_vault(self):
  from integralis_auth import OAuthError
  self.finish();self.auth.token_deadline=0;self.refresh_error=OAuthError('invalid_grant',400)
  with self.assertRaises(PermissionError):self.auth.require_access()
  self.assertFalse(self.auth.status()['signedIn']);self.assertNotIn('integralis.tokens',self.vault)
 def test_expired_lease_never_silently_reacquires(self):
  self.finish();self.auth.lease_deadline=0
  with self.assertRaises(PermissionError):self.auth.require_access()
  self.assertEqual(sum(c[1].endswith('/use-sessions') for c in self.calls),1)
 def test_restore_rejects_changed_installation_or_product(self):
  self.finish();other=self.restore(config={**self.config,'product':'another'})
  self.assertFalse(other.status()['signedIn'])
  self.finish();other=self.restore(root=Path(self.tmp.name)/'other-installation')
  self.assertFalse(other.status()['signedIn'])
 def test_concurrent_actions_refresh_only_once(self):
  self.finish();self.auth.token_deadline=0
  with ThreadPoolExecutor(max_workers=4) as pool:results=list(pool.map(lambda _:self.auth.require_access(),range(4)))
  self.assertTrue(all(r['allowed'] for r in results));self.assertEqual(self.refresh_count,1)
 def test_logout_revokes_rotated_refresh_and_access(self):
  self.finish();self.auth.token_deadline=0;self.auth.require_access();self.auth.logout()
  revoked=[c[3]['token'] for c in self.calls if c[1].endswith('/revoke')]
  self.assertCountEqual(revoked,['rotated-refresh','rotated-access']);self.assertFalse(self.restore().status()['signedIn'])

 def test_refresh_without_id_token_uses_previously_verified_subject(self):
  self.finish();original=self.auth.transport
  def transport(*args,**kwargs):
   result=original(*args,**kwargs)
   if args[1].endswith('/token'):result.pop('id_token',None)
   return result
  self.auth.transport=transport;self.auth.token_deadline=0
  self.assertTrue(self.auth.require_access()['allowed']);self.assertEqual(self.auth.subject,'fixture-account')
 def test_refresh_wrong_nonce_rejected(self):
  self.finish();self.auth.token_deadline=0;self.refresh_changes={'nonce':'other'}
  with self.assertRaises(PermissionError):self.auth.require_access()
  self.assertFalse(self.auth.status()['signedIn'])
 def test_restored_deadlines_are_absolute_and_invalid_record_is_cleared(self):
  self.finish();deadline=self.auth.token_deadline;restored=self.restore()
  self.assertEqual(restored.token_deadline,deadline)
  record=json.loads(self.vault['integralis.tokens']);record['token_deadline']='NaN';self.vault['integralis.tokens']=json.dumps(record)
  self.assertFalse(self.restore().status()['signedIn']);self.assertNotIn('integralis.tokens',self.vault)
 def test_missing_session_id_never_grants_access(self):
  self.login();original=self.auth.transport
  def transport(*args,**kwargs):
   result=original(*args,**kwargs)
   if args[1].endswith('/use-sessions'):result['use_session'].pop('id')
   return result
  self.auth.transport=transport
  with self.assertRaises(ValueError):self.auth.callback({'state':self.state,'code':'code'})
  self.assertFalse(self.auth.status()['allowed'])

 def test_refresh_cannot_change_original_authentication_time(self):
  self.claim_changes={'auth_time':int(time.time())-60};self.finish()
  self.refresh_changes={'auth_time':int(time.time())};self.auth.token_deadline=0
  with self.assertRaises(PermissionError):self.auth.require_access()
  self.assertFalse(self.auth.status()['signedIn'])
 def test_replaced_remote_session_is_removed_locally(self):
  from integralis_auth import OAuthError
  self.finish();original=self.auth.transport
  def transport(*args,**kwargs):
   if args[1].endswith('/heartbeat'):raise OAuthError('use_session_replaced',409)
   return original(*args,**kwargs)
  self.auth.transport=transport
  with self.assertRaises(PermissionError):self.auth.require_access()
  self.assertIsNone(self.auth.session)
  self.assertFalse(self.restore().status()['allowed'])

if __name__=='__main__':unittest.main()

