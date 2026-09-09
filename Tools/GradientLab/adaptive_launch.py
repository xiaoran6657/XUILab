"""G2 owned Player dispatch with durable intents, full receipts, and startup focus."""
import argparse
import datetime as dt
import json
import os
from pathlib import Path
import subprocess
import time
import uuid
import gradient_experiment as contracts
from adaptive_plan import validate_adaptive,ARTIFACTS
from adaptive_verify import read,need,check_gate,verify_run,safe_relative
from subdivision_launch import tree_files,check_inventory,remove_owned,check_build as base_check_build
from subdivision_focus_launch import verify_startup_focus

def validate_plan(plan,require_frozen=True):return validate_adaptive(plan)

def check_build(path,player,plan,repo):
    manifest=read(path)
    safe_relative(path.parent,manifest["player"])
    for name in manifest["files"]:safe_relative(path.parent,name)
    for name in manifest["sourceInputs"]:safe_relative(repo,name)
    return base_check_build(path,player,plan,repo)

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
    for key in ("runId","pid","planSha256","buildManifestSha256","player","playerSha256","command","launcherSha256","dispatchPolicySha256"):
        need(record[key]==r[key],"Launch record mismatch: "+key)
    command=r["command"]
    need(isinstance(command,list) and command and command[0]==str(player),"Launch executable command")
    expected={"-screen-fullscreen":"0","-screen-width":"960","-screen-height":"540","-logFile":str(log),"--xuilab-run-id":name,"--xuilab-output-root":str(root),"--gradient-plan-sha256":ph,"--gradient-build-manifest-sha256":bh}
    for flag,value in expected.items():
        need(command.count(flag)==1 and command[command.index(flag)+1]==value,"Launch command: "+flag)
    need(command.count("-force-d3d11")==1 and command.count("--xuilab-run")==1,"Launch flags")
    verify_startup_focus(r["startupFocus"],directory,r["pid"])
    return r


