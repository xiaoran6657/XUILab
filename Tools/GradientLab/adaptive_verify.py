"""G2 raw verification. Shares parsers; owns adaptive semantics and full gate coverage."""
import math
import hashlib
import json
from pathlib import Path
import gradient_experiment as contracts
import gradient_recovery as recovery
from player_verify import (EvidenceError,need,number,integer,rows,read,near,quantile,CORE_COLUMNS,TRACE_COLUMNS,SCAN_COLUMNS,verify_quality as fixed_quality,verify_mesh as fixed_mesh)
from adaptive_plan import validate_adaptive
from adaptive_math import select

SELECTION_COLUMNS=["sample_index","selection_calls","cache_hits","selection_ticks","min_segments","max_segments","quality_limited","estimated_error"]

def safe_relative(root,name):
    from pathlib import PureWindowsPath
    need(isinstance(name,str) and name and not PureWindowsPath(name).is_absolute() and not PureWindowsPath(name).drive and "\\" not in name and ":" not in name and ".." not in Path(name).parts and not Path(name).is_absolute(),"Unsafe repository path")
    path=root/name;contracts._assert_regular_file(path,name);return path

def check_gate(gate, plan, root):
    need(gate.get("schemaVersion")=="xuilab.gradient.preflight/v1" and gate.get("status")=="pass","Preflight status/schema")
    need(gate.get("candidateId")==plan["candidateId"],"Preflight candidate mismatch")
    need(isinstance(gate.get("sourceInputs"),dict) and gate["sourceInputs"],"Preflight source inputs absent")
    for name,digest in gate["sourceInputs"].items():
        path=safe_relative(root,name)
        need(not Path(name).is_absolute() and ".." not in Path(name).parts,"Unsafe preflight path")
        contracts._assert_regular_file(path,name)
        need(contracts.sha256_file(path)==digest,f"Preflight input drift: {name}")
    prefixes={"gradient-math-mesh":("XUILab/Assets/XUILab/GradientLab/Runtime/","XUILab/Assets/XUILab/GradientLab/Tests/EditMode/"),
        "gradient-lifecycle":("XUILab/Assets/XUILab/GradientLab/Runtime/","XUILab/Assets/XUILab/GradientLab/Tests/PlayMode/"),
        "gradient-pixel":("XUILab/Assets/XUILab/GradientLab/Runtime/","XUILab/Assets/XUILab/GradientLab/Presentation/","XUILab/Assets/XUILab/GradientLab/Diagnostics/","XUILab/Assets/XUILab/GradientLab/Resources/","XUILab/Assets/XUILab/GradientLab/Tests/Quality/"),
        "gradient-runner":("XUILab/Assets/XUILab/Benchmarking/Runtime/","XUILab/Assets/XUILab/GradientLab/Runtime/","XUILab/Assets/XUILab/GradientLab/Presentation/","XUILab/Assets/XUILab/GradientLab/BenchmarkIntegration/","XUILab/Assets/XUILab/GradientLab/Tests/Benchmarking/")}
    assemblies={"gradient-math-mesh":"XUILab.GradientLab.Tests.EditMode","gradient-lifecycle":"XUILab.GradientLab.Tests.PlayMode","gradient-pixel":"XUILab.GradientLab.Tests.Quality","gradient-runner":"XUILab.GradientLab.Tests.Benchmarking"}
    prefixes["core"]=("XUILab/Assets/XUILab/Benchmarking/Runtime/","XUILab/Assets/XUILab/Benchmarking/Tests/EditMode/")
    assemblies["core"]="XUILab.Benchmarking.Tests.EditMode"
    checks=gate.get("checks",[])
    if plan.get("experimentId")=="gradient-adaptive-v1":
        need(len(checks)==5 and {c.get("kind") for c in checks}==set(assemblies),"Adaptive requires exactly five full semantic gates")
    need({c.get("kind") for c in checks}>={"gradient-math-mesh","gradient-lifecycle","gradient-pixel","gradient-runner"},"Required semantic gates missing")
    for check in checks:
        path=safe_relative(root,check["terminalPath"])
        need(not Path(check["terminalPath"]).is_absolute() and ".." not in Path(check["terminalPath"]).parts,"Unsafe gate evidence path")
        need(contracts.sha256_file(path)==check["sha256"],"Gate evidence drift")
        request_path=Path(check["requestPath"])
        need(not request_path.is_absolute() and ".." not in request_path.parts,"Unsafe request path")
        request_path=safe_relative(root,check["requestPath"]);need(contracts.sha256_file(request_path)==check["requestSha256"],"Gate request drift")
        request=read(request_path)
        need(assemblies[check["kind"]] in request["parameters"].get("assembly_names",[]) and not request["parameters"].get("test_names") and not request["parameters"].get("group_names"),"Semantic gate must cover its full test assembly")
        required={n for n in gate["sourceInputs"] if n.startswith(prefixes[check["kind"]])}
        need(required and set(check["scopeInputs"])==required,"Gate source scope incomplete")
        for name,digest in check["scopeInputs"].items():need(request["inputs"].get(name)==digest==gate["sourceInputs"][name],f"Gate test source mismatch: {name}")
        doc=read(path);need(doc["candidate"]==request["candidate"] and request["kind"]=="test","Gate request/terminal candidate mismatch")
        frozen={k:v for k,v in request.items() if k not in ("before","instance","operator")}
        operation=hashlib.sha256(json.dumps(frozen,sort_keys=True,ensure_ascii=False,separators=(",",":")).encode("utf-8")).hexdigest()
        need(doc["operation"]==operation and doc["instance"]==request["instance"] and doc["response"]["success"] is True and doc["response"]["data"]["status"]=="succeeded","Gate operation binding/status mismatch")
        if request["candidate"]!=plan["candidateId"]:
            need(check.get("reusePolicy")=="unchanged-source-scope" and check.get("sourceCandidate")==request["candidate"],"Cross-candidate gate requires explicit scoped carry-forward")
        summary=doc["response"]["data"]["result"]["summary"]
        need(summary["resultState"]=="Passed" and summary["total"]>0 and summary["total"]==summary["passed"] and summary["failed"]==summary["skipped"]==0,"Gate test not passed")
        if plan.get("experimentId")=="gradient-adaptive-v1":
            import re
            from collections import Counter
            tests=doc["response"]["data"]["result"]["results"]
            need(len(tests)==summary["total"] and all(t["state"]=="Passed" for t in tests),"Truncated or nonpassed gate detail")
            selection=request["parameters"]
            need(selection.get("assembly_names")==[assemblies[check["kind"]]] and not selection.get("category_names"),"Gate must select exactly one unfiltered assembly")
            need(selection["mode"]==("EditMode" if check["kind"] in ("core","gradient-math-mesh") else "PlayMode"),"Gate mode mismatch")
            actual=[t["fullName"] for t in tests];duplicates={n:c for n,c in Counter(actual).items() if c>1}
            collision="XUILab.Benchmarking.Tests.EditMode.BenchmarkRunnerTests.ProtocolV1_RejectsMissingOrChangedRequiredMetrics(System.String[])"
            need(duplicates==({collision:3} if check["kind"]=="core" else {}),"Unexpected duplicate gate detail")
            declared=set();case_count=0
            for name in required:
                if "/Tests/" not in name or not name.endswith(".cs"):continue
                source=(root/name).read_text(encoding="utf-8-sig")
                namespace=re.search(r"namespace\s+([\w.]+)",source);cls=re.search(r"class\s+(\w+)",source)
                if not namespace or not cls:continue
                case_count+=len(re.findall(r"\[(?:Test|UnityTest|TestCase)(?:\(|\])",source))
                for method in re.finditer(r"\[(?:Test|UnityTest|TestCase(?:Source)?)(?:\([^\]]*\))?\]\s*(?:\[[^\]]+\]\s*)*public\s+(?:void|IEnumerator)\s+(\w+)\s*\(",source):declared.add(namespace.group(1)+"."+cls.group(1)+"."+method.group(1))
            need({n.split("(")[0] for n in actual}==declared,"Gate missing or unknown source method")
            need(len(tests)==(32 if check["kind"]=="core" else case_count),"Gate test case coverage mismatch")


