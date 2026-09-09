"""Read-only semantic mutations of a real v2 receipt; no Player dispatch."""
import copy,subprocess,sys,unittest
from pathlib import Path,PureWindowsPath
from unittest.mock import patch
import subdivision_historical as m
class HistoricalTests(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  cls.repo=Path(__file__).resolve().parents[2];cls.base=cls.repo/"Artifacts/gradient-subdivision-player-r2"
  if not (cls.base/"matrix-report-r1.json").exists():raise unittest.SkipTest("Local evidence unavailable")
  cls.plan=m.read(cls.base/"matrix-plan.json");cls.run_config=cls.plan["runs"][54];cls.build=m.read(cls.base/"build-manifest.json")
  cls.relative="Artifacts/gradient-subdivision-player-r2/matrix-recovery2";cls.path=cls.repo/cls.relative/".receipts"/(cls.run_config["runId"]+".json")
  cls.value=m.read(cls.path);cls.original=staticmethod(m.read)
 def call(self):
  return m.receipt(self.repo,PureWindowsPath(self.repo),self.relative,self.run_config,m.contracts.sha256_file(self.base/"matrix-plan.json"),m.contracts.sha256_file(self.base/"build-manifest.json"),self.build,"Tools/GradientLab/subdivision_focus_launch.py",m.contracts.sha256_file(self.base/"campaign-policy-r2.json"),True)
 def test_positive(self):self.assertEqual(self.call()["exitCode"],0)
 def test_semantic_mutations(self):
  for change in (
   lambda r:r.update(pid=0),lambda r:r.update(exitCode=3),lambda r:r.update(player="C:/other/player.exe"),
   lambda r:r.update(launcherSha256="0"*64),lambda r:r.update(recoveryPolicySha256="0"*64),
   lambda r:r["files"].pop("samples.csv"),lambda r:r["startupFocus"].update(acquiredUtc="2099-01-01T00:00:00Z"),
  ):
   bad=copy.deepcopy(self.value);change(bad)
   with patch.object(m,"read",side_effect=lambda p:bad if p==self.path else self.original(p)):
    with self.assertRaises(ValueError):self.call()
 def test_wrong_external_manifest(self):
  archive=self.repo/"Artifacts/baselines/gradient-subdivision-r2-r1"
  result=subprocess.run([sys.executable,"-B",str(archive/"Tools/GradientLab/subdivision_historical.py"),"--archive",str(archive),"--manifest-sha256","0"*64],capture_output=True,text=True)
  self.assertNotEqual(result.returncode,0);self.assertIn("External manifest hash",result.stderr)
if __name__=="__main__":unittest.main()
