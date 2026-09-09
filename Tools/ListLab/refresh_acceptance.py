"""Supplemental acceptance checks for retained v1 List refresh evidence.
This does not rewrite receipts or claim cryptographic process attestation.
"""
import argparse,datetime as dt,json,re
from collections import Counter
from pathlib import Path
from refresh_verify import read,need,sha,verify,check_gate,contracts
def tree_contract(root,plan):
    names={r["runId"] for r in plan["runs"]}
    need({p.name for p in root.iterdir()}==names|{".receipts",".logs"},"Unknown/missing run root entry or retained intent/failure")
    for folder,suffix in ((".receipts",".json"),(".logs",".log")):
        need({p.name for p in (root/folder).iterdir()}=={n+suffix for n in names},"Missing/unknown "+folder)
def complete_test_details(gate,repo):
    counts={}
    for c in gate["checks"]:
        q=read(repo/c["requestPath"]);e=read(repo/c["terminalPath"]);result=e["response"]["data"]["result"];summary=result["summary"];tests=result["results"]
        expected=22 if c["kind"]=="functional-runner" else 32
        names=[t["fullName"] for t in tests]
        need(len(tests)==summary["total"]==summary["passed"]==expected,"Truncated/inflated test results")
        duplicates={n:c for n,c in Counter(names).items() if c>1}
        # Frozen NUnit source has null plus three distinct arrays; MCP serializes all arrays as System.String[].
        collision="XUILab.Benchmarking.Tests.EditMode.BenchmarkRunnerTests.ProtocolV1_RejectsMissingOrChangedRequiredMetrics(System.String[])"
        need(duplicates==({collision:3} if c["kind"]=="core" else {}),"Unexpected duplicate test names")
        need(all(t["state"]=="Passed" for t in tests),"Nonpassed test detail")
        need(not q["parameters"].get("category_names"),"Unexpected category filter")
        if c["kind"]=="functional-runner":
            files=[repo/("XUILab/Assets/XUILab/ListLab/Tests/"+folder+"/"+name+".cs") for folder,name in
                (("PlayMode","ListViewTests"),("PlayMode","RefreshUpdateTests"),("Benchmarking","ListRefreshBenchmarkTests"),("Benchmarking","ListBenchmarkTests"))]
        else:files=list((repo/"XUILab/Assets/XUILab/Benchmarking/Tests/EditMode").glob("*Tests.cs"))
        declared=set()
        for p in files:
            text=p.read_text(encoding="utf-8-sig");namespace=re.search(r"namespace\s+([\w.]+)",text).group(1);cls=re.search(r"class\s+(\w+)",text).group(1)
            for m in re.finditer(r"\[(?:Test|UnityTest|TestCase(?:Source)?)(?:\([^\]]*\))?\]\s*(?:\[[^\]]+\]\s*)*public\s+(?:void|IEnumerator)\s+(\w+)\s*\(",text):
                declared.add(namespace+"."+cls+"."+m.group(1))
        actual={name.split("(")[0] for name in names}
        need(actual==declared,"Test detail omits declared method or includes unknown method")
        counts[c["kind"]]=expected
    return counts
def supplement(plan_path,root,repo,gate_path,build_path):
    raw=verify(plan_path,root,repo,gate_path,build_path)
    need(raw["status"]=="pass","Raw evidence verification failed")
    plan=read(plan_path);gate=read(gate_path);check_gate(gate,plan,repo);counts=complete_test_details(gate,repo)
    tree_contract(root,plan);need(not (repo/"Artifacts/list-refresh-player.lock").exists(),"Retained Player lock")
    rows=[];ph=sha(plan_path);bh=sha(build_path)
    for run in plan["runs"]:
        name=run["runId"];receipt_path=root/".receipts"/(name+".json");log=root/".logs"/(name+".log");r=read(receipt_path)
        need(r["schemaVersion"]=="xuilab.list-refresh.launch-receipt/v1" and r["runId"]==name,"Receipt schema/run")
        need(type(r["pid"]) is int and r["pid"]>0 and type(r["exitCode"]) is int and r["exitCode"]==0,"Receipt PID/exit")
        need(r["correctness"]=="pass" and r["planSha256"]==ph and r["buildManifestSha256"]==bh,"Receipt outcome/control")
        need(r["identitySha256"]==sha(root/name/"identity.json"),"Receipt identity SHA")
        need(0<r["durationSeconds"]<=run["timeoutSeconds"]+15,"Receipt wall clock")
        dt.datetime.fromisoformat(r["completedUtc"])
        contracts._assert_regular_file(log,str(log))
        contracts._assert_regular_file(root/name/"events.log",str(root/name/"events.log"))
        need(log.is_file() and log.stat().st_size>0,"Missing/empty Player log")
        events=(root/name/"events.log").read_text(encoding="utf-8")
        need("application_paused" not in events and "focus_lost" not in events,"Resize/pause/focus invalidation")
        rows.append(dict(runId=name,pid=r["pid"],exitCode=r["exitCode"],receiptSha256=sha(receipt_path),logSha256=sha(log),identitySha256=r["identitySha256"]))
    return dict(schemaVersion="xuilab.list-refresh.supplement/v1",status="pass",planSha256=ph,buildManifestSha256=bh,tests=counts,runs=rows,
        processEvidence="Frozen launcher Popen/wait receipt plus Player Load actual-executable guard; not authenticated external process attestation.",
        resolutionEvidence="Frozen Bootstrap checks width/height each Update; resize calls MarkPaused -> application_paused and invalid. All retained runs valid with no pause event.",
        logHashTiming="Hashes captured after completion for retention; no historical launch fields fabricated.")
def main():
    p=argparse.ArgumentParser()
    for n in ("plan","runs","gate","build-manifest","output"):p.add_argument("--"+n,type=Path,required=True)
    p.add_argument("--repo",type=Path,default=Path.cwd());a=p.parse_args();d=supplement(a.plan,a.runs,a.repo,a.gate,a.build_manifest)
    with a.output.open("x",encoding="utf-8") as f:json.dump(d,f,indent=2)
    print(json.dumps(dict(status=d["status"],runs=len(d["runs"]),tests=d["tests"])))
if __name__=="__main__":main()