def verify_run(directory,plan,run,plan_hash,repo_root,gate):
    p=run["parameters"]
    validate_adaptive(plan)
    need(contracts.sha256_file(repo_root/"Docs/Experiments/GRADIENT_ADAPTIVE_PROTOCOL-r1.md")==p["experimentProtocolSha256"],"Adaptive protocol hash")
    contracts._assert_no_reparse_components(directory,str(directory))
    need(directory.is_dir(),"Run directory missing")
    need({x.name for x in directory.iterdir()}==set(plan["artifacts"]),"Run artifact set mismatch")
    identity=read(directory/"identity.json");error=recovery._check_identity(identity,plan,run,directory);need(error is None,error)
    need(identity.get("planSha256")==plan_hash and identity.get("dirty")==plan["dirty"],"Identity plan hash/dirty mismatch")
    cfg=read(directory/"config.json");env=read(directory/"environment.json");summary=read(directory/"summary.json");binding=read(directory/"gradient-binding.json");metrics=read(directory/"gradient-metrics.json")
    need(cfg.get("schemaVersion")=="xuilab.benchmark.config/v1" and env.get("schemaVersion")=="xuilab.benchmark.environment/v1","Core schema mismatch")
    need(cfg.get("enableProfilerRecorders") is True and cfg.get("requiredMetrics")==["Frame Interval"] and cfg.get("optionalMetrics")==["Main Thread","GC Allocated In Frame","System Used Memory"],"Metric configuration mismatch")
    need(type(cfg.get("dirty")) is bool and all(type(cfg.get(k)) is int for k in ("runIndex","plannedRepeatCount","warmupFrames","measureFrames","sampleCapacity","targetFrameRate","vSyncCount")),"Core config numeric/boolean types")
    need(cfg.get("cpuIterationsPerFrame")==0 and cfg.get("allocationBytesPerFrame")==0 and cfg.get("quitWhenDone") is True,"Unexpected synthetic load or nonquitting formal config")
    need(contracts.sha256_file(directory/"config.json")==identity["configSha256"].lower(),"Core configuration hash mismatch")
    for k in ("runId","caseId","runIndex","plannedRepeatCount","warmupFrames","measureFrames","sampleCapacity","frameBudgetMs"):need(cfg[k]==run[k],f"Config {k} mismatch")
    for k in ("candidateId","buildId","sourceRevision","dirty"):need(cfg[k]==plan[k],f"Config {k} mismatch")
    need(cfg["faultPlan"]["mode"]=="none" and cfg["tier"]=="windows-development-player","Formal config fault/tier")
    need(cfg["targetFrameRate"]==p["targetFrameRate"] and cfg["vSyncCount"]==p["vSyncCount"],"Config pacing")
    expected_env={"unityVersion":"2022.3.45f1c1","screenWidth":p["screenWidth"],"screenHeight":p["screenHeight"],"graphicsDeviceType":p["graphicsApi"],"qualityLevel":p["qualityLevel"],"scriptingBackend":"mono","buildType":"development","targetFrameRate":p["targetFrameRate"],"vSyncCount":p["vSyncCount"],"tier":"windows-development-player"}
    for k,v in expected_env.items():need(env[k]==v,f"Player environment {k} mismatch")
    need(binding["run"]==run and binding["planSha256"]==plan_hash and binding["colorSpace"]=="Linear","Observed binding mismatch")
    need(binding["preflight"]==gate,"Embedded preflight mismatch")
    need(type(binding.get("startFocus")) is bool and type(binding.get("observedFocusAtExport")) is bool,"Missing/invalid focus observations")
    if not binding["startFocus"]:need(summary["measurementValidity"]!="valid","Startup focus loss cannot become valid")
    need(identity.get("buildManifestSha256")==binding.get("buildManifestSha256")==p.get("buildManifestSha256"),"Identity/binding/build manifest hash mismatch")
    need(summary["runId"]==run["runId"] and summary["planId"]==plan["planId"] and summary["contractSha256"]==plan["contractSha256"],"Summary binding")
    need(summary["evidenceKind"]==plan["evidenceKind"] and summary["contractId"]==plan["contractId"],"Summary contract/evidence kind")
    need(cfg["seriesId"]==plan["planId"] and cfg["protocolVersion"]==plan["protocolVersion"] and cfg["caseVersion"]=="1","Config series/protocol/case version")
    need(metrics["runId"]==run["runId"] and metrics["caseId"]==run["caseId"],"Gradient metric identity")
    core=rows(directory/"samples.csv",CORE_COLUMNS);trace=rows(directory/"gradient-samples.csv",TRACE_COLUMNS)
    need(len(core)==len(trace)==run["measureFrames"],"Missing/extra samples")
    frame_times=[];elapsed=0;last_frame=None;dirty_total=rebuild_total=0
    changed=len(p["changedIndices"])
    for i,(c,t) in enumerate(zip(core,trace)):
        need(integer(c["sample_index"])==integer(t["sample_index"])==i,"Noncontinuous sample index")
        frame=integer(c["unity_frame"]);action=integer(t["action_frame"]);settled=integer(t["settled_frame"])
        need(frame==settled==action+1 and (last_frame is None or frame==last_frame+1),"Action/core frame mismatch")
        last_frame=frame;dt=number(c["frame_interval_ms"]);need(dt>=0,"Negative frame interval");frame_times.append(dt);elapsed+=dt
        near(c["elapsed_ms"],elapsed,2e-5,"Cumulative frame time mismatch")
        expected_dirty=changed if changed and i%300 else 0
        need(integer(t["dirty_delta"])==integer(t["rebuild_delta"])==expected_dirty,"Unexpected component work")
        dirty_total+=integer(t["dirty_delta"]);rebuild_total+=integer(t["rebuild_delta"])
        for k,v in {"visible":p["visibleCount"],"culled":p["count"]-p["visibleCount"],"changed_count":changed}.items():need(integer(t[k])==v,f"Trace {k} mismatch")
        if p["effectMode"]=="fixed":
            for k,v in {"vertices":p["visibleCount"]*66,"triangles":p["visibleCount"]*64,"segments":p["visibleCount"]*32}.items():need(integer(t[k])==v,f"Fixed trace {k} mismatch")

        phase=i+(run["warmupFrames"] if p.get("continueWarmup",False) else 0);low=p.get("transitionFrom",.25);high=p.get("transitionTo",.75)
        bias=(low+(high-low)*(phase%300)/299 if phase//300%2==0 else high-(high-low)*(phase%300)/299) if changed else p["bias"]
        near(t["bias"],bias,2e-7,"Trace action bias mismatch")
        for k in CORE_COLUMNS[4:]:
            if c[k]!="":need(integer(c[k])>=0,"Invalid optional counter")
    need(metrics["sampleCount"]==len(core) and metrics["totalDirty"]==dirty_total and metrics["totalRebuild"]==rebuild_total and metrics["cleanupActiveObjects"]==0,"Gradient totals/cleanup mismatch")
    for key,pct in (("p50FrameIntervalMs",.5),("p95FrameIntervalMs",.95),("p99FrameIntervalMs",.99)):near(summary[key],quantile(frame_times,pct),2e-7,"Core percentile mismatch")
    near(summary["maxFrameIntervalMs"],max(frame_times),2e-7,"Core maximum mismatch");near(summary["overBudgetRatio"],sum(v>run["frameBudgetMs"] for v in frame_times)/len(frame_times),2e-7,"Core overbudget mismatch")
    for column,field,mode in (("main_thread_ns","meanMainThreadNanoseconds","mean"),("gc_allocated_bytes","totalGcAllocatedBytes","sum"),("system_used_memory_bytes","lastSystemUsedMemoryBytes","last")):
        values=[integer(row[column]) for row in core if row[column]!=""]
        if not values:need(summary[field] is None,f"Unavailable {column} replaced by a value")
        else:
            expected=sum(values)/len(values) if mode=="mean" else sum(values) if mode=="sum" else values[-1]
            near(summary[field],expected,max(1e-7,abs(expected)*1e-12),f"Optional metric {field} mismatch")
    need(summary["sampleCount"]==len(core),"Summary sample count")
    need(summary["correctness"]==metrics["correctness"],"Core/Gradient correctness mismatch")
    need(summary["exportSucceeded"] is True and summary["cleanupSucceeded"] is True,"Export/cleanup did not finish")
    if summary["measurementValidity"]=="valid":
        events=(directory/"events.log").read_text(encoding="utf-8")
        need("focus_lost" not in events and "application_paused" not in events,"Invalid focus/pause marked valid")
    mesh=read(directory/"gradient-mesh.json")
    near(mesh["bias"],number(trace[-1]["bias"]),2e-7,"Final submitted mesh/trace bias mismatch")
    quality=verify_quality(directory,plan,run,metrics);verify_mesh(directory,run)
    selection=verify_selection(directory,run,metrics,trace)
    need(summary["qualityStatus"]==quality["status"],"Derived quality status mismatch")
    need(summary["state"]=="completed" and summary["correctness"]=="pass" and summary["measurementValidity"]=="valid","Run did not complete with passing correctness and valid measurement")
    need(summary.get("processSuccess") is True and type(summary.get("exitCode")) is int and summary["exitCode"]==0,"Run process did not succeed")
    result={k:run[k] for k in ("runId","groupId","caseId","variant","runIndex","plannedRepeatCount")}
    result.update({k:summary[k] for k in ("state","correctness","measurementValidity","qualityStatus","failureCode","failureReason")})
    result["metrics"]={"frameIntervalMs":frame_times,"costMetrics":{"componentDirtyTotal":dirty_total,"componentRebuildTotal":rebuild_total,"visibleVertices":max(integer(t["vertices"]) for t in trace),"qualityMaxError":quality["maxError"]}}
    details={"runId":run["runId"],"rawEvidence":"verified","quality":quality,"environment":env,"frameP50":quantile(frame_times,.5),"frameP95":quantile(frame_times,.95),"frameP99":quantile(frame_times,.99)}
    if plan.get("experimentId")=="gradient-adaptive-v1":
        need(number(metrics["coldPrepareMs"])>0,"Cold prepare timing missing")
        details["coldPrepareMs"]=metrics["coldPrepareMs"]
    details["selection"]=selection
    return result,details

def verify_selection(directory,run,metrics,trace):
    p=run["parameters"];adaptive=p["effectMode"]=="adaptive";count=p["visibleCount"]
    raw=rows(directory/"selection-samples.csv",SELECTION_COLUMNS);need(len(raw)==len(trace),"Selection trace length")
    calls=hits=ticks=limited=0;minimum=65;maximum=0;max_error=0
    for i,(r,t) in enumerate(zip(raw,trace)):
        need(integer(r["sample_index"])==i,"Selection index")
        expected_calls=integer(t["rebuild_delta"]) if adaptive else 0
        if adaptive:
            nodes,error,is_limited=select(tuple(p["startRgba"]),tuple(p["endRgba"]),number(t["bias"]),p["minSegments"],p["maxSegments"],p["tolerance"]);segments=len(nodes)-1
        else:segments=32;error=0;is_limited=False
        need(integer(r["selection_calls"])==expected_calls and integer(r["cache_hits"])==0,"Selection/cache work mismatch")
        work_ticks=integer(r["selection_ticks"]);need(work_ticks>=0 and (expected_calls>0 or work_ticks==0),"Selection tick scope mismatch")
        need(integer(r["min_segments"])==integer(r["max_segments"])==segments,"Selection segment range")
        need(integer(r["quality_limited"])==(count if is_limited else 0),"Selection limited observation")
        near(r["estimated_error"],error,2e-10,"Selection analytic estimate")
        need(integer(t["segments"])==count*segments and integer(t["vertices"])==count*2*(segments+1) and integer(t["triangles"])==count*2*segments,"Actual adaptive topology")
        calls+=expected_calls;hits+=integer(r["cache_hits"]);ticks+=work_ticks;limited+=integer(r["quality_limited"]);minimum=min(minimum,segments);maximum=max(maximum,segments);max_error=max(max_error,error)
    expected={"subdivisionMode":p["effectMode"],"selectionAlgorithm":p["selectionAlgorithm"] if adaptive else "not_used","selectionCalls":calls,"selectionCacheHits":hits,"selectionTicks":ticks,"minSelectedSegments":minimum,"maxSelectedSegments":maximum,"qualityLimitedObservations":limited,"coldSelectionCalls":p["count"] if adaptive else 0,"coldSelectionCacheHits":0}
    for key,value in expected.items():need(metrics.get(key)==value,"Selection metric "+key)
    near(metrics["maximumEstimatedError"],max_error,2e-10,"Selection maximum estimate")
    frequency=metrics.get("selectionFrequency");cold=metrics.get("coldSelectionTicks")
    need(type(frequency) is int and frequency>0 and type(cold) is int and cold>=0,"Selection clock metadata")
    need((adaptive and cold>0) or (not adaptive and cold==0),"Cold selection timing scope")
    need(metrics.get("selectionTimingMeaning")=="Stopwatch elapsed ticks include cache lookup and instrumentation; not whole-frame CPU time","Selection clock meaning")
    return dict(calls=calls,cacheHits=hits,ticks=ticks,frequency=frequency,selectionMs=ticks*1000/frequency,coldSelectionMs=cold*1000/frequency,coldCalls=expected["coldSelectionCalls"],minSegments=minimum,maxSegments=maximum,limitedObservations=limited,maximumEstimatedError=max_error)


def verify_quality(directory,plan,run,metrics):
    if run["parameters"]["effectMode"]=="fixed":return fixed_quality(directory,plan,run,metrics)
    import numpy as np
    p=run["parameters"];dynamic=p["state"]=="all";scan_count=600 if dynamic else 1
    raw=rows(directory/"quality-scan.csv",SCAN_COLUMNS);grouped=[[] for _ in range(scan_count)]
    previous=-1
    for row in raw:
        index=integer(row["scan_index"]);need(0<=index<scan_count and index>=previous,"Scan order/index")
        grouped[index].append(row);previous=index
    q=contracts.validate_quality_document(read(directory/"quality.json"),plan)
    need(q["runId"]==run["runId"] and q["colorSpace"]=="encoded-rgb" and q["alphaMode"]=="straight-rgba-equal-weight" and q["aggregation"]==plan["quality"]["aggregation"],"Quality document identity/meaning")
    need(len(q["samples"])==4097,"Quality dense coverage")
    t=np.arange(4097)/4096;qt=np.asarray([v["t"] for v in q["samples"]]);qe=np.asarray([v["expectedRgba"] for v in q["samples"]]);qa=np.asarray([v["actualRgba"] for v in q["samples"]])
    need(np.max(np.abs(qt-t))<1e-12,"Quality document t grid")
    start=np.asarray(p["startRgba"],dtype=np.float32).astype(float);end=np.asarray(p["endRgba"],dtype=np.float32).astype(float)
    per_scan=[];matches=[];quant_max=0;function_max=0
    for index,group in enumerate(grouped):
        need(group,"Missing quality bias")
        data=np.asarray([[number(row[c]) for c in SCAN_COLUMNS] for row in group]);bias=data[0,1]
        expected_bias=(p["transitionFrom"]+(p["transitionTo"]-p["transitionFrom"])*(index%300)/299 if index//300%2==0 else p["transitionTo"]-(p["transitionTo"]-p["transitionFrom"])*(index%300)/299) if dynamic else p["bias"]
        near(bias,expected_bias,2e-7,"Quality action bias coverage")
        nodes,estimate,limited=select(tuple(p["startRgba"]),tuple(p["endRgba"]),bias,p["minSegments"],p["maxSegments"],p["tolerance"])
        need(len(group)==len(nodes),"Adaptive quality node count")
        need(np.array_equal(data[:,2],np.arange(len(nodes))) and np.max(np.abs(data[:,1]-bias))<1e-10,"Adaptive node index/bias")
        grid=np.asarray(nodes);need(np.max(np.abs(data[:,3]-grid))<1e-10,"Adaptive selected node positions")
        a=(1-bias)/bias;expected_nodes=start+(end-start)*(grid/(a+(1-a)*grid))[:,None]
        function_max=max(function_max,float(np.max(np.abs(data[:,4:8]-expected_nodes))))
        need(function_max<2e-6,"Adaptive runtime node function drift")
        quant=np.floor(np.clip(data[:,4:8].astype(np.float32),0,1)*np.float32(255)+np.float32(.5))
        need(np.array_equal(data[:,8:12],quant),"Adaptive Color32 quantization")
        quant_max=max(quant_max,float(np.max(np.abs(data[:,4:8]-quant/255))))
        cell=np.minimum(len(nodes)-2,np.maximum(0,np.searchsorted(grid,t,side="left")-1));u=(t-grid[cell])/(grid[cell+1]-grid[cell])
        actual=data[cell,4:8]+(data[cell+1,4:8]-data[cell,4:8])*u[:,None]
        reference=start+(end-start)*(t/(a+(1-a)*t))[:,None]
        error=float(np.max(np.abs(actual-reference)));per_scan.append(error)
        need(error<=estimate+3e-7,"Adaptive dense error exceeds analytic bound")
        matches.append(np.max(np.abs(qe-reference))<3e-7 and np.max(np.abs(qa-actual))<3e-7)
    worst=max(per_scan);near(metrics["qualityMaxError"],worst,3e-7,"Adaptive worst quality mismatch")
    near(metrics["quantizationMaxError"],quant_max,2e-7,"Adaptive quantization maximum")
    need(quant_max<=.5/255+1e-6,"Adaptive Color32 bound")
    need(any(match and error>=worst-3e-7 for match,error in zip(matches,per_scan)),"Adaptive quality document is not worst-bias scan")
    return dict(status="pass" if worst<=plan["quality"]["threshold"] else "quality_limited",maxError=worst,rmsError=float(np.sqrt(np.mean((qe-qa)**2))),quantizationMaxError=quant_max,functionFloatMaxError=function_max,scanCount=scan_count)


def verify_mesh(directory,run):
    if run["parameters"]["effectMode"]=="fixed":return fixed_mesh(directory,run)
    p=run["parameters"];mesh=read(directory/"gradient-mesh.json");vertices=mesh["vertices"];indices=mesh["indices"]
    bias=number(mesh["bias"]);nodes,_,_=select(tuple(p["startRgba"]),tuple(p["endRgba"]),bias,p["minSegments"],p["maxSegments"],p["tolerance"]);segments=len(nodes)-1
    need(mesh["mode"]=="AdaptiveSegments" and mesh["elementIndex"]==(p["changedIndices"][0] if p["changedIndices"] else 0),"Adaptive submitted mesh mode/element")
    need(len(vertices)==2*(segments+1) and len(indices)==6*segments,"Adaptive submitted mesh length")
    expected_indices=[v for i in range(segments) for v in ((2*i,2*i+1,2*i+3,2*i+3,2*i+2,2*i) if p["direction"]=="Horizontal" else (2*i,2*i+2,2*i+3,2*i+3,2*i+1,2*i))]
    need(indices==expected_indices and all(type(i) is int for i in indices),"Adaptive topology coverage/winding")
    width,height=(900,450) if p["layout"]=="large" else (900/p["geometry"]["columns"]*.9,480/p["geometry"]["rows"]*.9)
    expected_positions=[([-width/2+t*width,y,0] if p["direction"]=="Horizontal" else [y,-height/2+t*height,0]) for t in nodes for y in ((-height/2,height/2) if p["direction"]=="Horizontal" else (-width/2,width/2))]
    a=(1-bias)/bias
    for i,(vertex,expected) in enumerate(zip(vertices,expected_positions)):
        need(isinstance(vertex.get("position"),list) and len(vertex["position"])==3 and isinstance(vertex.get("rgba"),list) and len(vertex["rgba"])==4,"Adaptive vertex channels")
        need(all(abs(number(x)-y)<.001 for x,y in zip(vertex["position"],expected)),"Adaptive vertex position")
        need(all(type(c) is int and 0<=c<=255 for c in vertex["rgba"]),"Adaptive vertex color type")
        t=nodes[i//2];w=t/(a+(1-a)*t)
        color=[x+(y-x)*w for x,y in zip(p["startRgba"],p["endRgba"])]
        need(all(abs(c-math.floor(max(0,min(1,e))*255+.5))<=1 for c,e in zip(vertex["rgba"],color)),"Adaptive vertex gradient color")
