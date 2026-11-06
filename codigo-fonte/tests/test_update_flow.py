import hashlib,tempfile,unittest
from update_service import UpdateService
class UpdateFlowTests(unittest.TestCase):
 def test_install_rechecks_after_tamper(self):
  with tempfile.TemporaryDirectory() as d:
   s=UpdateService(d,'1.7.0');payload=b'MZinstaller'
   s._write({'release':{'available':True},'installer':'PecaStudio-Setup-1.8.0.exe','sha256':hashlib.sha256(payload).hexdigest(),'asset':3});s._gh=lambda *a,**k:payload
   self.assertTrue(s.dispatch('download')['downloaded'])
   (s.root/'PecaStudio-Setup-1.8.0.exe').write_bytes(b'tampered')
   with self.assertRaisesRegex(ValueError,'Integridade'):s.dispatch('install',{'confirm':True})
 def test_bad_download_is_removed(self):
  with tempfile.TemporaryDirectory() as d:
   s=UpdateService(d,'1.7.0');s._write({'release':{'available':True},'installer':'PecaStudio-Setup-1.8.0.exe','sha256':'a'*64,'asset':3});s._gh=lambda *a,**k:b'bad'
   with self.assertRaises(ValueError):s.dispatch('download')
   self.assertFalse(s.status()['downloaded']);self.assertFalse(list(s.root.glob('*.part')))
