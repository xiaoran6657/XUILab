"""Verify a matrix with explicit retained timeouts/deferrals; never label it all-pass."""
from __future__ import annotations
import argparse
import csv
import json
from pathlib import Path
import statistics
import gradient_experiment as contracts
from player_verify import read,need,check_gate,quantile
from player_launch import check_build
from player_resume import inventory,receipt_result,timeout_record


def report(plan_path,root,gate_path,build_path,repo,policy_path):
    plan=contracts.validate_plan(read(plan_path),require_frozen=True);gate=read(gate_path);check_gate(gate,plan,repo)
    plan_hash=contracts.sha256_file(plan_path);build_hash=contracts.sha256_file(build_path);gate_hash=contracts.sha256_file(gate_path);policy=read(policy_path);policy_hash=contracts.sha256_file(policy_path)
    manifest=read(build_path);check_build(build_path,build_path.parent/manifest["player"],plan,repo)
    need(gate["sourceInputs"]==manifest["sourceInputs"],"Gate/build sources mismatch")
    need(policy["planSha256"]==plan_hash and policy["buildManifestSha256"]==build_hash and policy["driverSha256"]==contracts.sha256_file(Path(__file__).with_name("player_resume.py")),"Recovery execution identity mismatch")
    need(policy["protocolSha256"]==contracts.sha256_file(repo/policy["protocolPath"]),"Recovery protocol mismatch")
    need(all(r["parameters"]["preflightSha256"]==gate_hash and r["parameters"]["buildManifestSha256"]==build_hash for r in plan["runs"]),"Plan control hash mismatch")
    blocked=inventory(root,plan,plan_hash);runs=[];groups={};environment=None
    for run in plan["runs"]:
        rid=run["runId"];receipt=root/".receipts"/(rid+".json");failure=root/(rid+"-orchestration-failure.json");deferred=root/(rid+"-deferred.json");directory=root/rid
        row={k:run[k] for k in ("runId","groupId","caseId","runIndex","plannedRepeatCount")}
        group=groups.setdefault(run["groupId"],dict(groupId=run["groupId"],parameters=run["parameters"],expectedRuns=run["plannedRepeatCount"],runs=[]))
        if receipt.exists():
            need(not failure.exists() and not deferred.exists(),"Conflicting receipt status")
            result,detail=receipt_result(root,run,plan,plan_hash,build_hash,repo,gate,policy_hash)
            if environment is None:environment=detail["environment"]
            for key in ("operatingSystem","processorType","processorCount","graphicsDeviceName","graphicsDeviceVersion"):
                need(detail["environment"].get(key) is not None and detail["environment"][key]==environment[key],"Cross-run hardware/OS mismatch")
            summary=read(directory/"summary.json");metrics=read(directory/"gradient-metrics.json")
            row.update(state="completed",correctness="pass",measurementValidity="valid",qualityStatus=result["qualityStatus"],qualityMaxError=detail["quality"]["maxError"],quantizationMaxError=detail["quality"]["quantizationMaxError"],p50=detail["frameP50"],p95=detail["frameP95"],p99=detail["frameP99"],maximum=summary["maxFrameIntervalMs"],overBudgetRatio=summary["overBudgetRatio"],componentDirtyTotal=metrics["totalDirty"],componentRebuildTotal=metrics["totalRebuild"],visibleVertices=run["parameters"]["visibleCount"]*run["parameters"]["expectedVertices"],meanMainThreadNanoseconds=summary["meanMainThreadNanoseconds"],totalGcAllocatedBytes=summary["totalGcAllocatedBytes"],lastSystemUsedMemoryBytes=summary["lastSystemUsedMemoryBytes"])
        elif failure.exists():
            need(not deferred.exists(),"Failure/deferral conflict")
            value=timeout_record(failure,run,plan_hash,root);row.update(state="timeout",correctness="unknown",measurementValidity="invalid",qualityStatus="unavailable",failure=value)
        elif deferred.exists():
            need(not directory.exists() and not (root/".logs"/(rid+".log")).exists(),"Deferred run unexpectedly has output")
            value=read(deferred);source,digest=blocked.get(run["caseId"],(None,None))
            expected=dict(schemaVersion="xuilab.gradient.deferred/v1",runId=rid,planSha256=plan_hash,resumePolicySha256=policy_hash,reason="prior_same_case_timeout",sourceFailureRunId=source,sourceFailureSha256=digest)
            need(source is not None and value==expected,"Unproven or mismatched deferral")
            row.update(state="deferred",correctness="not_run",measurementValidity="not_run",qualityStatus="not_run",sourceFailureRunId=source)
        else:
            need(not directory.exists() and not (root/".logs"/(rid+".log")).exists(),"Unresolved output without receipt")
            row.update(state="not_run",correctness="not_run",measurementValidity="not_run",qualityStatus="not_run")
        runs.append(row);group["runs"].append(row)
    for group in groups.values():
        completed=[r for r in group["runs"] if r["state"]=="completed"]
        group["verifiedRuns"]=len(completed);group["complete"]=len(completed)==group["expectedRuns"]
        group["qualityStatus"]="pass" if completed and all(r["qualityStatus"]=="pass" for r in completed) else "quality_limited" if completed else "unavailable"
        if group["complete"]:
            group["statistics"]={}
            for metric in ("p50","p95","p99","maximum","overBudgetRatio"):
                values=[r[metric] for r in completed];median=statistics.median(values)
                group["statistics"][metric]=dict(median=median,minimum=min(values),maximum=max(values),mad=statistics.median(abs(v-median) for v in values),iqr=quantile(values,.75)-quantile(values,.25))
    counts={state:sum(r["state"]==state for r in runs) for state in ("completed","timeout","deferred","not_run")}
    return dict(schemaVersion="xuilab.gradient.matrix-review/v1",status="complete" if counts["completed"]==len(runs) else "partial",candidateId=plan["candidateId"],buildId=plan["buildId"],sourceRevision=plan["sourceRevision"],dirty=plan["dirty"],planSha256=plan_hash,buildManifestSha256=build_hash,resumePolicySha256=policy_hash,reportToolSha256=contracts.sha256_file(Path(__file__)),counts=counts,completeGroups=sum(g["complete"] for g in groups.values()),environment=environment,groups=list(groups.values()),runs=runs)


