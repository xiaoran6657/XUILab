"""Frozen recovery of a retained startup-focus failure; never rewrites evidence."""
from pathlib import Path
import gradient_experiment as contracts
from player_verify import read,need
from subdivision_launch import tree_files

TOOL_FILES=['Tools/GradientLab/subdivision_launch.py', 'Tools/GradientLab/subdivision_continue.py', 'Tools/GradientLab/subdivision_recovery.py', 'Tools/GradientLab/subdivision_report.py', 'Tools/GradientLab/subdivision_plan.py', 'Tools/GradientLab/player_verify.py', 'Tools/GradientLab/player_plan.py', 'Tools/GradientLab/gradient_experiment.py', 'Tools/GradientLab/gradient_recovery.py', 'Tools/UnityOperations/operation_journal.py', 'Docs/Experiments/GRADIENT_SUBDIVISION_RECOVERY-r1.md']

def repo_path(repo,name):
    p=Path(name)
    need(isinstance(name,str) and not p.is_absolute() and ".." not in p.parts,"Unsafe recovery path")
    p=repo/p;contracts._assert_no_reparse_components(p,name)
    return p

def validate_policy(path,plan,plan_path,gate_path,build_path,repo,continued_root):
    policy=read(path)
    need(policy["schemaVersion"]=="xuilab.gradient.subdivision-recovery/v1","Recovery schema")
    for field,item in (("planSha256",plan_path),("preflightSha256",gate_path),("buildManifestSha256",build_path)):
        need(policy[field]==contracts.sha256_file(item),"Recovery control drift: "+field)
    start=policy["resumeIndex"];need(type(start)is int and 0<start<len(plan["runs"]),"Recovery index")
    need(policy["selectedRunIds"]==[r["runId"] for r in plan["runs"][start:]],"Recovery must be exact remaining suffix including invalid attempt")
    need(policy["failedRunId"]==plan["runs"][start]["runId"],"Recovery failed run mismatch")
    old=repo_path(repo,policy["originalRoot"]);new=repo_path(repo,policy["continuedRoot"])
    need(new.resolve()==continued_root.resolve() and new.resolve()!=old.resolve(),"Recovery destination mismatch")
    files={p.relative_to(old).as_posix():contracts.sha256_file(p) for p in tree_files(old)}
    need(files==policy["retainedFiles"],"Retained original attempt drift")
    need(set(policy["toolInputs"])==set(TOOL_FILES),"Recovery tool scope incomplete")
    for name,digest in policy["toolInputs"].items():
        need(contracts.sha256_file(repo_path(repo,name))==digest,"Recovery tool drift: "+name)
    selected=set(policy["selectedRunIds"])
    if new.exists():
        need({p.name for p in new.iterdir()}<=selected|{".receipts",".logs",".launches"},"Unselected or unresolved continued run")
    first=[r["runId"] for r in plan["runs"][:start]];rid=policy["failedRunId"]
    need({p.name for p in old.iterdir()}==set(first)|{rid,rid+"-orchestration-failure.json",".receipts",".logs",".launches"},"Retained tree does not match completed prefix plus failure")
    need({p.name for p in (old/".receipts").iterdir()}=={r+".json" for r in first},"Retained receipt prefix incomplete")
    for folder,suffix in ((".logs",".log"),(".launches",".json")):
        need({p.name for p in (old/folder).iterdir()}=={r+suffix for r in first+[rid]},"Retained execution inventory mismatch")
    failure=read(old/(rid+"-orchestration-failure.json"));launch=read(old/".launches"/(rid+".json"));summary=read(old/rid/"summary.json")
    need(failure["runId"]==rid and failure["planSha256"]==policy["planSha256"] and failure["exitCode"]==3,"Not an eligible invalid measurement")
    need(type(failure["pid"])is int and failure["pid"]>0 and failure["pid"]==launch["pid"],"Failure process binding")
    need(summary["runId"]==rid and summary["state"]=="completed" and summary["correctness"]=="pass" and summary["measurementValidity"]=="invalid" and summary["exitCode"]==3,"Failure classification changed")
    need(summary["exportSucceeded"] is True and summary["cleanupSucceeded"] is True,"Failure export/cleanup incomplete")
    events=(old/rid/"events.log").read_text(encoding="utf-8")
    need("focus_lost" in events and "measure_started" in events and events.index("focus_lost")<events.index("measure_started"),"Expected pre-measure focus loss missing")
    identity=read(old/rid/"identity.json")
    need(identity["runId"]==rid and identity["planSha256"]==policy["planSha256"] and identity["buildManifestSha256"]==policy["buildManifestSha256"],"Invalid attempt identity mismatch")
    need(set(identity["artifactSha256"])==set(plan["artifacts"])-{"identity.json"},"Invalid raw inventory incomplete")
    for name,digest in identity["artifactSha256"].items():need(contracts.sha256_file(old/rid/name)==digest,"Invalid attempt raw drift")
    need(identity["configSha256"].lower()==contracts.sha256_file(old/rid/"config.json"),"Invalid config drift")
    return policy

