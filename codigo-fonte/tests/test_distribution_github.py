import tempfile,unittest,json
from update_service import UpdateService

class GitHubChannelTests(unittest.TestCase):
 def service(self,root):return UpdateService(root,'1.9.0',distribution={'manifest_url':'https://raw.githubusercontent.com/integralislabs/peca-studio-distribuicao/main/release-manifest.json','download_base_url':'https://github.com/integralislabs/peca-studio-distribuicao/releases/download/'})
 def test_only_configured_release_repo_can_supply_the_installer(self):
  with tempfile.TemporaryDirectory() as root:
   s=self.service(root)
   good='https://github.com/integralislabs/peca-studio-distribuicao/releases/download/v2.0.0/PecaStudio-Setup-2.0.0.exe'
   self.assertEqual(s._channel_url(good),good)
   for bad in ['https://github.com/other/repo/releases/download/v2/setup.exe','https://evil.example/setup.exe','http://github.com/integralislabs/peca-studio-distribuicao/releases/download/setup.exe']:
    with self.assertRaises(ValueError):s._channel_url(bad)
 def test_only_github_signed_asset_redirect_is_allowed(self):
  with tempfile.TemporaryDirectory() as root:
   s=self.service(root);source='https://github.com/integralislabs/peca-studio-distribuicao/releases/download/v2/setup.exe'
   self.assertTrue(s._allowed_asset_redirect(source,'https://release-assets.githubusercontent.com/github-production-release-asset/x?signature=temporary'))
   self.assertFalse(s._allowed_asset_redirect(source,'https://evil.example/x'))
   self.assertFalse(s._allowed_asset_redirect(s.distribution['manifest_url'],'https://release-assets.githubusercontent.com/x'))
