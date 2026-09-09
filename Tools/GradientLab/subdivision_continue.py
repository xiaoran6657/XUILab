"""Explicit remaining-suffix continuation of fixed subdivision Player dispatch with durable intents and exact owned PIDs.

A receipt never suppresses raw verification. Existing uncertain/failed runs
block redispatch; this module does not erase their artifacts or retry them.
"""
from __future__ import annotations
import argparse
import datetime as dt
import json
import os
from pathlib import Path
import subprocess
import time
import uuid
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"GradientLab"))
import gradient_experiment as contracts
from subdivision_plan import validate_subdivision
from player_plan import ARTIFACTS
def validate_plan(plan,require_frozen=True):return validate_subdivision(plan)
from player_verify import read,need,check_gate,verify_run


def tree_files(directory):
    contracts._assert_no_reparse_components(directory,str(directory))
    need(directory.is_dir(),"Required tree missing: "+str(directory))
    found=set()
    for current,dirs,files in os.walk(directory,followlinks=False):
        for name in dirs:contracts._assert_no_reparse_components(Path(current)/name,name)
        for name in files:
            item=Path(current)/name;contracts._assert_regular_file(item,str(item));found.add(item)
    return found


def check_build(path,player,plan,repo):
    manifest=read(path)
    need(manifest.get("schemaVersion")=="xuilab.gradient.build/v1","Build manifest schema")
    for key in ("candidateId","buildId","sourceRevision","dirty"):need(manifest[key]==plan[key],f"Build {key} mismatch")
    base=path.parent
    need((base/manifest["player"]).resolve()==player.resolve(),"Build Player path mismatch")
    need(isinstance(manifest.get("files"),dict) and manifest["files"],"Build hashes absent")
    for name,digest in manifest["files"].items():
        need(not Path(name).is_absolute() and ".." not in Path(name).parts,"Build path escape")
        item=base/name;contracts._assert_regular_file(item,name);need(contracts.sha256_file(item)==digest,f"Build file drift: {name}")
    need(isinstance(manifest.get("sourceInputs"),dict) and manifest["sourceInputs"],"Build source inputs absent")
    expected_sources={item.relative_to(repo).as_posix() for folder in ("XUILab/Assets","XUILab/Packages","XUILab/ProjectSettings") for item in tree_files(repo/folder)}
    need(expected_sources.issubset(manifest["sourceInputs"]),"Build source tree incomplete")
    build_tree=player.parent
    need(build_tree!=base and base in build_tree.parents,"Player must have a dedicated build subdirectory")
    expected_files={item.relative_to(base).as_posix() for item in tree_files(build_tree)}
    need(set(manifest["files"])==expected_files,"Build file tree incomplete or contains undeclared files")
    sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"UnityOperations"))
    from operation_journal import Journal,digest
    journal=Journal(repo);operation=manifest["buildOperation"];record_dir=journal.directory(operation)
    need(digest(record_dir/"request.json")==manifest["buildRequestSha256"] and digest(record_dir/"terminal.json")==manifest["buildTerminalSha256"],"Build journal binding mismatch")
    request=journal.request(operation);record=read(record_dir/"terminal.json")
    need(request["kind"]=="build" and request["candidate"]==plan["candidateId"] and request["inputs"]==manifest["sourceInputs"],"Build provenance request mismatch")
    need((repo/request["parameters"]["output_path"]).resolve()==player.resolve(),"Build request executable mismatch")
    need(journal.terminal(operation,record["evidence"],validate_only=True)["outcome"]=="pass","Build journal not passed")
    for name,digest in manifest["sourceInputs"].items():
        need(not Path(name).is_absolute() and ".." not in Path(name).parts,"Source path escape")
        item=repo/name;contracts._assert_regular_file(item,name);need(contracts.sha256_file(item)==digest,f"Frozen source drift: {name}")
    need(manifest["player"] in manifest["files"],"Executable not hashed")
    return manifest


def remove_owned(path,token):
    need(read(path).get("token")==token,"Ownership changed; preserve marker")
    path.unlink()


def check_inventory(root,plan):
    ids={r["runId"] for r in plan["runs"]}
    allowed=ids|{".receipts",".logs",".launches"}
    need({p.name for p in root.iterdir()}<=allowed,"Unknown root entry or unresolved intent/failure")
    for folder,suffix in ((".receipts",".json"),(".logs",".log"),(".launches",".json")):
        d=root/folder
        contracts._assert_no_reparse_components(d,str(d))
        if d.exists():
            need(d.is_dir() and {p.name for p in d.iterdir()}<={n+suffix for n in ids},"Unknown evidence entry")
    for name in ids:
        paths=[root/name,root/".receipts"/(name+".json"),root/".logs"/(name+".log"),root/".launches"/(name+".json")]
        for path in paths:contracts._assert_no_reparse_components(path,str(path))
        need(all(p.exists() for p in paths) or not any(p.exists() for p in paths),"Incomplete retained dispatch; inspect without resend")


