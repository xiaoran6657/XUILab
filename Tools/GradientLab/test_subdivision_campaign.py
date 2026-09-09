import copy,json,tempfile,unittest
from pathlib import Path
from subdivision_campaign import validate_policy
from subdivision_focus_launch import verify_startup_focus
from player_verify import read
class CampaignTests(unittest.TestCase):
 def test_frozen_policy_mutations(self):
  repo=Path(__file__).resolve().parents[2];base=repo/"Artifacts/gradient-subdivision-player-r2";source=base/"campaign-policy-r2.json"
  if not source.exists():self.skipTest("Local evidence unavailable")
  policy=read(source);planpath=base/"matrix-plan.json";plan=read(planpath);gate=repo/"Artifacts/gradient-subdivision-validation/preflight-r2.json";build=base/"build-manifest.json";target=repo/policy["continuedRoot"]
  validate_policy(source,plan,planpath,gate,build,repo,target)
  with tempfile.TemporaryDirectory() as temp:
   path=Path(temp)/"policy.json"
   for change in (
    lambda p:p.update(resumeIndex=55),lambda p:p["selectedRunIds"].reverse(),
    lambda p:p.update(continuedRoot=p["retained"][0]["root"]),lambda p:p.update(toolInputs={}),
    lambda p:p.update(continuedRoot=p["retained"][0]["root"]+"/new-child"),
    lambda p:p.update(continuedRoot=p["retained"][1]["root"]+"/new-child"),
    lambda p:p.update(continuedRoot="Artifacts/gradient-subdivision-player-r2"),
    lambda p:p.update(priorPolicySha256="0"*64),lambda p:p["retained"][1].update(startIndex=53),
    lambda p:p["retained"][0]["files"].pop(next(iter(p["retained"][0]["files"]))),
    lambda p:p["retained"][1]["files"].pop(next(iter(p["retained"][1]["files"]))),
   ):
    bad=copy.deepcopy(policy);change(bad);path.write_text(json.dumps(bad))
    with self.assertRaises(ValueError):validate_policy(path,plan,planpath,gate,build,repo,repo/bad["continuedRoot"])
 def test_focus_must_precede_prepare(self):
  with tempfile.TemporaryDirectory() as temp:
   directory=Path(temp);(directory/"events.log").write_text("2026-09-08T01:00:01Z state=Prepare\n")
   focus=dict(acquired=True,pid=123,activationCalls=1,lastActivationUtc="2026-09-08T01:00:00Z",acquiredUtc="2026-09-08T01:00:00Z")
   verify_startup_focus(focus,directory,123)
   focus["acquiredUtc"]="2026-09-08T01:00:02Z"
   with self.assertRaises(ValueError):verify_startup_focus(focus,directory,123)
if __name__=="__main__":unittest.main()
