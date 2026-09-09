"""Verify copied G1 evidence against original native identities, without dispatch."""
import argparse,json,sys
from pathlib import Path,PureWindowsPath
import gradient_experiment as contracts
from player_verify import read,need,near,check_gate,verify_run,quantile
from player_plan import ARTIFACTS
from subdivision_plan import validate_subdivision,SCENARIOS
from subdivision_launch import tree_files,check_inventory
from subdivision_campaign import validate_policy
from subdivision_focus_launch import verify_startup_focus
from subdivision_report import distribution,compare
from historical_verify import build_provenance,gate_closure,recorded_path

def receipt(root,recorded,relative,run,plan_hash,build_hash,build,launcher,policy_hash=None,focus=False):
    directory=root/relative/run["runId"];base=root/relative;rid=run["runId"]
    r=read(base/".receipts"/(rid+".json"));start=base/".launches"/(rid+".json");log=base/".logs"/(rid+".log")
    need(r["schemaVersion"]=="xuilab.gradient.launch-receipt/v2" and r["runId"]==rid,"Receipt schema/run")
    need(type(r["pid"]) is int and r["pid"]>0 and type(r["exitCode"]) is int and r["exitCode"]==0 and r["correctness"]=="pass","Receipt process/outcome")
    need(r["planSha256"]==plan_hash and r["buildManifestSha256"]==build_hash and 0<r["durationSeconds"]<=run["timeoutSeconds"]+15,"Receipt controls/duration")
    player_rel="Artifacts/gradient-subdivision-player-r2/"+build["player"]
    recorded_path(r["player"],recorded/PureWindowsPath(player_rel))
    need(r["playerSha256"]==build["files"][build["player"]] and r["launcherSha256"]==contracts.sha256_file(root/launcher),"Receipt executable/tool")
    need(r["identitySha256"]==contracts.sha256_file(directory/"identity.json") and r["files"]=={n:contracts.sha256_file(directory/n) for n in ARTIFACTS},"Receipt raw hashes")
    need(log.stat().st_size>0 and r["logSha256"]==contracts.sha256_file(log) and r["launchRecordSha256"]==contracts.sha256_file(start),"Receipt sidecar hashes")
    launch=read(start);need(launch["schemaVersion"]=="xuilab.gradient.launch-start/v2","Start schema")
    for k in ("runId","pid","planSha256","buildManifestSha256","player","playerSha256","command","launcherSha256"):
        need(launch[k]==r[k],"Start/receipt mismatch: "+k)
    if policy_hash:need(r["recoveryPolicySha256"]==launch["recoveryPolicySha256"]==policy_hash,"Receipt recovery policy")
    command=r["command"];need(isinstance(command,list) and command[0]==r["player"],"Command executable")
    for flag,value in {"-screen-fullscreen":"0","-screen-width":"960","-screen-height":"540","--xuilab-run-id":rid,"--gradient-plan-sha256":plan_hash,"--gradient-build-manifest-sha256":build_hash}.items():
        need(command.count(flag)==1 and command[command.index(flag)+1]==value,"Command flag mismatch: "+flag)
    for flag,value in {"-logFile":recorded/PureWindowsPath(relative)/".logs"/(rid+".log"),"--xuilab-output-root":recorded/PureWindowsPath(relative),"--gradient-plan":recorded/"Artifacts/gradient-subdivision-player-r2"/("pilot-plan.json" if rid.startswith("g1-pilot") else "matrix-plan.json"),"--gradient-preflight":recorded/"Artifacts/gradient-subdivision-validation/preflight-r2.json","--gradient-build-manifest":recorded/"Artifacts/gradient-subdivision-player-r2/build-manifest.json"}.items():
        need(command.count(flag)==1,"Command path count");recorded_path(command[command.index(flag)+1],value)
    need(command.count("-force-d3d11")==command.count("--xuilab-run")==1,"Command flags")
    if focus:verify_startup_focus(r["startupFocus"],directory,r["pid"])
    return r

