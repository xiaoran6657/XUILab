"""Verify fixed-subdivision v2 process evidence and report paired quality/cost."""
import argparse,csv,json,statistics
from pathlib import Path
import gradient_experiment as contracts
from subdivision_plan import validate_subdivision,SCENARIOS
from subdivision_launch import check_build,check_inventory,verify_receipt
from player_verify import read,need,check_gate,verify_run,quantile

def distribution(values):
    med=statistics.median(values)
    return dict(median=med,minimum=min(values),maximum=max(values),range=max(values)-min(values),
                mad=statistics.median(abs(x-med) for x in values))

def compare(baseline,variant):
    need(len(baseline)==len(variant)==5,"Five paired processes required")
    delta=statistics.median(variant)-statistics.median(baseline)
    threshold=max(.05*statistics.median(baseline),.5*max(max(baseline)-min(baseline),max(variant)-min(variant)))
    signs=[v-b for b,v in zip(baseline,variant)]
    verdict="inconclusive"
    if delta < -threshold and sum(x<0 for x in signs)>=4:verdict="improved"
    if delta > threshold and sum(x>0 for x in signs)>=4:verdict="regressed"
    return dict(result=verdict,baselineP95=baseline,variantP95=variant,pairedDeltas=signs,
                medianDifference=delta,thresholdMs=threshold,relativePercent=100*delta/statistics.median(baseline))

