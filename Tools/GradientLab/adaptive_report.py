"""Verify G2 owned-process evidence and compare five paired independent runs."""
import argparse,json
from pathlib import Path
import gradient_experiment as contracts
from adaptive_plan import validate_adaptive,SCENARIOS
from adaptive_verify import read,need,check_gate,verify_run,quantile
from adaptive_launch import check_build,check_inventory,verify_receipt
from adaptive_policy import validate_policy
from subdivision_report import distribution,compare

def verify(plan_path,run_root,repo,gate_path,build_path,policy_path,policy_hash):
    plan=validate_adaptive(read(plan_path));gate=read(gate_path);check_gate(gate,plan,repo)
    need(contracts.sha256_file(policy_path)==policy_hash,"Dispatch policy SHA")
    policy=validate_policy(policy_path,plan,plan_path,gate_path,build_path,repo,run_root)
    ph=contracts.sha256_file(plan_path);gh=contracts.sha256_file(gate_path);bh=contracts.sha256_file(build_path)
    manifest=read(build_path);player=(build_path.parent/manifest["player"]).resolve();check_build(build_path,player,plan,repo)
    need(gate["sourceInputs"]==manifest["sourceInputs"],"Gate/build inputs")
    contracts._assert_no_reparse_components(run_root,str(run_root));need(run_root.is_dir(),"Run root missing");check_inventory(run_root,plan)
    ids={r["runId"] for r in plan["runs"]}
    need({p.name for p in run_root.iterdir()}==ids|{".receipts",".logs",".launches"},"Incomplete exact run tree")
    for folder,suffix in ((".receipts",".json"),(".logs",".log"),(".launches",".json")):
        need({p.name for p in (run_root/folder).iterdir()}=={name+suffix for name in ids},"Incomplete sidecar tree")
    rows=[];environment=None
    for run in plan["runs"]:
        receipt=verify_receipt(run_root,run,ph,bh,player,manifest)
        need(receipt.get("dispatchPolicySha256")==policy_hash,"Receipt dispatch policy")
        result,detail=verify_run(run_root/run["runId"],plan,run,ph,repo,gate)
        need(receipt.get("qualityStatus")==result["qualityStatus"],"Receipt quality")
        env=detail["environment"]
        if environment is None:environment=env
        fields=("operatingSystem","processorType","processorCount","graphicsDeviceName","graphicsDeviceVersion")
        need(all(env.get(key)==environment.get(key) for key in fields),"Cross-run hardware/OS drift")
        values=result["metrics"]["frameIntervalMs"];cost=result["metrics"]["costMetrics"];quality=detail["quality"];selection=detail["selection"]
        rows.append(dict(runId=run["runId"],scenario=run["parameters"]["scenario"],variant=run["variant"],repeat=run["runIndex"],correctness=result["correctness"],measurementValidity=result["measurementValidity"],qualityStatus=result["qualityStatus"],p50=quantile(values,.5),p95=quantile(values,.95),p99=quantile(values,.99),maximum=max(values),overBudgetRatio=sum(v>run["frameBudgetMs"] for v in values)/len(values),coldPrepareMs=detail["coldPrepareMs"],qualityMaxError=quality["maxError"],qualityRmsError=quality["rmsError"],quantizationMaxError=quality["quantizationMaxError"],componentDirtyTotal=cost["componentDirtyTotal"],componentRebuildTotal=cost["componentRebuildTotal"],maximumVisibleVertices=cost["visibleVertices"],**selection))
    groups=[];comparisons=[];pilot=len(rows)==4
    metrics=("p50","p95","p99","maximum","overBudgetRatio","coldPrepareMs","qualityMaxError","qualityRmsError","quantizationMaxError","selectionMs","coldSelectionMs","minSegments","maxSegments","maximumVisibleVertices")
    for scenario,*_ in SCENARIOS:
        subset=[r for r in rows if r["scenario"]==scenario]
        if not subset:continue
        for variant in ("fixed32","adaptive64"):
            runs=sorted([r for r in subset if r["variant"]==variant],key=lambda r:r["repeat"])
            need([r["repeat"] for r in runs]==list(range(1,2 if pilot else 6)),"Group repeat coverage")
            groups.append(dict(scenario=scenario,variant=variant,runs=runs,qualityStatus="pass" if all(r["qualityStatus"]=="pass" for r in runs) else "quality_limited",statistics={metric:distribution([r[metric] for r in runs]) for metric in metrics}))
        if not pilot:
            baseline=[r["p95"] for r in sorted(subset,key=lambda r:r["repeat"]) if r["variant"]=="fixed32"]
            variant=[r["p95"] for r in sorted(subset,key=lambda r:r["repeat"]) if r["variant"]=="adaptive64"]
            comparisons.append(dict(scenario=scenario,**compare(baseline,variant)))
    return dict(schemaVersion="xuilab.gradient.adaptive-report/v1",status="pass",correctness="pass",measurementValidity="valid",candidateId=plan["candidateId"],buildId=plan["buildId"],sourceRevision=plan["sourceRevision"],dirty=plan["dirty"],planSha256=ph,buildManifestSha256=bh,preflightSha256=gh,dispatchPolicySha256=policy_hash,reportToolSha256=contracts.sha256_file(Path(__file__)),pilot=pilot,runCount=len(rows),environment=environment,runs=rows,groups=groups,comparisons=comparisons,limits=["Frame Interval is wall-clock, not CPU/GPU time.","Selection ticks include cache check and instrumentation; cold/steady separated.","coldPrepare includes object creation and Canvas flush, not GPU completion.","CPU/GC/memory/UI/GPU unavailable.","qualityRmsError is RMS at the worst-max-error bias.","Quality-limited costs do not establish a quality-satisfying optimization."])

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    for name in ("plan","runs","gate","build-manifest","policy","output"):parser.add_argument("--"+name,type=Path,required=True)
    parser.add_argument("--repo",type=Path,default=Path.cwd());parser.add_argument("--policy-sha256",required=True);args=parser.parse_args()
    result=verify(args.plan.resolve(),args.runs.absolute(),args.repo.resolve(),args.gate.resolve(),args.build_manifest.resolve(),args.policy.resolve(),args.policy_sha256)
    contracts.write_json_new(args.output,result);print(json.dumps(dict(status=result["status"],runCount=result["runCount"],comparisons=result["comparisons"])))
if __name__=="__main__":main()
