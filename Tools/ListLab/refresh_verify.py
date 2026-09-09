"""Read-only List refresh raw evidence verification; no Unity calls."""
from __future__ import annotations
import argparse, hashlib, json, statistics, sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"GradientLab"))
import gradient_experiment as contracts
from player_verify import need,read,rows,number,integer,near,quantile,CORE_COLUMNS
from refresh_plan import validate_plan,ARTIFACTS,CASE,sha
TRACE="sample_index,action_frame,settled_frame,updates,target_mask,state_mask,label_checksum,bind_count,unbind_count,created,destroyed,leased,cached,pending,visible,offset".split(",")
CLASSES={"XUILab.ListLab.Tests.ListViewTests","XUILab.ListLab.Tests.RefreshUpdateTests","XUILab.ListLab.Tests.ListRefreshBenchmarkTests","XUILab.ListLab.Tests.ListBenchmarkTests"}
def check_gate(gate,plan,root):
    need(gate.get("schemaVersion")=="xuilab.list-refresh.preflight/v1" and gate.get("status")=="pass" and gate["candidateId"]==plan["candidateId"],"Preflight identity/status")
    for name,h in gate["sourceInputs"].items():
        need(not Path(name).is_absolute() and ".." not in Path(name).parts,"Unsafe source path")
        contracts._assert_regular_file(root/name,name);need(sha(root/name)==h,"Preflight drift: "+name)
    need({c["kind"] for c in gate["checks"]}=={"functional-runner","core"},"Missing semantic gate")
    for c in gate["checks"]:
        for field,hfield in (("requestPath","requestSha256"),("terminalPath","sha256")):
            need(not Path(c[field]).is_absolute() and ".." not in Path(c[field]).parts,"Unsafe evidence")
            need(sha(root/c[field])==c[hfield],"Gate evidence drift")
        q=read(root/c["requestPath"]);e=read(root/c["terminalPath"]);p=q["parameters"]
        need(q["kind"]=="test" and q["candidate"]==e["candidate"],"Test binding")
        frozen={k:v for k,v in q.items() if k not in ("before","instance","operator")}
        operation=hashlib.sha256(json.dumps(frozen,sort_keys=True,ensure_ascii=False,separators=(",",":")).encode()).hexdigest()
        need(e["operation"]==operation and e["instance"]==q["instance"],"Test operation mismatch")
        d=e["response"]["data"];s=d["result"]["summary"]
        need(e["response"]["success"] is True and d["status"]=="succeeded" and s["resultState"]=="Passed" and s["passed"]==s["total"]>0 and s["failed"]==s["skipped"]==0,"Test did not pass")
        if c["kind"]=="functional-runner":
            need(p["mode"]=="PlayMode" and set(p.get("test_names",[]))==CLASSES and not p.get("group_names") and not p.get("assembly_names"),"Functional selection")
            actual={t["fullName"].rsplit(".",1)[0] for t in d["result"]["results"]}
            need(actual==CLASSES and s["total"]>=22,"Functional/Runner coverage")
            prefixes=("XUILab/Assets/XUILab/ListLab/","XUILab/Assets/XUILab/Benchmarking/Runtime/")
        else:
            need(p["mode"]=="EditMode" and p.get("assembly_names")==["XUILab.Benchmarking.Tests.EditMode"] and not p.get("test_names") and not p.get("group_names"),"Core selection")
            prefixes=("XUILab/Assets/XUILab/Benchmarking/Runtime/","XUILab/Assets/XUILab/Benchmarking/Tests/EditMode/")
        required={n for n in gate["sourceInputs"] if n.startswith(prefixes)}
        need(required and set(c["scopeInputs"])==required,"Incomplete test source scope")
        for n,h in c["scopeInputs"].items():need(q["inputs"].get(n)==h==gate["sourceInputs"][n],"Test input drift: "+n)
        if q["candidate"]!=plan["candidateId"]:need(c.get("reusePolicy")=="unchanged-source-scope" and c.get("sourceCandidate")==q["candidate"],"Undeclared scoped carry-forward")
