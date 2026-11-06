import importlib.util,unittest
from pathlib import Path
spec=importlib.util.spec_from_file_location('build_desktop_local',Path(__file__).resolve().parents[1]/'packaging/build_desktop.py')
build=importlib.util.module_from_spec(spec);spec.loader.exec_module(build)
class CommercialBuildTests(unittest.TestCase):
 def test_commercial_installer_cannot_reuse_unverified_development_bundle(self):
  with self.assertRaisesRegex(ValueError,'compilar'):build.validate_build_mode(True,'commercial-config.json')
  build.validate_build_mode(False,'commercial-config.json')
