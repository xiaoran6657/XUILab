"""Read-only three-root report; old reports and evidence stay immutable."""
import argparse,json
from pathlib import Path
import gradient_experiment as contracts
from player_verify import read,need,check_gate,verify_run,quantile
from subdivision_plan import validate_subdivision,SCENARIOS
from subdivision_launch import check_build,check_inventory,verify_receipt as original_receipt
from subdivision_continue import verify_receipt as continued_receipt
from subdivision_focus_launch import verify_receipt as focused_receipt
from subdivision_campaign import validate_policy
from subdivision_report import distribution,compare

def verify(plan_path,run_root,repo,gate_path,build_path,policy_path,policy_hash):
    plan=validate_subdivision(read(plan_path));gate=read(gate_path);check_gate(gate,plan,repo)
    need(contracts.sha256_file(policy_path)==policy_hash,"Campaign policy hash")
    policy=validate_policy(policy_path,plan,plan_path,gate_path,build_path,repo,run_root)
    ph=contracts.sha256_file(plan_path);bh=contracts.sha256_file(build_path);gh=contracts.sha256_file(gate_path)
    manifest=read(build_path);player=(build_path.parent/manifest["player"]).resolve()
    check_build(build_path,player,plan,repo)
    need(gate["sourceInputs"]==manifest["sourceInputs"],"Gate/build source mismatch")
    need(all(r["parameters"]["preflightSha256"]==gh and r["parameters"]["buildManifestSha256"]==bh for r in plan["runs"]),"Control hash mismatch")
    check_inventory(run_root,plan);expected=set(policy["selectedRunIds"])
    need({p.name for p in run_root.iterdir()}==expected|{".receipts",".logs",".launches"},"Complete suffix required")
    for folder,suffix in ((".receipts",".json"),(".logs",".log"),(".launches",".json")):
        need({p.name for p in (run_root/folder).iterdir()}=={r+suffix for r in expected},"Complete sidecars required")
    rows=[];environment=None
    for ordinal,run in enumerate(plan["runs"]):
        if ordinal<52:root=repo/policy["retained"][0]["root"];checker=original_receipt;binding=None
        elif ordinal<54:root=repo/policy["retained"][1]["root"];checker=continued_receipt;binding=policy["priorPolicySha256"]
        else:root=run_root;checker=focused_receipt;binding=policy_hash
        receipt=checker(root,run,ph,bh,player,manifest)
        if binding:need(receipt.get("recoveryPolicySha256")==binding,"Receipt policy mismatch")
        result,detail=verify_run(root/run["runId"],plan,run,ph,repo,gate)
        need(result["correctness"]=="pass" and result["measurementValidity"]=="valid","Run not accepted")
        need(receipt["qualityStatus"]==result["qualityStatus"],"Receipt quality mismatch")
        env=detail["environment"]
        if environment is None:environment=env
        need(all(env.get(k)==environment.get(k) for k in ("operatingSystem","processorType","processorCount","graphicsDeviceName","graphicsDeviceVersion")),"Environment drift")
        values=result["metrics"]["frameIntervalMs"];p=run["parameters"];q=detail["quality"];cost=result["metrics"]["costMetrics"]
        rows.append(dict(runId=run["runId"],root=root.relative_to(repo).as_posix(),scenario=p["scenario"],segments=p["segments"],repeat=run["runIndex"],
            correctness=result["correctness"],measurementValidity=result["measurementValidity"],qualityStatus=result["qualityStatus"],
            p50=quantile(values,.5),p95=quantile(values,.95),p99=quantile(values,.99),maximum=max(values),
            overBudgetRatio=sum(v>run["frameBudgetMs"] for v in values)/len(values),coldPrepareMs=detail["coldPrepareMs"],
            qualityMaxError=q["maxError"],qualityRmsError=q["rmsError"],quantizationMaxError=q["quantizationMaxError"],
            componentDirtyTotal=cost["componentDirtyTotal"],componentRebuildTotal=cost["componentRebuildTotal"],visibleVertices=cost["visibleVertices"]))
    groups=[];comparisons=[]
    for scenario,*_ in SCENARIOS:
        subset=[r for r in rows if r["scenario"]==scenario]
        for seg in (8,16,32,64):
            runs=sorted([r for r in subset if r["segments"]==seg],key=lambda r:r["repeat"])
            need(len(runs)==5,"Five repeats required")
            groups.append(dict(scenario=scenario,segments=seg,runs=runs,
                qualityStatus="pass" if all(r["qualityStatus"]=="pass" for r in runs) else "quality_limited",
                statistics={m:distribution([r[m] for r in runs]) for m in ("p50","p95","p99","maximum","overBudgetRatio","coldPrepareMs","qualityMaxError","qualityRmsError","quantizationMaxError")}))
        baseline=[r["p95"] for r in sorted(subset,key=lambda r:r["repeat"]) if r["segments"]==32]
        for seg in (8,16,64):
            variant=[r["p95"] for r in sorted(subset,key=lambda r:r["repeat"]) if r["segments"]==seg]
            comparisons.append(dict(scenario=scenario,segments=seg,**compare(baseline,variant)))
    return dict(schemaVersion="xuilab.gradient.subdivision-report/v2",status="pass",correctness="pass",measurementValidity="valid",
        candidateId=plan["candidateId"],buildId=plan["buildId"],sourceRevision=plan["sourceRevision"],dirty=plan["dirty"],
        planSha256=ph,buildManifestSha256=bh,preflightSha256=gh,reportToolSha256=contracts.sha256_file(Path(__file__)),
        pilot=False,runCount=len(rows),environment=environment,runs=rows,groups=groups,comparisons=comparisons,
        recovery=dict(policySha256=policy_hash,retainedValidPrefix=54,continuedRoot=policy["continuedRoot"],
            excludedAttempts=[dict(root=span["root"],runId=plan["runs"][span["endIndex"]]["runId"],
                reason="pre-measure focus loss" if i==0 else "startup wall-clock timeout",rawAvailable=i==0,
                candidateId=plan["candidateId"],buildId=plan["buildId"],exitCode=3 if i==0 else 1,
                durationSeconds=read(repo/span["root"]/(plan["runs"][span["endIndex"]]["runId"]+"-orchestration-failure.json"))["durationSeconds"],
                qualityStatus=read(repo/span["root"]/plan["runs"][span["endIndex"]]["runId"]/"summary.json")["qualityStatus"] if i==0 else "unavailable",
                correctness="pass" if i==0 else "unavailable",measurementValidity="invalid" if i==0 else "not_assessed") for i,span in enumerate(policy["retained"])]),
        limits=["Frame Interval is wall-clock, not CPU/GPU time.","coldPrepareMs includes object creation and Canvas flush, not GPU completion.",
            "CPU/GC/memory/UI/GPU metrics unavailable.","Quality-limited costs do not establish a quality-satisfying optimization.","Dirty source candidate: exploratory evidence, not M4 frozen release evidence."])

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    for n in ("plan","runs","gate","build-manifest","policy","output"):parser.add_argument("--"+n,type=Path,required=True)
    parser.add_argument("--repo",type=Path,default=Path.cwd());parser.add_argument("--policy-sha256",required=True);a=parser.parse_args()
    value=verify(a.plan.resolve(),a.runs.absolute(),a.repo.resolve(),a.gate.resolve(),a.build_manifest.resolve(),a.policy.resolve(),a.policy_sha256)
    contracts.write_json_new(a.output,value);print(json.dumps(dict(status=value["status"],runCount=value["runCount"])))
if __name__=="__main__":main()