def action(profile,i):
    count=0 if profile=="idle" or (profile in ("sparse","burst") and i%60) else 3 if profile=="burst" else 9 if profile=="batch" else 1
    return count,sum(1<<((i+n)%9) for n in range(count))
def checksum(mask):
    h=2166136261
    for slot in range(9):
        i=slot+10;label=f"{i+1:05d}    PLAYER {i+1:05d}                        {100000-i}"
        label=label[:-1]+str((mask>>slot)&1)
        for ch in label:h=((h^ord(ch))*16777619)&0xffffffff
    return h
def verify_trace(directory,run,metrics,summary):
    match=CASE.fullmatch(run["caseId"]);need(match is not None,"Case")
    backend,policy,profile=match.groups()
    need(metrics["caseId"]==run["caseId"] and metrics["runId"]==run["runId"],"Metrics identity")
    need((metrics["backend"],metrics["policy"],metrics["profile"],metrics["itemCount"],metrics["visibleCount"])==(backend,policy,profile,1000,9),"Metrics contract")
    core=rows(directory/"samples.csv",CORE_COLUMNS);trace=rows(directory/"refresh-samples.csv",TRACE)
    need(len(core)==len(trace)==run["measureFrames"]==metrics["sampleCount"]==summary["sampleCount"],"Sample count")
    mask=0
    for i in range(run["warmupFrames"]):mask^=action(profile,i)[1]
    need(metrics["initialMask"]==mask,"Warmup terminal content")
    bind=metrics["bindAtStart"];unbind=metrics["unbindAtStart"];elapsed=0;times=[];last_frame=None
    expected_leased=13 if backend=="virtual" else 1000
    for i,(c,t) in enumerate(zip(core,trace)):
        count,targets=action(profile,i);mask^=targets
        delta=count if policy=="target" else 0 if count==0 else 9 if profile=="batch" else 9*count
        bind+=delta;unbind+=delta
        expected=dict(sample_index=i,updates=count,target_mask=targets,state_mask=mask,label_checksum=checksum(mask),
            bind_count=bind,unbind_count=unbind,created=metrics["createdAtStart"],destroyed=metrics["destroyedAtStart"],leased=expected_leased,pending=0,visible=9)
        for k,v in expected.items():need(integer(t[k])==v,"Trace "+k+" at "+str(i))
        need(integer(t["cached"])+expected_leased==integer(t["created"])-integer(t["destroyed"]),"Pool accounting")
        near(t["offset"],492,.05,"Scroll drift")
        frame=integer(c["unity_frame"])
        need(integer(c["sample_index"])==i and frame==integer(t["settled_frame"])==integer(t["action_frame"])+1 and (last_frame is None or frame==last_frame+1),"Action/sample frame alignment")
        last_frame=frame;value=number(c["frame_interval_ms"]);need(value>=0,"Negative frame interval");times.append(value);elapsed+=value
        near(c["elapsed_ms"],elapsed,2e-5,"Elapsed sum")
        for col in CORE_COLUMNS[4:]:
            if c[col]!="":need(integer(c[col])>=0,"Negative optional metric")
    need(metrics["finalBind"]==bind and metrics["finalUnbind"]==unbind and metrics["finalCreated"]==metrics["createdAtStart"] and metrics["finalDestroyed"]==metrics["destroyedAtStart"],"Final counters")
    need(metrics["finalLeased"]==expected_leased and metrics["finalCached"]==integer(trace[-1]["cached"]) and metrics["cleanupUnique"]==0,"Final ownership/cleanup")
    for field,p in (("p50FrameIntervalMs",.5),("p95FrameIntervalMs",.95),("p99FrameIntervalMs",.99)):near(summary[field],quantile(times,p),2e-7,"Percentile")
    near(summary["maxFrameIntervalMs"],max(times),2e-7,"Max")
    near(summary["overBudgetRatio"],sum(x>run["frameBudgetMs"] for x in times)/len(times),2e-7,"Budget ratio")
    for column,field,mode in (("main_thread_ns","meanMainThreadNanoseconds","mean"),("gc_allocated_bytes","totalGcAllocatedBytes","sum"),("system_used_memory_bytes","lastSystemUsedMemoryBytes","last")):
        values=[integer(r[column]) for r in core if r[column]!=""]
        if not values:need(summary[field] is None,"Unavailable metric was replaced")
        else:
            need(len(values)==len(core),"Partial optional recorder availability")
            target=statistics.mean(values) if mode=="mean" else sum(values) if mode=="sum" else values[-1]
            near(summary[field],target,max(1e-7,abs(target)*1e-12),"Optional summary")
    return dict(frameP50=quantile(times,.5),frameP95=quantile(times,.95),frameP99=quantile(times,.99),frameMax=max(times),overBudgetRatio=summary["overBudgetRatio"],bindDelta=bind-metrics["bindAtStart"],coldBuildMs=metrics["coldBuildMs"],totalGcAllocatedBytes=summary["totalGcAllocatedBytes"])