def verify(plan_path,run_root,repo,gate_path,build_path,recovery_policy=None,recovery_policy_sha256=None):
    plan=validate_subdivision(read(plan_path));gate=read(gate_path);check_gate(gate,plan,repo)
    ph=contracts.sha256_file(plan_path);gh=contracts.sha256_file(gate_path);bh=contracts.sha256_file(build_path)
    manifest=read(build_path);player=(build_path.parent/manifest["player"]).resolve()
    check_build(build_path,player,plan,repo)
    need(gate["sourceInputs"]==manifest["sourceInputs"],"Gate/build input mismatch")
    need(all(r["parameters"]["preflightSha256"]==gh and r["parameters"]["buildManifestSha256"]==bh for r in plan["runs"]),"Control hashes mismatch")
    contracts._assert_no_reparse_components(run_root,str(run_root));need(run_root.is_dir(),"Missing run root")
    check_inventory(run_root,plan)
    recovery=None;original=None
    if recovery_policy is not None:
        need(contracts.sha256_file(recovery_policy)==recovery_policy_sha256,"Report recovery policy hash mismatch")
        from subdivision_recovery import validate_policy
        from subdivision_continue import verify_receipt as continued_receipt
        recovery=validate_policy(recovery_policy,plan,plan_path,gate_path,build_path,repo,run_root)
        original=repo/recovery["originalRoot"]
    expected=set(recovery["selectedRunIds"]) if recovery else {r["runId"] for r in plan["runs"]}
    need({p.name for p in run_root.iterdir()}==expected|{".receipts",".logs",".launches"},"Incomplete exact run tree")
    for folder,suffix in ((".receipts",".json"),(".logs",".log"),(".launches",".json")):
        need({p.name for p in (run_root/folder).iterdir()}=={r+suffix for r in expected},"Incomplete evidence tree")
    rows=[];environment=None
    for ordinal,run in enumerate(plan["runs"]):
        source_root=original if recovery and ordinal<recovery["resumeIndex"] else run_root
        receipt_check=continued_receipt if recovery and source_root==run_root else verify_receipt
        receipt=receipt_check(source_root,run,ph,bh,player,manifest)
        if recovery and source_root==run_root:need(receipt.get("recoveryPolicySha256")==recovery_policy_sha256,"Receipt recovery policy mismatch")
        result,detail=verify_run(source_root/run["runId"],plan,run,ph,repo,gate)
        need(receipt.get("qualityStatus")==result["qualityStatus"],"Receipt quality status mismatch")
        env=detail["environment"]
        fields=("operatingSystem","processorType","processorCount","graphicsDeviceName","graphicsDeviceVersion")
        if environment is None:environment=env
        need(all(env.get(k)==environment.get(k) for k in fields),"Cross-run environment drift")
        values=result["metrics"]["frameIntervalMs"];p=run["parameters"];quality=detail["quality"]
        rows.append(dict(runId=run["runId"],scenario=p["scenario"],segments=p["segments"],repeat=run["runIndex"],
            correctness=result["correctness"],measurementValidity=result["measurementValidity"],qualityStatus=result["qualityStatus"],
            p50=quantile(values,.5),p95=quantile(values,.95),p99=quantile(values,.99),maximum=max(values),
            overBudgetRatio=sum(v>run["frameBudgetMs"] for v in values)/len(values),coldPrepareMs=detail["coldPrepareMs"],
            qualityMaxError=quality["maxError"],qualityRmsError=quality["rmsError"],quantizationMaxError=quality["quantizationMaxError"],
            componentDirtyTotal=result["metrics"]["costMetrics"]["componentDirtyTotal"],
            componentRebuildTotal=result["metrics"]["costMetrics"]["componentRebuildTotal"],
            visibleVertices=result["metrics"]["costMetrics"]["visibleVertices"]))
    groups=[];comparisons=[];pilot=len(rows)==4
    for scenario,*_ in SCENARIOS:
        subset=[r for r in rows if r["scenario"]==scenario]
        if not subset:continue
        for seg in (8,16,32,64):
            runs=sorted([r for r in subset if r["segments"]==seg],key=lambda r:r["repeat"])
            if not runs:continue
            need(len(runs)==(1 if pilot else 5),"Group repeat completeness")
            groups.append(dict(scenario=scenario,segments=seg,runs=runs,
                qualityStatus="pass" if all(r["qualityStatus"]=="pass" for r in runs) else "quality_limited",
                statistics={metric:distribution([r[metric] for r in runs]) for metric in ("p50","p95","p99","maximum","overBudgetRatio","coldPrepareMs","qualityMaxError","qualityRmsError","quantizationMaxError")}))
        if not pilot:
            baseline=[r["p95"] for r in sorted(subset,key=lambda r:r["repeat"]) if r["segments"]==32]
            for seg in (8,16,64):
                variant=[r["p95"] for r in sorted(subset,key=lambda r:r["repeat"]) if r["segments"]==seg]
                comparisons.append(dict(scenario=scenario,segments=seg,**compare(baseline,variant)))
    return dict(schemaVersion="xuilab.gradient.subdivision-report/v1",status="pass",correctness="pass",measurementValidity="valid",
        candidateId=plan["candidateId"],buildId=plan["buildId"],sourceRevision=plan["sourceRevision"],dirty=plan["dirty"],
        planSha256=ph,buildManifestSha256=bh,preflightSha256=gh,reportToolSha256=contracts.sha256_file(Path(__file__)),
        pilot=pilot,runCount=len(rows),environment=environment,runs=rows,groups=groups,comparisons=comparisons,
        recovery=None if recovery is None else dict(policySha256=contracts.sha256_file(recovery_policy),originalRoot=recovery["originalRoot"],continuedRoot=recovery["continuedRoot"],retainedValidPrefix=recovery["resumeIndex"],excludedInvalidRunId=recovery["failedRunId"],excludedReason="pre-measure focus loss",invalidAttemptRetained=True,excludedAttempt=dict(runId=recovery["failedRunId"],root=recovery["originalRoot"],attempt="original",candidateId=plan["candidateId"],buildId=plan["buildId"],correctness="pass",measurementValidity="invalid",qualityStatus=read(original/recovery["failedRunId"]/"summary.json")["qualityStatus"],exitCode=3,failureReason="Application focus was lost before measurement")),
        limits=["Frame Interval is wall-clock, not CPU/GPU time.","coldPrepareMs includes object creation and Canvas flush, not GPU completion.",
                "CPU/GC/memory/UI/GPU metrics unavailable.","quality_limited costs remain valid but do not establish a quality-satisfying optimization."])

def main():
    p=argparse.ArgumentParser(description=__doc__)
    for n in ("plan","runs","gate","build-manifest","output"):p.add_argument("--"+n,type=Path,required=True)
    p.add_argument("--repo",type=Path,default=Path.cwd());p.add_argument("--recovery-policy",type=Path);p.add_argument("--recovery-policy-sha256");a=p.parse_args()
    value=verify(a.plan.resolve(),a.runs.absolute(),a.repo.resolve(),a.gate.resolve(),a.build_manifest.resolve(),a.recovery_policy.resolve() if a.recovery_policy else None,a.recovery_policy_sha256)
    contracts.write_json_new(a.output,value)
    print(json.dumps(dict(status=value["status"],runCount=value["runCount"],comparisons=[dict(scenario=c["scenario"],segments=c["segments"],result=c["result"]) for c in value["comparisons"]])))
if __name__=="__main__":main()