def verify(root,expected):
    root=root.absolute();sha=contracts.sha256_file
    need(Path(__file__).absolute()==root/"Tools/GradientLab/subdivision_historical.py","Invoke archived verifier")
    for name in ("gradient_experiment","player_verify","player_plan","subdivision_plan","subdivision_launch","subdivision_campaign","subdivision_focus_launch","subdivision_recovery","subdivision_report","historical_verify","player_launch","player_resume","gradient_recovery","operation_journal"):
        folder="Tools/UnityOperations/" if name=="operation_journal" else "Tools/GradientLab/"
        need(Path(sys.modules[name].__file__).absolute()==root/(folder+name+".py"),"Dependency outside archive: "+name)
    need(sha(root/"baseline-manifest.json")==expected,"External manifest hash")
    metadata=read(root/"baseline-manifest.json");need(metadata["schemaVersion"]=="xuilab.gradient.subdivision-historical/v1","Archive schema")
    recorded=PureWindowsPath(metadata["recordedRepoRoot"]);need(recorded.is_absolute() and ".." not in recorded.parts,"Recorded root")
    actual={p.relative_to(root).as_posix() for p in tree_files(root)}-{"baseline-manifest.json"}
    need(actual==set(metadata["files"]),"Archive file set")
    for name,value in metadata["files"].items():
        need(not Path(name).is_absolute() and ".." not in Path(name).parts,"Unsafe member")
        need((root/name).stat().st_size==value["size"] and sha(root/name)==value["sha256"],"Archive payload drift: "+name)
    base=root/"Artifacts/gradient-subdivision-player-r2";build_path=base/"build-manifest.json";build=read(build_path)
    gate_path=root/"Artifacts/gradient-subdivision-validation/preflight-r2.json";gate=read(gate_path)
    need(build["schemaVersion"]=="xuilab.gradient.build/v1" and build["sourceInputs"]==metadata["sourceInputs"]==gate["sourceInputs"],"Source scope")
    for name,digest in build["sourceInputs"].items():need(sha(root/name)==digest,"Frozen source drift")
    sources={p.relative_to(root).as_posix() for folder in ("XUILab/Assets","XUILab/Packages","XUILab/ProjectSettings") for p in tree_files(root/folder)}
    need(sources.issubset(build["sourceInputs"]),"Unexpected Unity source")
    need({p.relative_to(base).as_posix() for p in tree_files(base/"build")}==set(build["files"]),"Build file set")
    for name,digest in build["files"].items():need(sha(base/name)==digest,"Build drift")
    need(not (root/"Artifacts/gradient-player.lock").exists(),"Retained global lock")
    output={}
    for kind in ("matrix","pilot"):
        plan_path=base/(kind+"-plan.json");plan=validate_subdivision(read(plan_path));ph=sha(plan_path);bh=sha(build_path);gh=sha(gate_path)
        for k in ("candidateId","buildId","sourceRevision","dirty"):need(plan[k]==build[k]==metadata[k],"Candidate identity")
        check_gate(gate,plan,root)
        need(all(r["parameters"]["preflightSha256"]==gh and r["parameters"]["buildManifestSha256"]==bh for r in plan["runs"]),"Plan controls")
        if kind=="matrix":
            build_provenance(root,build,plan,recorded)
            for check in gate["checks"]:
                envelope=read(root/check["terminalPath"]);request=root/"Artifacts/unity-operations"/envelope["operation"]/"request.json"
                need(read(request)==read(root/check["requestPath"]),"Export/journal request mismatch")
                gate_closure(root,dict(check,requestSha256=sha(request)),recorded)
            policy_path=base/"campaign-policy-r2.json";policy_hash=sha(policy_path);policy=read(policy_path);new_root=root/policy["continuedRoot"]
            validate_policy(policy_path,plan,plan_path,gate_path,build_path,root,new_root)
            check_inventory(new_root,plan);need({p.name for p in new_root.iterdir()}==set(policy["selectedRunIds"])|{".receipts",".logs",".launches"},"Incomplete suffix")
        else:
            check_inventory(base/"pilot",plan);need({p.name for p in (base/"pilot").iterdir()}=={r["runId"] for r in plan["runs"]}|{".receipts",".logs",".launches"},"Incomplete pilot")
        saved=read(base/(kind+"-report-r1.json"))
        need(saved["status"]==saved["correctness"]=="pass" and saved["measurementValidity"]=="valid" and saved["runCount"]==len(plan["runs"]),"Saved report status/count")
        need(saved["planSha256"]==ph and saved["buildManifestSha256"]==bh and saved["preflightSha256"]==gh,"Saved report controls")
        expected_tool="subdivision_campaign_report.py" if kind=="matrix" else "subdivision_report.py"
        # The pilot report predates recovery changes to its report tool; bind the archived pre-recovery source.
        tool=base/"tool-sources-r1/Tools/GradientLab/subdivision_report.py" if kind=="pilot" else root/"Tools/GradientLab"/expected_tool
        if kind=="pilot" and not tool.exists():tool=base/"tool-sources-r1/subdivision_report.py"
        need(saved["reportToolSha256"]==sha(tool),"Saved report tool identity")
        need([r["runId"] for r in saved["runs"]]==[r["runId"] for r in plan["runs"]],"Saved run order")
        environment=None
        for ordinal,(run,row) in enumerate(zip(plan["runs"],saved["runs"])):
            binding=None;focus=False;launcher="Tools/GradientLab/subdivision_launch.py"
            if kind=="pilot":relative="Artifacts/gradient-subdivision-player-r2/pilot"
            elif ordinal<52:relative=policy["retained"][0]["root"]
            elif ordinal<54:relative=policy["retained"][1]["root"];launcher="Tools/GradientLab/subdivision_continue.py";binding=policy["priorPolicySha256"]
            else:relative=policy["continuedRoot"];launcher="Tools/GradientLab/subdivision_focus_launch.py";binding=policy_hash;focus=True
            r=receipt(root,recorded,relative,run,ph,bh,build,launcher,binding,focus)
            result,detail=verify_run(root/relative/run["runId"],plan,run,ph,root,gate)
            need(row["correctness"]==result["correctness"]=="pass" and row["measurementValidity"]==result["measurementValidity"]=="valid" and row["qualityStatus"]==r["qualityStatus"]==result["qualityStatus"],"Saved raw outcome")
            if kind=="matrix":need(row["root"]==relative,"Report source root")
            p=run["parameters"];need(row["scenario"]==p["scenario"] and row["segments"]==p["segments"] and row["repeat"]==run["runIndex"],"Saved row grouping")
            env=detail["environment"]
            if environment is None:environment=env
            need(all(env.get(k)==environment.get(k)==saved["environment"].get(k) for k in ("operatingSystem","processorType","processorCount","graphicsDeviceName","graphicsDeviceVersion")),"Environment drift")
            values=result["metrics"]["frameIntervalMs"];q=detail["quality"];cost=result["metrics"]["costMetrics"]
            derived=dict(p50=quantile(values,.5),p95=quantile(values,.95),p99=quantile(values,.99),maximum=max(values),overBudgetRatio=sum(v>run["frameBudgetMs"] for v in values)/len(values),coldPrepareMs=detail["coldPrepareMs"],qualityMaxError=q["maxError"],qualityRmsError=q["rmsError"],quantizationMaxError=q["quantizationMaxError"],componentDirtyTotal=cost["componentDirtyTotal"],componentRebuildTotal=cost["componentRebuildTotal"],visibleVertices=cost["visibleVertices"])
            for k,value in derived.items():near(row[k],value,1e-10,"Saved metric mismatch: "+k)
        groups=[];comparisons=[]
        for scenario,*_ in SCENARIOS:
            subset=[r for r in saved["runs"] if r["scenario"]==scenario]
            if not subset:continue
            for seg in (8,16,32,64):
                runs=sorted([r for r in subset if r["segments"]==seg],key=lambda r:r["repeat"])
                if not runs:continue
                need(len(runs)==(5 if kind=="matrix" else 1),"Repeat completeness")
                groups.append(dict(scenario=scenario,segments=seg,runs=runs,qualityStatus="pass" if all(r["qualityStatus"]=="pass" for r in runs) else "quality_limited",statistics={m:distribution([r[m] for r in runs]) for m in ("p50","p95","p99","maximum","overBudgetRatio","coldPrepareMs","qualityMaxError","qualityRmsError","quantizationMaxError")}))
            if kind=="matrix":
                baseline=[r["p95"] for r in sorted(subset,key=lambda r:r["repeat"]) if r["segments"]==32]
                for seg in (8,16,64):comparisons.append(dict(scenario=scenario,segments=seg,**compare(baseline,[r["p95"] for r in sorted(subset,key=lambda r:r["repeat"]) if r["segments"]==seg])))
        need(saved["groups"]==groups and saved["comparisons"]==comparisons,"Saved group/comparison mismatch")
        if kind=="matrix":
            recovery=saved["recovery"];need(recovery["policySha256"]==policy_hash and recovery["retainedValidPrefix"]==54 and recovery["continuedRoot"]==policy["continuedRoot"] and len(recovery["excludedAttempts"])==2,"Report recovery binding")
            for i,(span,excluded) in enumerate(zip(policy["retained"],recovery["excludedAttempts"])):
                rid=plan["runs"][span["endIndex"]]["runId"];failure=read(root/span["root"]/(rid+"-orchestration-failure.json"))
                need(excluded["root"]==span["root"] and excluded["runId"]==rid and excluded["exitCode"]==failure["exitCode"] and excluded["durationSeconds"]==failure["durationSeconds"],"Excluded attempt identity")
                need(excluded["candidateId"]==plan["candidateId"] and excluded["buildId"]==plan["buildId"] and excluded["rawAvailable"] is (i==0),"Excluded attempt provenance")
                need(excluded["qualityStatus"]==(read(root/span["root"]/rid/"summary.json")["qualityStatus"] if i==0 else "unavailable"),"Excluded quality")
        output[kind]=dict(runs=len(plan["runs"]),comparisons={k:sum(c["result"]==k for c in comparisons) for k in ("improved","regressed","inconclusive")})
    return dict(schemaVersion="xuilab.gradient.subdivision-historical-verification/v1",integrity="pass",correctness="pass",candidateId=metadata["candidateId"],archiveManifestSha256=expected,verifierSha256=sha(Path(__file__)),results=output,limitation="Historical evidence only; no new Player execution or current-workspace acceptance")

if __name__=="__main__":
    p=argparse.ArgumentParser(description=__doc__);p.add_argument("--archive",type=Path,required=True);p.add_argument("--manifest-sha256",required=True);p.add_argument("--output",type=Path);a=p.parse_args();r=verify(a.archive,a.manifest_sha256)
    if a.output:
        need(not a.output.absolute().is_relative_to(a.archive.resolve()),"Write verification outside archive");contracts.write_json_new(a.output,r)
    print(json.dumps(r))
