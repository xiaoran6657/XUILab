"""Full campaign report with explicit failed attempts and stricter origin audit."""
import argparse,json
from pathlib import Path
import gradient_experiment as c
from adaptive_campaign_report import verify
from adaptive_attempt_audit import audit

def report(plan,runs,repo,gate,build,policy,policy_hash):
    result=verify(plan,runs,repo,gate,build,policy,policy_hash)
    result["invalidAttempts"]=audit(repo,plan,build,policy)
    result["finalReportToolSha256"]=c.sha256_file(Path(__file__))
    result["attemptAuditToolSha256"]=c.sha256_file(Path(__file__).with_name("adaptive_attempt_audit.py"))
    return result

if __name__=="__main__":
    p=argparse.ArgumentParser(description=__doc__)
    for n in ("plan","runs","repo","gate","build","policy","output"):p.add_argument("--"+n,type=Path,required=True)
    p.add_argument("--policy-sha256",required=True);a=p.parse_args()
    r=report(a.plan.resolve(),a.runs.absolute(),a.repo.resolve(),a.gate.resolve(),a.build.resolve(),a.policy.resolve(),a.policy_sha256);c.write_json_new(a.output,r);print(json.dumps(dict(runCount=r["runCount"],invalidAttempts=r["invalidAttempts"],comparisons=r["comparisons"])))