def verify_receipt(root,run,ph,bh,player,manifest):
    name=run["runId"];directory=root/name
    r=read(root/".receipts"/(name+".json"));start=root/".launches"/(name+".json");log=root/".logs"/(name+".log")
    need(r.get("schemaVersion")=="xuilab.gradient.launch-receipt/v2" and r.get("runId")==name,"Receipt schema/run")
    need(type(r.get("pid")) is int and r["pid"]>0 and type(r.get("exitCode")) is int and r["exitCode"]==0,"Receipt PID/exit")
    need(r["planSha256"]==ph and r["buildManifestSha256"]==bh and r["correctness"]=="pass","Receipt control/outcome")
    need(r["player"]==str(player) and r["playerSha256"]==manifest["files"][manifest["player"]],"Receipt executable")
    need(r["launcherSha256"]==contracts.sha256_file(Path(__file__)),"Launcher source drift")
    need(0<r["durationSeconds"]<=run["timeoutSeconds"]+15,"Receipt duration")
    need(r["identitySha256"]==contracts.sha256_file(directory/"identity.json"),"Receipt identity")
    need(r["files"]=={n:contracts.sha256_file(directory/n) for n in ARTIFACTS},"Receipt raw hashes")
    need(log.stat().st_size>0 and r["logSha256"]==contracts.sha256_file(log),"Receipt log")
    need(r["launchRecordSha256"]==contracts.sha256_file(start),"Launch record hash")
    record=read(start)
    need(record["schemaVersion"]=="xuilab.gradient.launch-start/v2","Launch record schema")
    for key in ("runId","pid","planSha256","buildManifestSha256","player","playerSha256","command","launcherSha256","recoveryPolicySha256"):
        need(record[key]==r[key],"Launch record mismatch: "+key)
    command=r["command"]
    need(isinstance(command,list) and command and command[0]==str(player),"Launch executable command")
    expected={"-screen-fullscreen":"0","-screen-width":"960","-screen-height":"540","-logFile":str(log),"--xuilab-run-id":name,"--xuilab-output-root":str(root),"--gradient-plan-sha256":ph,"--gradient-build-manifest-sha256":bh}
    for flag,value in expected.items():
        need(command.count(flag)==1 and command[command.index(flag)+1]==value,"Launch command: "+flag)
    need(command.count("-force-d3d11")==1 and command.count("--xuilab-run")==1,"Launch flags")
    return r


