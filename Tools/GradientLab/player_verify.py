"""Recompute Gradient Player evidence from raw artifacts (NumPy for dense scans).

No Unity calls, no result mutation, and no merging frames across processes.
"""
from __future__ import annotations
import argparse
import csv
import json
import math
import statistics
import hashlib
from pathlib import Path
import gradient_experiment as contracts
import gradient_recovery as recovery

CORE_COLUMNS = ["sample_index","unity_frame","elapsed_ms","frame_interval_ms","main_thread_ns","gc_allocated_bytes","system_used_memory_bytes"]
TRACE_COLUMNS = ["sample_index","action_frame","settled_frame","bias","visible","culled","dirty_delta","rebuild_delta","vertices","triangles","segments","changed_count"]
SCAN_COLUMNS = ["scan_index","bias","node_index","t","r","g","b","a","quant_r","quant_g","quant_b","quant_a"]

class EvidenceError(ValueError): pass

def need(value, reason):
    if not value: raise EvidenceError(reason)

def number(value):
    x=float(value)
    need(math.isfinite(x), "Nonfinite numeric sample")
    return x

def integer(value):
    x=int(value)
    need(str(x)==str(value), "Noncanonical integer sample")
    return x

def rows(path, columns):
    contracts._assert_regular_file(path,str(path))
    with path.open(encoding="utf-8-sig",newline="") as f:
        reader=csv.DictReader(f)
        need(reader.fieldnames==columns,f"{path.name}: wrong columns")
        result=list(reader)
    need(all(set(r)==set(columns) and all(v is not None for v in r.values()) for r in result),f"{path.name}: malformed rows")
    return result

def read(path):
    contracts._assert_regular_file(path,str(path))
    return contracts.read_json(path)

def quantile(values,p):
    values=sorted(values);pos=(len(values)-1)*p;i=int(pos)
    return values[i]+(values[min(i+1,len(values)-1)]-values[i])*(pos-i)

def near(actual,expected,tolerance,reason):
    need(abs(number(actual)-expected)<=tolerance,reason)

def check_gate(gate, plan, root):
    need(gate.get("schemaVersion")=="xuilab.gradient.preflight/v1" and gate.get("status")=="pass","Preflight status/schema")
    need(gate.get("candidateId")==plan["candidateId"],"Preflight candidate mismatch")
    need(isinstance(gate.get("sourceInputs"),dict) and gate["sourceInputs"],"Preflight source inputs absent")
    for name,digest in gate["sourceInputs"].items():
        path=root/name
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
    if plan.get("experimentId")=="gradient-subdivision-v1":
        need(len(checks)==5 and {c.get("kind") for c in checks}==set(assemblies),"Subdivision requires exactly five full semantic gates")
    need({c.get("kind") for c in checks}>={"gradient-math-mesh","gradient-lifecycle","gradient-pixel","gradient-runner"},"Required semantic gates missing")
    for check in checks:
        path=root/check["terminalPath"]
        need(not Path(check["terminalPath"]).is_absolute() and ".." not in Path(check["terminalPath"]).parts,"Unsafe gate evidence path")
        need(contracts.sha256_file(path)==check["sha256"],"Gate evidence drift")
        request_path=Path(check["requestPath"])
        need(not request_path.is_absolute() and ".." not in request_path.parts,"Unsafe request path")
        request_path=root/request_path;need(contracts.sha256_file(request_path)==check["requestSha256"],"Gate request drift")
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
        if plan.get("experimentId")=="gradient-subdivision-v1":
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