def launch(plan_path,root,gate_path,player,build_path,repo,policy_path,policy_hash):
    import numpy  # Required by full quality verification; fail before dispatch.
    plan=validate_plan(read(plan_path),require_frozen=True);gate=read(gate_path);check_gate(gate,plan,repo)
    from adaptive_policy import validate_policy
    need(contracts.sha256_file(policy_path)==policy_hash,"Dispatch policy hash mismatch")
    policy=validate_policy(policy_path,plan,plan_path,gate_path,build_path,repo,root)
    plan_hash=contracts.sha256_file(plan_path);gate_hash=contracts.sha256_file(gate_path);build_hash=contracts.sha256_file(build_path)
    need(all(r["parameters"]["preflightSha256"]==gate_hash and r["parameters"].get("buildManifestSha256")==build_hash for r in plan["runs"]),"Frozen plan gate/build manifest mismatch")
    contracts._assert_no_reparse_components(root,"run root");root.mkdir(parents=True,exist_ok=True)
    token=uuid.uuid4().hex;lock=repo/"Artifacts"/"gradient-player.lock"
    contracts.write_json_new(lock,{"schemaVersion":"xuilab.gradient.launch-lock/v1","pid":os.getpid(),"token":token,"createdUtc":dt.datetime.now(dt.timezone.utc).isoformat()})
    unsafe_to_release=False
    try:
        check_inventory(root,plan)
        for run in plan["runs"]:
            run_id=run["runId"];directory=root/run_id;intent=root/(run_id+"-intent.json");failure=root/(run_id+"-orchestration-failure.json");receipt_path=root/".receipts"/(run_id+".json");log=root/".logs"/(run_id+".log")
            for path in (directory,intent,failure,receipt_path,log):contracts._assert_no_reparse_components(path,str(path))
            need(not intent.exists(),f"{run_id}: unresolved dispatch intent; do not resend")
            need(not failure.exists(),f"{run_id}: retained failed run; do not resend")
            need(contracts.sha256_file(policy_path)==policy_hash,"Dispatch policy changed during dispatch")
            validate_policy(policy_path,plan,plan_path,gate_path,build_path,repo,root)
            need(contracts.sha256_file(plan_path)==plan_hash and contracts.sha256_file(gate_path)==gate_hash and contracts.sha256_file(build_path)==build_hash,"Control input drift")
            manifest=check_build(build_path,player,plan,repo)
            need(gate["sourceInputs"]==manifest["sourceInputs"],"Gate/build source inventory mismatch")
            if directory.exists() or receipt_path.exists():
                need(directory.is_dir() and receipt_path.is_file(),f"{run_id}: incomplete receipt/run pair")
                receipt=verify_receipt(root,run,plan_hash,build_hash,player,manifest)
                result,_=verify_run(directory,plan,run,plan_hash,repo,gate)
                need(result["state"]=="completed" and result["correctness"]=="pass" and result["measurementValidity"]=="valid","Existing run not accepted")
                need(receipt.get("dispatchPolicySha256")==policy_hash,"Existing receipt dispatch policy mismatch")
                need(receipt.get("correctness")==result["correctness"] and receipt.get("qualityStatus")==result["qualityStatus"],"Receipt outcome mismatch")
                print(json.dumps({"runId":run_id,"action":"verified_existing","correctness":result["correctness"]}),flush=True);continue
            need(not log.exists(),f"{run_id}: existing log without terminal receipt")
            log.parent.mkdir(exist_ok=True)
            marker={"schemaVersion":"xuilab.gradient.launch-intent/v2","runId":run_id,"planSha256":plan_hash,"buildManifestSha256":build_hash,"token":token,"ownerPid":os.getpid(),"player":str(player),"createdUtc":dt.datetime.now(dt.timezone.utc).isoformat()}
            command=[str(player),"-screen-fullscreen","0","-screen-width","960","-screen-height","540","-force-d3d11","-logFile",str(log),"--xuilab-run","--xuilab-run-id",run_id,"--xuilab-output-root",str(root),"--gradient-plan",str(plan_path),"--gradient-plan-sha256",plan_hash,"--gradient-preflight",str(gate_path),"--gradient-build-manifest",str(build_path),"--gradient-build-manifest-sha256",build_hash]
            start_path=root/".launches"/(run_id+".json")
            contracts._assert_no_reparse_components(start_path,str(start_path))
            need(not start_path.exists(),"Retained launch record; inspect before retry")
            marker.update(dispatchPolicySha256=policy_hash,command=command,playerSha256=contracts.sha256_file(player),launcherSha256=contracts.sha256_file(Path(__file__)))
            contracts.write_json_new(intent,marker)
            process=None;focus=None;started=time.monotonic()
            try:
                startup=None
                if hasattr(subprocess,"STARTUPINFO"):
                    startup=subprocess.STARTUPINFO();startup.dwFlags|=subprocess.STARTF_USESHOWWINDOW;startup.wShowWindow=1
                unsafe_to_release=True
                process=subprocess.Popen(command,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,startupinfo=startup)
                contracts.write_json_new(start_path,dict(marker,schemaVersion="xuilab.gradient.launch-start/v2",pid=process.pid))
                from adaptive_focus import acquire_foreground
                try:
                    focus=acquire_foreground(process)
                except BaseException:
                    if process.poll() is None:process.kill();process.wait(timeout=15)
                    unsafe_to_release=False
                    raise
                try:exit_code=process.wait(timeout=max(.001,run["timeoutSeconds"]-(time.monotonic()-started)))
                except subprocess.TimeoutExpired:
                    if process.poll() is None:process.kill();process.wait(timeout=15)
                    unsafe_to_release=False
                    raise RuntimeError("Player wall-clock timeout")
                unsafe_to_release=False
                need(exit_code==0,f"Player exit code {exit_code}")
                result,detail=verify_run(directory,plan,run,plan_hash,repo,gate)
                need(result["state"]=="completed" and result["correctness"]=="pass" and result["measurementValidity"]=="valid","Player correctness/validity did not pass")
                verify_startup_focus(focus,directory,process.pid)
                need(log.is_file() and log.stat().st_size>0,"Missing/empty Player log")
                contracts.write_json_new(receipt_path,{"schemaVersion":"xuilab.gradient.launch-receipt/v2","startupFocus":focus,"dispatchPolicySha256":policy_hash,"runId":run_id,"planSha256":plan_hash,"buildManifestSha256":build_hash,"pid":process.pid,"player":str(player),"playerSha256":marker["playerSha256"],"command":command,"launcherSha256":marker["launcherSha256"],"launchRecordSha256":contracts.sha256_file(start_path),"logSha256":contracts.sha256_file(log),"exitCode":exit_code,"durationSeconds":time.monotonic()-started,"identitySha256":contracts.sha256_file(directory/"identity.json"),"files":{n:contracts.sha256_file(directory/n) for n in ARTIFACTS},"correctness":result["correctness"],"qualityStatus":result["qualityStatus"],"completedUtc":dt.datetime.now(dt.timezone.utc).isoformat()})
                remove_owned(intent,token)
                print(json.dumps({"runId":run_id,"action":"completed","p95":detail["frameP95"],"correctness":result["correctness"]}),flush=True)
            except BaseException as exc:
                if unsafe_to_release:
                    # Preserve uncertain running work; only a timeout above kills its owned process.
                    raise
                contracts.write_json_new(failure,{"runId":run_id,"reason":str(exc),"startupFocus":focus,"pid":None if process is None else process.pid,"exitCode":None if process is None else process.returncode,"durationSeconds":time.monotonic()-started,"planSha256":plan_hash})
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