def verify_run(directory,plan,run,plan_hash,repo,gate):
    need({p.name for p in directory.iterdir()}==set(ARTIFACTS),"Raw artifact set")
    cfg=read(directory/"config.json");env=read(directory/"environment.json");ident=read(directory/"identity.json");summary=read(directory/"summary.json")
    binding=read(directory/"refresh-binding.json");metrics=read(directory/"refresh-metrics.json");p=run["parameters"]
    need(sha(directory/"config.json")==ident["configSha256"].lower(),"Core config hash")
    for k in ("runId","caseId","runIndex","plannedRepeatCount","warmupFrames","measureFrames","sampleCapacity","frameBudgetMs"):need(cfg[k]==run[k],"Config "+k)
    for k in ("candidateId","buildId","sourceRevision","dirty"):need(cfg[k]==plan[k] and ident[k]==plan[k],"Identity "+k)
    need(cfg["faultPlan"]["mode"]=="none" and cfg["tier"]=="windows-development-player" and cfg["caseVersion"]=="1" and cfg["seriesId"]==plan["planId"],"Core protocol")
    need(cfg["targetFrameRate"]==p["targetFrameRate"] and cfg["vSyncCount"]==0,"Config pacing")
    need(cfg["protocolVersion"]==plan["protocolVersion"]=="xuilab.benchmark.protocol/v1" and cfg["seed"]==1337 and cfg["readyTimeoutFrames"]==300 and cfg["cpuIterationsPerFrame"]==cfg["allocationBytesPerFrame"]==0,"Core workload constants")
    need(cfg["enableProfilerRecorders"] is True and cfg["requiredMetrics"]==["Frame Interval"] and cfg["optionalMetrics"]==["Main Thread","GC Allocated In Frame","System Used Memory"] and cfg["quitWhenDone"] is True,"Metric/quit policy")
    need(sha(repo/"Docs/Experiments/LIST_REFRESH_PROTOCOL-r1.md")==plan["contractSha256"],"Protocol SHA drift")
    need(ident["runId"]==run["runId"] and ident["schemaVersion"]=="xuilab.benchmark.identity/v1" and ident["runnerVersion"]=="1","Core identity schema/run")
    expected=dict(unityVersion="2022.3.45f1c1",screenWidth=960,screenHeight=540,graphicsDeviceType="Direct3D11",qualityLevel="High Fidelity",scriptingBackend="mono",buildType="development",targetFrameRate=p["targetFrameRate"],vSyncCount=0,tier="windows-development-player")
    for k,v in expected.items():need(env[k]==v,"Environment "+k)
    need(binding["schemaVersion"]=="xuilab.list-refresh.binding/v1" and binding["run"]==run and binding["planSha256"]==plan_hash and binding["planId"]==plan["planId"],"Run binding")
    need(binding["contractId"]==plan["contractId"] and binding["contractSha256"]==plan["contractSha256"] and binding["preflight"]==gate and binding["buildManifestSha256"]==p["buildManifestSha256"],"Control binding")
    need(binding["startFocus"] is True and binding["observedFocusAtExport"] is True and binding["batchMode"] is False and binding["colorSpace"]=="Linear","Focus/color/batch")
    need(summary["runId"]==run["runId"] and summary["state"]=="completed" and summary["correctness"]==metrics["correctness"]=="pass" and summary["measurementValidity"]=="valid","Result not accepted")
    need(summary["exportSucceeded"] is True and summary["cleanupSucceeded"] is True and summary["processSuccess"] is True and type(summary["exitCode"]) is int and summary["exitCode"]==0,"Terminal process")
    events=(directory/"events.log").read_text(encoding="utf-8")
    need("focus_lost" not in events and "application_paused" not in events,"Focus/pause event")
    details=verify_trace(directory,run,metrics,summary);details.update(runId=run["runId"],environment=env)
    return dict(state="completed",correctness="pass",measurementValidity="valid"),details
