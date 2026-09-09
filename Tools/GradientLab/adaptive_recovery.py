"""Exact remaining suffix after retained invalid measurement; all prior attempts immutable."""
from pathlib import Path
import gradient_experiment as c
from adaptive_policy import validate_policy as base_validate,relative_root
from adaptive_verify import read,need
from subdivision_launch import tree_files

EXTRA=("Tools/GradientLab/adaptive_continue.py","Tools/GradientLab/adaptive_recovery.py","Tools/GradientLab/adaptive_campaign_report.py")

def validate_policy(path,plan,plan_path,gate_path,build_path,repo,root):
    p=base_validate(path,plan,plan_path,gate_path,build_path,repo,root)
    need(p.get("recoveryVersion")=="xuilab.gradient.adaptive-recovery/v1","Recovery schema")
    need(type(p.get("resumeIndex")) is int and 0<p["resumeIndex"]<len(plan["runs"]),"Recovery index")
    need(p.get("selectedRunIds")==[r["runId"] for r in plan["runs"][p["resumeIndex"]:]],"Recovery exact suffix")
    need(isinstance(p.get("recoveryTools"),dict) and set(p["recoveryTools"])==set(EXTRA),"Recovery tool inventory")
    for n,h in p["recoveryTools"].items():need(c.sha256_file(repo/n)==h,"Recovery tool drift "+n)
    need(isinstance(p.get("history"),list) and p["history"],"Recovery history missing")
    offset=0;roots=set()
    for prior in p["history"]:
        old=relative_root(repo,prior["root"]);need(old!=root and old not in root.parents and root not in old.parents and str(old) not in roots,"Recovery roots overlap")
        roots.add(str(old));start=prior["start"];end=prior["end"]
        need(type(start) is int and type(end) is int and start==offset and start<=end<len(plan["runs"]),"Recovery history gap")
        oldpolicy=relative_root(repo,prior["policy"]);need(c.sha256_file(oldpolicy)==prior["policySha256"],"Historical policy drift")
        original=base_validate(oldpolicy,plan,plan_path,gate_path,build_path,repo,old)
        need(original.get("resumeIndex",0)==start,"Historical start mismatch")
        need({f.relative_to(old).as_posix():c.sha256_file(f) for f in tree_files(old)}==prior["files"],"Retained tree drift")
        accepted=[r["runId"] for r in plan["runs"][start:end]];failed=plan["runs"][end]["runId"]
        need({x.name for x in old.iterdir()}==set(accepted)|{failed,failed+"-orchestration-failure.json",".receipts",".logs",".launches"},"Historical exact run tree")
        need({x.name for x in (old/".receipts").iterdir()}=={n+".json" for n in accepted},"Historical receipt coverage")
        for folder,suffix in ((".logs",".log"),(".launches",".json")):
            need({x.name for x in (old/folder).iterdir()}=={n+suffix for n in accepted+[failed]},"Historical sidecar coverage")
        failure=read(old/(failed+"-orchestration-failure.json"));launch=read(old/".launches"/(failed+".json"));summary=read(old/failed/"summary.json");identity=read(old/failed/"identity.json")
        need(failure["runId"]==failed and failure["planSha256"]==p["planSha256"] and failure["exitCode"]==3 and type(failure["pid"]) is int and failure["pid"]>0 and failure["pid"]==launch["pid"],"Failure binding")
        need(summary["runId"]==failed and summary["state"]=="completed" and summary["correctness"]=="pass" and summary["measurementValidity"]=="invalid" and summary["exitCode"]==3 and summary["exportSucceeded"] is True and summary["cleanupSucceeded"] is True,"Failure classification")
        need("focus_lost" in (old/failed/"events.log").read_text(),"Expected focus loss absent")
        need(identity["runId"]==failed and identity["planSha256"]==p["planSha256"] and identity["buildManifestSha256"]==p["buildManifestSha256"],"Invalid raw identity")
        need(set(identity["artifactSha256"])==set(plan["artifacts"])-{"identity.json"},"Invalid raw inventory")
        for n,h in identity["artifactSha256"].items():need(c.sha256_file(old/failed/n)==h,"Invalid raw drift")
        need(identity["configSha256"].lower()==c.sha256_file(old/failed/"config.json"),"Invalid config drift")
        offset=end
    need(offset==p["resumeIndex"],"Recovery index/history mismatch")
    selected=set(p["selectedRunIds"])
    if root.exists():need({x.name for x in root.iterdir()}<=selected|{".receipts",".logs",".launches"},"Unresolved or unselected recovery run")
    return p
