"""Read-only campaign validation for two retained attempts and an exact suffix."""
from pathlib import Path
import gradient_experiment as contracts
from player_verify import read,need
from subdivision_launch import tree_files
from subdivision_recovery import repo_path,TOOL_FILES as OLD_TOOLS
TOOL_FILES=OLD_TOOLS+["Tools/GradientLab/subdivision_campaign.py","Tools/GradientLab/subdivision_focus_launch.py","Tools/GradientLab/subdivision_campaign_report.py","Tools/GradientLab/startup_focus.py","Docs/Experiments/GRADIENT_SUBDIVISION_RECOVERY-r2.md"]

def validate_policy(path,plan,plan_path,gate_path,build_path,repo,continued_root):
    policy=read(path)
    need(policy["schemaVersion"]=="xuilab.gradient.subdivision-campaign/v1","Campaign schema")
    for field,item in (("planSha256",plan_path),("preflightSha256",gate_path),("buildManifestSha256",build_path)):
        need(policy[field]==contracts.sha256_file(item),"Campaign control drift: "+field)
    need(policy["resumeIndex"]==54 and len(plan["runs"])==160,"Campaign scope")
    need(policy["selectedRunIds"]==[r["runId"] for r in plan["runs"][54:]],"Exact remaining suffix required")
    destination=repo_path(repo,policy["continuedRoot"])
    need(destination.resolve()==continued_root.resolve(),"Campaign destination")
    need(set(policy["toolInputs"])==set(TOOL_FILES),"Campaign tool scope")
    for name,digest in policy["toolInputs"].items():need(contracts.sha256_file(repo_path(repo,name))==digest,"Campaign tool drift: "+name)
    prior_path=repo_path(repo,policy["priorPolicy"])
    need(contracts.sha256_file(prior_path)==policy["priorPolicySha256"],"Prior policy drift")
    prior=read(prior_path)
    need(prior["resumeIndex"]==52 and prior["planSha256"]==policy["planSha256"],"Prior policy scope")
    need(len(policy["retained"])==2,"Retained attempts count")
    need(policy["retained"][0]["root"]==prior["originalRoot"] and policy["retained"][1]["root"]==prior["continuedRoot"],"Prior roots mismatch")
    roots={destination.resolve()}
    for span,start,end,exit_code in zip(policy["retained"],(0,52),(52,54),(3,1)):
        need(span["startIndex"]==start and span["endIndex"]==end,"Retained interval")
        root=repo_path(repo,span["root"]);resolved=root.resolve()
        need(all(resolved!=r and resolved not in r.parents and r not in resolved.parents for r in roots),"Overlapping roots");roots.add(resolved)
        actual={p.relative_to(root).as_posix():contracts.sha256_file(p) for p in tree_files(root)}
        need(actual==span["files"],"Retained files drift")
        if start==0:need(actual==prior["retainedFiles"],"Original inventory changed")
        ids=[r["runId"] for r in plan["runs"][start:end]];failed=plan["runs"][end]["runId"]
        expected=set(ids)|{".receipts",".launches",".logs",failed+"-orchestration-failure.json"}
        if exit_code==3:expected.add(failed)
        need({p.name for p in root.iterdir()}==expected,"Retained root inventory")
        for folder,suffix,values in ((".receipts",".json",ids),(".launches",".json",ids+[failed]),(".logs",".log",ids+[failed])):
            need({p.name for p in (root/folder).iterdir()}=={v+suffix for v in values},"Retained sidecar inventory")
        failure=read(root/(failed+"-orchestration-failure.json"));launch=read(root/".launches"/(failed+".json"))
        need(failure["runId"]==failed and failure["planSha256"]==policy["planSha256"] and failure["exitCode"]==exit_code,"Failure identity/exit")
        need(type(failure["pid"]) is int and failure["pid"]>0 and failure["pid"]==launch["pid"],"Failure owned process")
        need(launch["runId"]==failed and launch["planSha256"]==policy["planSha256"] and launch["buildManifestSha256"]==policy["buildManifestSha256"],"Failure launch identity")
        launcher="Tools/GradientLab/subdivision_launch.py" if start==0 else "Tools/GradientLab/subdivision_continue.py"
        need(launch["launcherSha256"]==policy["toolInputs"][launcher],"Excluded attempt launcher mismatch")
        if exit_code==1:
            need(failure["reason"]=="Player wall-clock timeout" and 180<=failure["durationSeconds"]<=195,"Expected timeout missing")
            need(not (root/failed).exists(),"Timeout unexpectedly has raw samples")
            need(launch["recoveryPolicySha256"]==policy["priorPolicySha256"],"Prior launch policy mismatch")
        else:
            summary=read(root/failed/"summary.json");identity=read(root/failed/"identity.json")
            need(summary["correctness"]=="pass" and summary["measurementValidity"]=="invalid" and summary["exitCode"]==3 and summary["exportSucceeded"] and summary["cleanupSucceeded"],"Invalid classification")
            events=(root/failed/"events.log").read_text()
            need("focus_lost" in events and events.index("focus_lost")<events.index("measure_started"),"Expected premeasure focus loss")
            need(identity["runId"]==failed and identity["planSha256"]==policy["planSha256"],"Invalid raw identity")
            need(set(identity["artifactSha256"])==set(plan["artifacts"])-{"identity.json"},"Invalid raw inventory")
            for name,digest in identity["artifactSha256"].items():need(contracts.sha256_file(root/failed/name)==digest,"Invalid raw drift")
    if destination.exists():
        need({p.name for p in destination.iterdir()}<=set(policy["selectedRunIds"])|{".receipts",".logs",".launches"},"Unresolved new attempt")
    return policy