def verify(plan_path,root,repo,gate_path,build_path):
    plan=validate_plan(read(plan_path));gate=read(gate_path);check_gate(gate,plan,repo)
    from refresh_launch import check_build
    build=read(build_path);check_build(build_path,build_path.parent/build["player"],plan,repo)
    need(gate["sourceInputs"]==build["sourceInputs"],"Gate/build source scope")
    ph=sha(plan_path);bh=sha(build_path);gh=sha(gate_path);details=[];failures=[]
    for run in plan["runs"]:
        try:
            need(run["parameters"]["buildManifestSha256"]==bh and run["parameters"]["preflightSha256"]==gh,"Plan control hashes")
            _,d=verify_run(root/run["runId"],plan,run,ph,repo,gate);receipt=read(root/".receipts"/(run["runId"]+".json"))
            need(receipt["runId"]==run["runId"] and receipt["exitCode"]==0 and receipt["planSha256"]==ph and receipt["buildManifestSha256"]==bh,"Receipt")
            need(receipt["files"]=={n:sha(root/run["runId"]/n) for n in ARTIFACTS},"Receipt raw hash drift")
            details.append(d)
        except (ValueError,KeyError,TypeError,OSError) as e:failures.append(dict(runId=run["runId"],reason=str(e)))
    if details:
        for d in details:
            for k in ("operatingSystem","processorType","processorCount","graphicsDeviceName","graphicsDeviceVersion"):
                need(d["environment"][k]==details[0]["environment"][k],"Cross-run machine drift")
    comparisons=[]
    if not failures:
        byid={d["runId"]:d for d in details}
        for group in sorted({r["groupId"] for r in plan["runs"]}):
            members=[r for r in plan["runs"] if r["groupId"]==group]
            a=[byid[r["runId"]]["frameP95"] for r in sorted(members,key=lambda x:x["runIndex"]) if r["variant"]=="window"]
            b=[byid[r["runId"]]["frameP95"] for r in sorted(members,key=lambda x:x["runIndex"]) if r["variant"]=="target"]
            threshold=max(.05*statistics.median(a),.5*max(max(a)-min(a),max(b)-min(b)))
            delta=statistics.median(b)-statistics.median(a)
            decision="improved" if len(a)==5 and sum(y<x for x,y in zip(a,b))>=4 and delta < -threshold else "regressed" if len(a)==5 and sum(y>x for x,y in zip(a,b))>=4 and delta>threshold else "inconclusive"
            comparisons.append(dict(group=group,windowP95=a,targetP95=b,medianDifference=delta,threshold=threshold,result=decision))
    return dict(schemaVersion="xuilab.list-refresh.verification/v1",status="pass" if not failures else "not_ready",planSha256=ph,details=details,failures=failures,comparisons=comparisons)
def main():
    p=argparse.ArgumentParser()
    for n in ("plan","runs","gate","build-manifest","output"):p.add_argument("--"+n,type=Path,required=True)
    p.add_argument("--repo",type=Path,default=Path.cwd());a=p.parse_args();v=verify(a.plan,a.runs,a.repo,a.gate,a.build_manifest)
    with a.output.open("x",encoding="utf-8") as f:json.dump(v,f,indent=2);f.write("\n")
    print(json.dumps(dict(status=v["status"],runs=len(v["details"]),failures=v["failures"])));return 0 if v["status"]=="pass" else 1
if __name__=="__main__":raise SystemExit(main())
