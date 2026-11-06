import json,tempfile,unittest,sys
from pathlib import Path
from unittest.mock import patch
from types import SimpleNamespace
from integralis_auth import installation_config

class BuildPolicyTests(unittest.TestCase):
 def test_commercial_marker_does_not_fall_back_when_config_is_deleted(self):
  with tempfile.TemporaryDirectory() as root,patch.dict(sys.modules,{'peca_commercial_build':SimpleNamespace(COMMERCIAL=True)}):
   self.assertEqual(installation_config(Path(root)),{'mode':'commercial'})
   (Path(root)/'integralis-config.json').write_text(json.dumps({'mode':'development'}))
   with self.assertRaises(ValueError):installation_config(Path(root))
 def test_source_build_is_visibly_development(self):
  with tempfile.TemporaryDirectory() as root,patch.dict(sys.modules,{'peca_commercial_build':None}):
   self.assertEqual(installation_config(Path(root)),{'mode':'development'})

if __name__=='__main__':unittest.main()