def render(result,output):
    import os
    os.environ["MPLCONFIGDIR"]=str(output/".matplotlib-cache")
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    groups=[g for g in result["groups"] if g["complete"]]
    labels=[];values=[];low=[];high=[];colors=[]
    for group in groups:
        p=group["parameters"];stat=group["statistics"]["p95"]
        labels.append(f'{p["layout"]} {p["count"]} / {p["state"]} / {p["direction"][0]} b={p["bias"]:.2f}')
        values.append(stat["median"]);low.append(stat["median"]-stat["minimum"]);high.append(stat["maximum"]-stat["median"])
        colors.append("#cf8c28" if group["qualityStatus"]!="pass" else "#167d99" if p["changedIndices"] else "#586780")
    fig,ax=plt.subplots(figsize=(12,11));ax.barh(range(len(groups)),values,xerr=[low,high],color=colors,capsize=3)
    ax.set_yticks(range(len(groups)),labels);ax.invert_yaxis();ax.set_xscale("log");ax.set_xlabel("Frame interval p95 (ms): median of 5 processes, whiskers = full range")
    ax.axvline(16.6666667,color="#bb4444",ls="--",lw=1);ax.grid(axis="x",alpha=.2)
    for i,value in enumerate(values):ax.text(value*1.05,i,f"{value:.3f}",va="center",fontsize=8)
    ax.set_title("Gradient fixed-32 baseline / verified complete groups only")
    fig.text(.01,.01,f'{result["counts"]["completed"]} completed, {result["counts"]["timeout"]} timeout, {result["counts"]["deferred"]} deferred. Amber: quality_limited. CPU/GC/GPU unavailable where not recorded.',fontsize=8)
    fig.tight_layout(rect=(0,.035,1,1));fig.savefig(output/"frame-p95.svg");fig.savefig(output/"frame-p95.png",dpi=160);plt.close(fig)


def main():
    p=argparse.ArgumentParser(description=__doc__)
    for name in ("plan","runs","gate","build-manifest","policy","output"):p.add_argument("--"+name,type=Path,required=True)
    p.add_argument("--repo",type=Path,default=Path.cwd());p.add_argument("--plot",action="store_true");a=p.parse_args()
    value=report(a.plan.resolve(),a.runs.absolute(),a.gate.resolve(),a.build_manifest.resolve(),a.repo.resolve(),a.policy.resolve())
    contracts._assert_no_reparse_components(a.output,str(a.output));a.output.mkdir(parents=True,exist_ok=False)
    import importlib.metadata as metadata
    value["analysisDependencies"]={name:metadata.version(name) for name in ("numpy","Pillow","packaging","python-dateutil","six")}
    if a.plot:value["analysisDependencies"].update({name:metadata.version(name) for name in ("matplotlib","contourpy","cycler","fonttools","kiwisolver","pyparsing")})
    contracts.write_json_new(a.output/"matrix-review.json",value)
    with (a.output/"runs.csv").open("x",encoding="utf-8",newline="") as f:
        fields=["runId","groupId","runIndex","state","correctness","measurementValidity","qualityStatus","p50","p95","p99","maximum","overBudgetRatio","qualityMaxError","quantizationMaxError","componentDirtyTotal","componentRebuildTotal","visibleVertices"]
        writer=csv.DictWriter(f,fieldnames=fields,extrasaction="ignore");writer.writeheader();writer.writerows(value["runs"])
    if a.plot:render(value,a.output)
    print(json.dumps({k:value[k] for k in ("status","counts","completeGroups")}),flush=True)
    return 0 if value["status"]=="complete" else 1
if __name__=="__main__":raise SystemExit(main())
