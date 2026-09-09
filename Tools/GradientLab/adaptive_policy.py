"""Freeze all G2 dispatch tools and controls; a failure never authorizes a retry."""
from pathlib import Path,PureWindowsPath
import gradient_experiment as contracts
from player_verify import read,need

TOOL_NAMES=("adaptive_plan.py","adaptive_focus.py","adaptive_math.py","adaptive_verify.py","adaptive_launch.py","adaptive_policy.py","adaptive_report.py","player_plan.py","player_verify.py","gradient_experiment.py","gradient_recovery.py","subdivision_plan.py","subdivision_launch.py","subdivision_focus_launch.py","subdivision_report.py","startup_focus.py")
TOOL_PATHS=tuple("Tools/GradientLab/"+name for name in TOOL_NAMES)+("Tools/UnityOperations/operation_journal.py",)

def relative_root(repo,name):
    need(isinstance(name,str) and name and ":" not in name and "\\" not in name and not PureWindowsPath(name).is_absolute() and ".." not in Path(name).parts,"Unsafe run root")
    path=(repo/name).absolute();contracts._assert_no_reparse_components(path,name);need(path!=repo and repo in path.parents,"Run root escapes repository");return path

def validate_policy(path,plan,plan_path,gate_path,build_path,repo,root):
    canonical=repo/"Docs/Experiments/GRADIENT_ADAPTIVE_PROTOCOL-r1.md"
    contracts._assert_regular_file(canonical,str(canonical))
    need(contracts.sha256_file(canonical)==plan["runs"][0]["parameters"]["experimentProtocolSha256"],"Canonical adaptive protocol drift before dispatch")
    p=read(path);need(p.get("schemaVersion")=="xuilab.gradient.adaptive-dispatch/v1","Dispatch policy schema")
    need(p.get("candidateId")==plan["candidateId"] and p.get("runIds")==[r["runId"] for r in plan["runs"]],"Dispatch candidate/coverage")
    need(relative_root(repo,p["runRoot"])==root.absolute(),"Dispatch root mismatch")
    for control in (plan_path,gate_path,build_path,path):
        need(root!=control and root not in control.parents,"Control file inside run tree")
    build=read(build_path);player_tree=(build_path.parent/build["player"]).parent.absolute()
    need(root!=player_tree and root not in player_tree.parents and player_tree not in root.parents,"Run/build trees overlap")
    expected={"planSha256":contracts.sha256_file(plan_path),"preflightSha256":contracts.sha256_file(gate_path),"buildManifestSha256":contracts.sha256_file(build_path),"protocolSha256":plan["runs"][0]["parameters"]["experimentProtocolSha256"]}
    for key,value in expected.items():need(p.get(key)==value,"Dispatch control "+key)
    need(p.get("startupFocus")=="owned-pid-before-Prepare" and p.get("failureAction")=="stop-preserve-no-retry","Dispatch behavior")
    need(isinstance(p.get("toolInputs"),dict) and set(p["toolInputs"])==set(TOOL_PATHS),"Dispatch tool inventory")
    for name,digest in p["toolInputs"].items():
        item=repo/name;contracts._assert_regular_file(item,name);need(contracts.sha256_file(item)==digest,"Dispatch tool drift: "+name)
    return p

def create_policy(plan,plan_path,gate_path,build_path,repo,root):
    canonical=repo/"Docs/Experiments/GRADIENT_ADAPTIVE_PROTOCOL-r1.md"
    contracts._assert_regular_file(canonical,str(canonical))
    need(contracts.sha256_file(canonical)==plan["runs"][0]["parameters"]["experimentProtocolSha256"],"Canonical adaptive protocol drift before dispatch")
    return dict(schemaVersion="xuilab.gradient.adaptive-dispatch/v1",candidateId=plan["candidateId"],runRoot=root.relative_to(repo).as_posix(),runIds=[r["runId"] for r in plan["runs"]],planSha256=contracts.sha256_file(plan_path),preflightSha256=contracts.sha256_file(gate_path),buildManifestSha256=contracts.sha256_file(build_path),protocolSha256=plan["runs"][0]["parameters"]["experimentProtocolSha256"],startupFocus="owned-pid-before-Prepare",failureAction="stop-preserve-no-retry",toolInputs={name:contracts.sha256_file(repo/name) for name in TOOL_PATHS})
