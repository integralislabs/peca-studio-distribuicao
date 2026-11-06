import unittest,tempfile,hashlib
from pathlib import Path
class DesktopTests(unittest.TestCase):
 def test_paths_outside_resources(self):
  import desktop_app
  self.assertNotEqual(desktop_app.data_root(),desktop_app.resource_root())
 def test_integrity_refuses_modified_installer(self):
  from update_service import verify_installer
  with tempfile.TemporaryDirectory() as d:
   p=Path(d)/'setup.exe';p.write_bytes(b'good')
   verify_installer(p,hashlib.sha256(b'good').hexdigest())
   p.write_bytes(b'bad')
   with self.assertRaises(ValueError):verify_installer(p,hashlib.sha256(b'good').hexdigest())
 def test_install_requires_confirmation(self):
  from update_service import UpdateService
  with tempfile.TemporaryDirectory() as d:
   with self.assertRaises(ValueError):UpdateService(d,'1.7.0').dispatch('install',{})
if __name__=='__main__':unittest.main()