def verify_quality(directory, plan, run, metrics):
    import numpy as np
    p=run["parameters"];state=p["state"];original=state in ("image","disabled");dynamic=state in ("few","all")
    segments=1 if original or state=="linear" else p.get("segments",32)
    raw=rows(directory/"quality-scan.csv",SCAN_COLUMNS)
    scan_count=600 if dynamic else 1
    need(len(raw)==scan_count*(segments+1),"Wrong quality scan coverage")
    data=np.asarray([[number(r[c]) for c in SCAN_COLUMNS] for r in raw],dtype=float).reshape(scan_count,segments+1,len(SCAN_COLUMNS))
    need(np.array_equal(data[:,:,0],np.repeat(np.arange(scan_count)[:,None],segments+1,axis=1)),"Quality scan indices")
    need(np.array_equal(data[:,:,2],np.repeat(np.arange(segments+1)[None,:],scan_count,axis=0)),"Quality node indices")
    grid=np.arange(segments+1)/segments
    need(np.max(np.abs(data[:,:,3]-grid))<1e-10,"Quality node t grid")
    biases=data[:,0,1]
    need(np.max(np.abs(data[:,:,1]-biases[:,None]))<1e-10,"Bias varies within scan")
    phase=np.arange(scan_count)%300
    low=p.get("transitionFrom",.25);high=p.get("transitionTo",.75)
    expected_bias=np.where(np.arange(scan_count)//300%2==0,low+(high-low)*phase/299,high-(high-low)*phase/299) if dynamic else np.array([p["bias"]])
    need(np.max(np.abs(biases-expected_bias))<2e-7,"Action scan bias coverage")
    start=np.asarray(p["startRgba"],dtype=np.float32).astype(float);end=np.asarray(p["endRgba"],dtype=np.float32).astype(float)
    a=(1-biases)/biases
    weights=np.broadcast_to(grid,(scan_count,segments+1)) if state=="linear" else grid/(a[:,None]+(1-a[:,None])*grid)
    expected_nodes=np.ones_like(data[:,:,4:8]) if original else start+(end-start)*weights[:,:,None]
    need(np.max(np.abs(data[:,:,4:8]-expected_nodes))<2e-6,"Runtime quality nodes do not match independent curve")
    quant=np.floor(np.clip(data[:,:,4:8].astype(np.float32),0,1)*np.float32(255)+np.float32(.5))
    need(np.array_equal(data[:,:,8:12],quant),"Color32 node quantization mismatch")
    quant_max=float(np.max(np.abs(data[:,:,4:8]-quant/255)))
    near(metrics["quantizationMaxError"],quant_max,2e-7,"Quantization maximum mismatch")
    need(quant_max<=.5/255+1e-6,"Color32 quantization exceeds bound")
    t=np.arange(4097)/4096;cell=np.minimum(segments-1,(t*segments).astype(int));u=t*segments-cell
    nodes=data[:,:,4:8]
    actual=nodes[:,cell,:]+(nodes[:,cell+1,:]-nodes[:,cell,:])*u[None,:,None]
    w=np.broadcast_to(t,(scan_count,4097)) if state=="linear" else t/(a[:,None]+(1-a[:,None])*t)
    reference=np.ones_like(actual) if original else start+(end-start)*w[:,:,None]
    errors=np.abs(actual-reference);per_scan=np.max(errors,axis=(1,2));worst=float(np.max(per_scan))
    near(metrics["qualityMaxError"],worst,3e-7,"Worst transition quality mismatch")
    q=contracts.validate_quality_document(read(directory/"quality.json"),plan)
    need(q["runId"]==run["runId"],"Quality report belongs to another run")
    need(q["aggregation"]==plan["quality"]["aggregation"] and q["colorSpace"]=="encoded-rgb" and q["alphaMode"]=="straight-rgba-equal-weight","Quality aggregation/space/alpha mismatch")
    need(len(q["samples"])==4097,"Quality document requires 4097 points")
    qt=np.asarray([s["t"] for s in q["samples"]]);qe=np.asarray([s["expectedRgba"] for s in q["samples"]]);qa=np.asarray([s["actualRgba"] for s in q["samples"]])
    need(np.max(np.abs(qt-t))<1e-12,"Quality document grid mismatch")
    eligible=np.where(per_scan>=worst-3e-7)[0]
    need(any(np.max(np.abs(qe-reference[i]))<3e-7 and np.max(np.abs(qa-actual[i]))<3e-7 for i in eligible),"Quality document is not a worst-case scan")
    return {"status":"pass" if worst<=plan["quality"]["threshold"] else "quality_limited","maxError":worst,"rmsError":float(np.sqrt(np.mean((qe-qa)**2))),"quantizationMaxError":quant_max,"scanCount":scan_count}

def verify_mesh(directory,run):
    p=run["parameters"];mesh=read(directory/"gradient-mesh.json");vertices=mesh["vertices"];indices=mesh["indices"]
    expected_element=p["changedIndices"][0] if p["changedIndices"] else 0
    need(type(mesh.get("elementIndex")) is int and mesh["elementIndex"]==expected_element,"Submitted mesh element mismatch")
    need(all(isinstance(v.get("position"),list) and len(v["position"])==3 and all(math.isfinite(float(x)) for x in v["position"]) and abs(float(v["position"][2]))<1e-6 and isinstance(v.get("rgba"),list) and len(v["rgba"])==4 and all(type(c) is int and 0<=c<=255 for c in v["rgba"]) for v in vertices),"Malformed mesh position or RGBA")
    need(len(vertices)==p["expectedVertices"] and len(indices)==p["expectedTriangles"]*3,"Submitted mesh topology length")
    need(all(isinstance(i,int) and 0<=i<len(vertices) for i in indices),"Mesh index range")
    mode="OriginalImage" if p["state"] in ("image","disabled") else "LinearVertices" if p["state"]=="linear" else "FixedSegments"
    need(mesh["mode"]==mode,"Submitted mesh mode mismatch")
    geo=p["geometry"]
    width,height=(880,24) if p["layout"]=="clip" else (900,450) if p["layout"]=="large" else (900/geo["columns"]*.9,480/geo["rows"]*.9)
    xs=[number(v["position"][0]) for v in vertices];ys=[number(v["position"][1]) for v in vertices]
    near(min(xs),-width/2,.001,"Mesh left bound");near(max(xs),width/2,.001,"Mesh right bound");near(min(ys),-height/2,.001,"Mesh bottom bound");near(max(ys),height/2,.001,"Mesh top bound")
    if mode=="FixedSegments":
        segments=p.get("segments",32)
        expected_positions=[([-width/2+i/segments*width,y,0] if p["direction"]=="Horizontal" else [y,-height/2+i/segments*height,0]) for i in range(segments+1) for y in ((-height/2,height/2) if p["direction"]=="Horizontal" else (-width/2,width/2))]
        expected_indices=[v for i in range(segments) for v in ((2*i,2*i+1,2*i+3,2*i+3,2*i+2,2*i) if p["direction"]=="Horizontal" else (2*i,2*i+2,2*i+3,2*i+3,2*i+1,2*i))]
    else:
        expected_positions=[[-width/2,-height/2,0],[-width/2,height/2,0],[width/2,height/2,0],[width/2,-height/2,0]]
        expected_indices=[0,1,2,2,3,0]
    need(indices==expected_indices,"Submitted mesh topology coverage/winding mismatch")
    for vertex,expected in zip(vertices,expected_positions):
        need(all(abs(number(a)-b)<.001 for a,b in zip(vertex["position"],expected)),"Submitted mesh vertex position mismatch")
    bias=number(mesh["bias"]);need(.05-1e-7<=bias<=.95+1e-7,"Mesh bias outside contract");a=(1-bias)/bias
    for v in vertices:
        pos=v["position"];t=(pos[0]+width/2)/width if p["direction"]=="Horizontal" else (pos[1]+height/2)/height
        w=t if p["state"]=="linear" else t/(a+(1-a)*t)
        color=[1]*4 if mode=="OriginalImage" else [x+(y-x)*w for x,y in zip(p["startRgba"],p["endRgba"])]
        need(all(abs(integer(str(c))-math.floor(max(0,min(1,e))*255+.5))<=1 for c,e in zip(v["rgba"],color)),"Submitted mesh color differs from contract")

def verify_run(directory,plan,run,plan_hash,repo_root,gate):
    p=run["parameters"]
    if plan.get("experimentId")=="gradient-subdivision-v1":
        from subdivision_plan import validate_subdivision
        validate_subdivision(plan)
        need(contracts.sha256_file(repo_root/"Docs/Experiments/GRADIENT_SUBDIVISION_PROTOCOL-r1.md")==p["experimentProtocolSha256"],"Subdivision protocol hash")
    else:need(p.get("segments",32)==32 and p.get("transitionFrom",.25)==.25 and p.get("transitionTo",.75)==.75 and not p.get("continueWarmup",False),"Baseline action/segments changed")
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
        for k,v in {"visible":p["visibleCount"],"culled":p["count"]-p["visibleCount"],"vertices":p["visibleCount"]*p["expectedVertices"],"triangles":p["visibleCount"]*p["expectedTriangles"],"segments":p["visibleCount"]*(p.get("segments",32) if p["effectMode"] in ("fixed32","fixed") else 0),"changed_count":changed}.items():need(integer(t[k])==v,f"Trace {k} mismatch")
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
    need(summary["qualityStatus"]==quality["status"],"Derived quality status mismatch")
    need(summary["state"]=="completed" and summary["correctness"]=="pass" and summary["measurementValidity"]=="valid","Run did not complete with passing correctness and valid measurement")
    need(summary.get("processSuccess") is True and type(summary.get("exitCode")) is int and summary["exitCode"]==0,"Run process did not succeed")
    result={k:run[k] for k in ("runId","groupId","caseId","variant","runIndex","plannedRepeatCount")}
    result.update({k:summary[k] for k in ("state","correctness","measurementValidity","qualityStatus","failureCode","failureReason")})
    result["metrics"]={"frameIntervalMs":frame_times,"costMetrics":{"componentDirtyTotal":dirty_total,"componentRebuildTotal":rebuild_total,"visibleVertices":p["visibleCount"]*p["expectedVertices"],"qualityMaxError":quality["maxError"]}}
    details={"runId":run["runId"],"rawEvidence":"verified","quality":quality,"environment":env,"frameP50":quantile(frame_times,.5),"frameP95":quantile(frame_times,.95),"frameP99":quantile(frame_times,.99)}
    if plan.get("experimentId")=="gradient-subdivision-v1":
        need(number(metrics["coldPrepareMs"])>0,"Cold prepare timing missing")
        details["coldPrepareMs"]=metrics["coldPrepareMs"]
    return result,details

def verify(plan_path,run_root,repo_root,gate_path,build_path):
    plan=contracts.validate_plan(read(plan_path),require_frozen=True);gate=read(gate_path);check_gate(gate,plan,repo_root)
    gate_hash=contracts.sha256_file(gate_path);need(all(r["parameters"]["preflightSha256"]==gate_hash for r in plan["runs"]),"Plan gate hash mismatch")
    from player_launch import check_build
    build_hash=contracts.sha256_file(build_path);need(all(r["parameters"]["buildManifestSha256"]==build_hash for r in plan["runs"]),"Plan build manifest hash mismatch")
    manifest=read(build_path);check_build(build_path,build_path.parent/manifest["player"],plan,repo_root)
    need(gate["sourceInputs"]==manifest["sourceInputs"],"Gate/build source inventory mismatch")
    expected_names={r["runId"] for r in plan["runs"]}|{".receipts",".logs"}
    need(run_root.is_dir() and {x.name for x in run_root.iterdir()}.issubset(expected_names),"Unknown or unresolved run/sidecar in result root")
    for folder,suffix in ((".receipts",".json"),(".logs",".log")):
        directory=run_root/folder;contracts._assert_no_reparse_components(directory,str(directory))
        need(directory.is_dir() and {x.name for x in directory.iterdir()}=={r["runId"]+suffix for r in plan["runs"]},"Missing/unknown receipt or log")
    plan_hash=contracts.sha256_file(plan_path);results=[];details=[];failures=[]
    for run in plan["runs"]:
        try:
            row,detail=verify_run(run_root/run["runId"],plan,run,plan_hash,repo_root,gate)
            receipt=read(run_root/".receipts"/(run["runId"]+".json"))
            need(receipt.get("schemaVersion")=="xuilab.gradient.launch-receipt/v1" and receipt.get("runId")==run["runId"] and type(receipt.get("exitCode")) is int and receipt["exitCode"]==0,"Receipt run/exit mismatch")
            need(receipt.get("planSha256")==plan_hash and receipt.get("buildManifestSha256")==build_hash and receipt.get("identitySha256")==contracts.sha256_file(run_root/run["runId"]/"identity.json") and receipt.get("qualityStatus")==row["qualityStatus"],"Receipt evidence binding mismatch")
            results.append(row);details.append(detail)
        except (EvidenceError,contracts.GradientToolError,OSError,ValueError,KeyError,TypeError) as exc:failures.append({"runId":run["runId"],"status":"not_ready","reason":str(exc)})
    document={"schemaVersion":"xuilab.gradient.results/v1","planId":plan["planId"],"contractId":plan["contractId"],"contractSha256":plan["contractSha256"],"evidenceKind":plan["evidenceKind"],"runs":results}
    if details:
        fields=("operatingSystem","processorType","processorCount","graphicsDeviceName","graphicsDeviceVersion")
        baseline=details[0]["environment"]
        for item in details:
            if any(item["environment"].get(k)!=baseline.get(k) for k in fields):failures.append({"runId":item["runId"],"status":"not_ready","reason":"Cross-run hardware/OS environment drift"})
    if not failures:contracts.validate_results_document(document,plan)
    return {"schemaVersion":"xuilab.gradient.raw-verification/v1","planSha256":plan_hash,"status":"pass" if not failures else "not_ready","failures":failures,"details":details,"results":document if not failures else None}

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument("--plan",type=Path,required=True);p.add_argument("--runs",type=Path,required=True);p.add_argument("--repo",type=Path,default=Path.cwd());p.add_argument("--gate",type=Path,required=True);p.add_argument("--output",type=Path,required=True);p.add_argument("--build-manifest",type=Path,required=True);a=p.parse_args()
    result=verify(a.plan,a.runs,a.repo,a.gate,a.build_manifest)
    with a.output.open("x",encoding="utf-8") as f:json.dump(result,f,ensure_ascii=False,indent=2);f.write("\n")
    print(json.dumps({"status":result["status"],"verifiedRuns":len(result["details"]),"failures":result["failures"]},ensure_ascii=False))
    return 0 if result["status"]=="pass" else 1
if __name__=="__main__":raise SystemExit(main())
