import hashlib,json,tempfile,unittest
from update_service import UpdateService

class DistributionUpdatesTests(unittest.TestCase):
 def test_customer_channel_uses_no_github_credential_and_checks_hash(self):
  with tempfile.TemporaryDirectory() as root:
   binary=b'MZ fixture installer';manifest={'version':'1.9.0','installer':'PecaStudio-Setup-1.9.0.exe','sha256':hashlib.sha256(binary).hexdigest()}
   s=UpdateService(root,'1.8.0',distribution={'manifest_url':'https://updates.example.com/peca/release-manifest.json'})
   s._https=lambda url,limit:json.dumps(manifest).encode() if url.endswith('.json') else binary
   s._gh=lambda *a,**k:self.fail('Customer must not need GitHub access')
   self.assertTrue(s.dispatch('check')['release']['available']);self.assertTrue(s.dispatch('download')['downloaded'])
 def test_cross_origin_installer_is_rejected_before_download(self):
  with tempfile.TemporaryDirectory() as root:
   s=UpdateService(root,'1.8.0',distribution={'manifest_url':'https://updates.example.com/release-manifest.json'})
   s._https=lambda *a:json.dumps({'version':'1.9.0','installer':'PecaStudio-Setup-1.9.0.exe','sha256':'a'*64,'installer_url':'https://other.example.com/setup.exe'}).encode()
   with self.assertRaises(ValueError):s.dispatch('check')

if __name__=='__main__':unittest.main()
