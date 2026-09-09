"""Frozen List refresh plans; standard-library-only."""
from __future__ import annotations
import argparse, hashlib, json, re
from pathlib import Path
ARTIFACTS=["config.json","environment.json","identity.json","samples.csv","summary.json","report.md","events.log","refresh-metrics.json","refresh-samples.csv","refresh-binding.json"]
CASE=re.compile(r"listrefresh-(normal|virtual)-1000-(window|target)-(idle|sparse|burst|high|batch)\Z")
def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def validate_plan(p,require_frozen=True):
    if p.get("schemaVersion")!="xuilab.list-refresh.plan/v1" or p.get("status")!="frozen" or p.get("contractId")!="list-refresh/v1":raise ValueError("Plan schema/status/contract")
    if p["artifacts"]!=ARTIFACTS or p["evidenceKind"]!="windows-development-player":raise ValueError("Artifact/tier contract")
    seen=set()
    for r in p["runs"]:
        if not CASE.fullmatch(r["caseId"]) or r["runId"] in seen or not re.fullmatch(r"[A-Za-z0-9_-]+",r["runId"]):raise ValueError("Case/run identity")
        seen.add(r["runId"])
        if (r["warmupFrames"],r["measureFrames"],r["sampleCapacity"],r["timeoutSeconds"])!=(300,1800,1800,180):raise ValueError("Sampling protocol")
        if not 1<=r["runIndex"]<=r["plannedRepeatCount"] or r["plannedRepeatCount"] not in (1,5):raise ValueError("Repeat contract")
        if r["parameters"]["targetFrameRate"] not in (-1,60) or r["parameters"]["vSyncCount"]!=0:raise ValueError("Pacing")
    if not seen:raise ValueError("Empty plan")
    if p.get("protocolVersion")!="xuilab.benchmark.protocol/v1" or p.get("dirty") is not True:raise ValueError("Protocol/evidence mode")
    pilot=len(p["runs"])==4
    combos=[("virtual","high",-1),("normal","batch",-1)] if pilot else [(b,f,-1) for b in ("normal","virtual") for f in ("idle","sparse","burst","high","batch")]+[("virtual","high",60)]
    expected=[(b,f,fps,i,policy) for b,f,fps in combos for i in range(1,2 if pilot else 6) for policy in (("window","target") if i%2 else ("target","window"))]
    actual=[]
    for r in p["runs"]:
        b,policy,f=CASE.fullmatch(r["caseId"]).groups();q=r["parameters"];fps=q["targetFrameRate"]
        if r["variant"]!=policy or r["groupId"]!=f"{b}-{f}-fps{fps}" or r["plannedRepeatCount"]!=(1 if pilot else 5):raise ValueError("Group contract")
        if r["frameBudgetMs"]!=16.6666667 or (q["screenWidth"],q["screenHeight"],q["graphicsApi"],q["qualityLevel"])!=(960,540,"Direct3D11","High Fidelity"):raise ValueError("Environment protocol")
        actual.append((b,f,fps,r["runIndex"],policy))
    if actual!=expected:raise ValueError("Incomplete/reordered protocol matrix")
    return p
def make_plan(plan_id,candidate,build,source,gate,manifest,pilot=False):
    mh=sha(manifest);gh=sha(gate);m=json.loads(Path(manifest).read_text(encoding="utf-8"))
    if any(m[k]!=v for k,v in dict(candidateId=candidate,buildId=build,sourceRevision=source,dirty=True).items()):raise ValueError("Build identity")
    runs=[]
    combos=[(b,p,-1) for b in ("normal","virtual") for p in ("idle","sparse","burst","high","batch")]+[("virtual","high",60)]
    if pilot:combos=[("virtual","high",-1),("normal","batch",-1)]
    for b,profile,fps in combos:
        for repeat in range(1,2 if pilot else 6):
            for policy in (("window","target") if repeat%2 else ("target","window")):
                case=f"listrefresh-{b}-1000-{policy}-{profile}"
                runs.append(dict(runId=f"{plan_id}-{case}-fps{fps}-r{repeat}",groupId=f"{b}-{profile}-fps{fps}",caseId=case,variant=policy,runIndex=repeat,plannedRepeatCount=1 if pilot else 5,
                    warmupFrames=300,measureFrames=1800,sampleCapacity=1800,frameBudgetMs=16.6666667,timeoutSeconds=180,
                    parameters=dict(targetFrameRate=fps,vSyncCount=0,screenWidth=960,screenHeight=540,graphicsApi="Direct3D11",qualityLevel="High Fidelity",preflightSha256=gh,buildManifestSha256=mh)))
    return validate_plan(dict(schemaVersion="xuilab.list-refresh.plan/v1",status="frozen",planId=plan_id,contractId="list-refresh/v1",
        contractSha256=sha("Docs/Experiments/LIST_REFRESH_PROTOCOL-r1.md"),candidateId=candidate,buildId=build,sourceRevision=source,dirty=True,
        evidenceKind="windows-development-player",protocolVersion="xuilab.benchmark.protocol/v1",artifacts=ARTIFACTS,runs=runs))
def main():
    p=argparse.ArgumentParser()
    for name in ("output","plan-id","candidate","build","source","gate","build-manifest"):p.add_argument("--"+name,required=True)
    p.add_argument("--pilot",action="store_true");a=p.parse_args();doc=make_plan(a.plan_id,a.candidate,a.build,a.source,a.gate,a.build_manifest,a.pilot)
    with Path(a.output).open("x",encoding="utf-8") as f:json.dump(doc,f,indent=2);f.write("\n")
    print(json.dumps(dict(runs=len(doc["runs"]),sha256=sha(a.output))))
if __name__=="__main__":main()
