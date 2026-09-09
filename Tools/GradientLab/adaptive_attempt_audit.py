"""Stricter failed-attempt provenance and explicit exclusions for a G2 campaign."""
from pathlib import Path,PureWindowsPath
from adaptive_verify import read,need
import gradient_experiment as c
from historical_verify import recorded_path

def audit(repo,plan_path,build_path,policy_path,recorded=None):
    plan=read(plan_path);build=read(build_path);policy=read(policy_path);recorded=recorded or PureWindowsPath(str(repo));excluded=[]
    ph=c.sha256_file(plan_path);bh=c.sha256_file(build_path)
    for prior in policy["history"]:
        root=repo/prior["root"];rid=plan["runs"][prior["end"]]["runId"];directory=root/rid
        need({x.name for x in directory.iterdir()}==set(plan["artifacts"]),"Invalid exact raw file set")
        for x in directory.iterdir():c._assert_regular_file(x,str(x))
        failure=read(root/(rid+"-orchestration-failure.json"));launch=read(root/".launches"/(rid+".json"));summary=read(directory/"summary.json")
        need(launch["schemaVersion"]=="xuilab.gradient.launch-start/v2" and launch["runId"]==rid and launch["pid"]==failure["pid"],"Invalid launch identity")
        need(launch["planSha256"]==ph and launch["buildManifestSha256"]==bh and launch["dispatchPolicySha256"]==prior["policySha256"],"Invalid launch controls")
        launcher="adaptive_launch.py" if prior["start"]==0 else "adaptive_continue.py"
        need(launch["launcherSha256"]==c.sha256_file(repo/"Tools/GradientLab"/launcher),"Invalid launcher SHA")
        player=recorded/PureWindowsPath(build_path.parent.relative_to(repo).as_posix())/PureWindowsPath(build["player"])
        recorded_path(launch["player"],player);need(launch["playerSha256"]==build["files"][build["player"]],"Invalid player SHA")
        command=launch["command"];need(isinstance(command,list) and command[0]==launch["player"],"Invalid command executable")
        scalar={"-screen-fullscreen":"0","-screen-width":"960","-screen-height":"540","--xuilab-run-id":rid,"--gradient-plan-sha256":ph,"--gradient-build-manifest-sha256":bh}
        for flag,value in scalar.items():need(command.count(flag)==1 and command[command.index(flag)+1]==value,"Invalid command flag")
        paths={"-logFile":recorded/PureWindowsPath(prior["root"])/".logs"/(rid+".log"),"--xuilab-output-root":recorded/PureWindowsPath(prior["root"]),"--gradient-plan":recorded/PureWindowsPath(plan_path.relative_to(repo).as_posix()),"--gradient-build-manifest":recorded/PureWindowsPath(build_path.relative_to(repo).as_posix()),"--gradient-preflight":recorded/"Artifacts/gradient-adaptive-validation/preflight-r1.json"}
        for flag,value in paths.items():need(command.count(flag)==1,"Invalid command path count");recorded_path(command[command.index(flag)+1],value)
        need(command.count("-force-d3d11")==command.count("--xuilab-run")==1,"Invalid command switches")
        events=(directory/"events.log").read_text();need("focus_lost" in events,"Invalid attempt lacks focus loss")
        need(summary["correctness"]=="pass" and summary["measurementValidity"]=="invalid" and failure["exitCode"]==summary["exitCode"]==3,"Invalid outcome")
        excluded.append(dict(runId=rid,root=prior["root"],policySha256=prior["policySha256"],exitCode=3,correctness="pass",measurementValidity="invalid",reason=summary["failureReason"],excludedFromStatistics=True,focusLossPhase="measure" if events.index("focus_lost")>events.index("measure_started") else "warmup",failureSha256=c.sha256_file(root/(rid+"-orchestration-failure.json"))))
    return excluded