def launch(plan_path,root,gate_path,player,build_path,repo,policy_path,policy_hash):
    plan=validate_plan(read(plan_path),require_frozen=True);gate=read(gate_path);check_gate(gate,plan,repo)
    from subdivision_recovery import validate_policy
    need(contracts.sha256_file(policy_path)==policy_hash,"Recovery policy hash mismatch")
    policy=validate_policy(policy_path,plan,plan_path,gate_path,build_path,repo,root)
    plan_hash=contracts.sha256_file(plan_path);gate_hash=contracts.sha256_file(gate_path);build_hash=contracts.sha256_file(build_path)
    need(all(r["parameters"]["preflightSha256"]==gate_hash and r["parameters"].get("buildManifestSha256")==build_hash for r in plan["runs"]),"Frozen plan gate/build manifest mismatch")
    contracts._assert_no_reparse_components(root,"run root");root.mkdir(parents=True,exist_ok=True)
    token=uuid.uuid4().hex;lock=repo/"Artifacts"/"gradient-player.lock"
    contracts.write_json_new(lock,{"schemaVersion":"xuilab.gradient.launch-lock/v1","pid":os.getpid(),"token":token,"createdUtc":dt.datetime.now(dt.timezone.utc).isoformat()})
    unsafe_to_release=False
    try:
        check_inventory(root,plan)
        for run in plan["runs"][policy["resumeIndex"]:]:
            run_id=run["runId"];directory=root/run_id;intent=root/(run_id+"-intent.json");failure=root/(run_id+"-orchestration-failure.json");receipt_path=root/".receipts"/(run_id+".json");log=root/".logs"/(run_id+".log")
            for path in (directory,intent,failure,receipt_path,log):contracts._assert_no_reparse_components(path,str(path))
            need(not intent.exists(),f"{run_id}: unresolved dispatch intent; do not resend")
            need(not failure.exists(),f"{run_id}: retained failed run; do not resend")
            need(contracts.sha256_file(policy_path)==policy_hash,"Recovery policy changed during dispatch")
            need(contracts.sha256_file(plan_path)==plan_hash and contracts.sha256_file(gate_path)==gate_hash and contracts.sha256_file(build_path)==build_hash,"Control input drift")
            manifest=check_build(build_path,player,plan,repo)
            need(gate["sourceInputs"]==manifest["sourceInputs"],"Gate/build source inventory mismatch")
            if directory.exists() or receipt_path.exists():
                need(directory.is_dir() and receipt_path.is_file(),f"{run_id}: incomplete receipt/run pair")
                receipt=verify_receipt(root,run,plan_hash,build_hash,player,manifest)
                result,_=verify_run(directory,plan,run,plan_hash,repo,gate)
                need(result["state"]=="completed" and result["correctness"]=="pass" and result["measurementValidity"]=="valid","Existing run not accepted")
                need(receipt.get("correctness")==result["correctness"] and receipt.get("qualityStatus")==result["qualityStatus"],"Receipt outcome mismatch")
                print(json.dumps({"runId":run_id,"action":"verified_existing","correctness":result["correctness"]}),flush=True);continue
            need(not log.exists(),f"{run_id}: existing log without terminal receipt")
            log.parent.mkdir(exist_ok=True)
            marker={"schemaVersion":"xuilab.gradient.launch-intent/v2","runId":run_id,"planSha256":plan_hash,"buildManifestSha256":build_hash,"token":token,"ownerPid":os.getpid(),"player":str(player),"createdUtc":dt.datetime.now(dt.timezone.utc).isoformat()}
            command=[str(player),"-screen-fullscreen","0","-screen-width","960","-screen-height","540","-force-d3d11","-logFile",str(log),"--xuilab-run","--xuilab-run-id",run_id,"--xuilab-output-root",str(root),"--gradient-plan",str(plan_path),"--gradient-plan-sha256",plan_hash,"--gradient-preflight",str(gate_path),"--gradient-build-manifest",str(build_path),"--gradient-build-manifest-sha256",build_hash]
            start_path=root/".launches"/(run_id+".json")
            contracts._assert_no_reparse_components(start_path,str(start_path))
            need(not start_path.exists(),"Retained launch record; inspect before retry")
            marker.update(recoveryPolicySha256=policy_hash,command=command,playerSha256=contracts.sha256_file(player),launcherSha256=contracts.sha256_file(Path(__file__)))
            contracts.write_json_new(intent,marker)
            process=None;started=time.monotonic()
            try:
                startup=None
                if hasattr(subprocess,"STARTUPINFO"):
                    startup=subprocess.STARTUPINFO();startup.dwFlags|=subprocess.STARTF_USESHOWWINDOW;startup.wShowWindow=1
                unsafe_to_release=True
                process=subprocess.Popen(command,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,startupinfo=startup)
                contracts.write_json_new(start_path,dict(marker,schemaVersion="xuilab.gradient.launch-start/v2",pid=process.pid))
                try:exit_code=process.wait(timeout=run["timeoutSeconds"])
                except subprocess.TimeoutExpired:
                    if process.poll() is None:process.kill();process.wait(timeout=15)
                    unsafe_to_release=False
                    raise RuntimeError("Player wall-clock timeout")
                unsafe_to_release=False
                need(exit_code==0,f"Player exit code {exit_code}")
                result,detail=verify_run(directory,plan,run,plan_hash,repo,gate)
                need(result["state"]=="completed" and result["correctness"]=="pass" and result["measurementValidity"]=="valid","Player correctness/validity did not pass")
                need(log.is_file() and log.stat().st_size>0,"Missing/empty Player log")
                contracts.write_json_new(receipt_path,{"schemaVersion":"xuilab.gradient.launch-receipt/v2","recoveryPolicySha256":policy_hash,"runId":run_id,"planSha256":plan_hash,"buildManifestSha256":build_hash,"pid":process.pid,"player":str(player),"playerSha256":marker["playerSha256"],"command":command,"launcherSha256":marker["launcherSha256"],"launchRecordSha256":contracts.sha256_file(start_path),"logSha256":contracts.sha256_file(log),"exitCode":exit_code,"durationSeconds":time.monotonic()-started,"identitySha256":contracts.sha256_file(directory/"identity.json"),"files":{n:contracts.sha256_file(directory/n) for n in ARTIFACTS},"correctness":result["correctness"],"qualityStatus":result["qualityStatus"],"completedUtc":dt.datetime.now(dt.timezone.utc).isoformat()})
                remove_owned(intent,token)
                print(json.dumps({"runId":run_id,"action":"completed","p95":detail["frameP95"],"correctness":result["correctness"]}),flush=True)
            except BaseException as exc:
                if unsafe_to_release:
                    # Preserve uncertain running work; only a timeout above kills its owned process.
                    raise
                contracts.write_json_new(failure,{"runId":run_id,"reason":str(exc),"pid":None if process is None else process.pid,"exitCode":None if process is None else process.returncode,"durationSeconds":time.monotonic()-started,"planSha256":plan_hash})
                remove_owned(intent,token)
                raise
    finally:
        if not unsafe_to_release:remove_owned(lock,token)


def main():
    p=argparse.ArgumentParser(description=__doc__)
    for name in ("plan","runs","gate","player","build-manifest","policy"):p.add_argument("--"+name,type=Path,required=True)
    p.add_argument("--repo",type=Path,default=Path.cwd());p.add_argument("--policy-sha256",required=True);a=p.parse_args()
    launch(a.plan.resolve(),a.runs.absolute(),a.gate.resolve(),a.player.resolve(),a.build_manifest.resolve(),a.repo.resolve(),a.policy.resolve(),a.policy_sha256)
if __name__=="__main__":main()
