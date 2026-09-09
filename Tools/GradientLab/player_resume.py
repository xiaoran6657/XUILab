"""Resume untouched runs in a frozen matrix; retain timeouts and explicit deferrals.

This is a separately hashed orchestration addendum. It never edits the build,
original plan, original launcher, completed runs, or retained failed attempts.
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
import gradient_experiment as contracts
from player_launch import check_build,remove_owned
from player_verify import read,need,check_gate,verify_run


def timeout_record(path,run,plan_hash,root):
    need(not (root/run["runId"]).exists(),"Timeout has conflicting unreceipted output")
    value=read(path)
    need(value.get("runId")==run["runId"] and value.get("planSha256")==plan_hash,"Failure identity mismatch")
    need(value.get("reason")=="Player wall-clock timeout","Non-timeout failure requires investigation")
    need(type(value.get("exitCode")) is int and value["exitCode"]!=0 and type(value.get("pid")) is int and value["pid"]>0,"Failure lacks terminal owned process evidence")
    need(type(value.get("durationSeconds")) in (int,float) and value["durationSeconds"]>=run["timeoutSeconds"],"Timeout duration mismatch")
    contracts._assert_regular_file(root/".logs"/(run["runId"]+".log"),"timeout log")
    return value


def receipt_result(root,run,plan,plan_hash,build_hash,repo,gate,policy_hash):
    run_id=run["runId"];directory=root/run_id;receipt=read(root/".receipts"/(run_id+".json"))
    need(receipt.get("schemaVersion")=="xuilab.gradient.launch-receipt/v1" and receipt.get("runId")==run_id and type(receipt.get("exitCode")) is int and receipt["exitCode"]==0,"Receipt identity/exit mismatch")
    need(receipt.get("planSha256")==plan_hash and receipt.get("buildManifestSha256")==build_hash and receipt.get("identitySha256")==contracts.sha256_file(directory/"identity.json"),"Receipt evidence drift")
    if "resumePolicySha256" in receipt:need(receipt["resumePolicySha256"]==policy_hash,"Receipt resume policy mismatch")
    result,detail=verify_run(directory,plan,run,plan_hash,repo,gate)
    need(receipt.get("qualityStatus")==result["qualityStatus"],"Receipt quality mismatch")
    return result,detail


def inventory(root,plan,plan_hash):
    allowed={".receipts",".logs"};blocked={}
    for run in plan["runs"]:
        rid=run["runId"]
        allowed.update((rid,rid+"-intent.json",rid+"-orchestration-failure.json",rid+"-deferred.json"))
    contracts._assert_no_reparse_components(root,str(root));need(root.is_dir(),"Existing run root required")
    for item in root.iterdir():
        contracts._assert_no_reparse_components(item,str(item));need(item.name in allowed,"Unknown run root artifact")
    ids={r["runId"] for r in plan["runs"]}
    for folder,suffix in ((".receipts",".json"),(".logs",".log")):
        directory=root/folder;contracts._assert_no_reparse_components(directory,str(directory))
        if directory.exists():need({p.name for p in directory.iterdir()}.issubset({rid+suffix for rid in ids}),"Unknown receipt/log")
    for run in plan["runs"]:
        rid=run["runId"];failure=root/(rid+"-orchestration-failure.json")
        need(not (root/(rid+"-intent.json")).exists(),"Unresolved intent: do not redispatch")
        if failure.exists():
            need(not (root/".receipts"/(rid+".json")).exists() and not (root/rid).exists() and not (root/(rid+"-deferred.json")).exists(),"Failure/output/receipt/deferral conflict")
            timeout_record(failure,run,plan_hash,root)
            blocked.setdefault(run["caseId"],(rid,contracts.sha256_file(failure)))
    positions={r["runId"]:i for i,r in enumerate(plan["runs"])}
    for run in plan["runs"]:
        rid=run["runId"]
        if run["caseId"] in blocked and positions[rid]<positions[blocked[run["caseId"]][0]]:
            need((root/".receipts"/(rid+".json")).exists(),"Pending run precedes retained same-case timeout")
    return blocked


def validate_existing(root,plan,plan_hash,build_hash,repo,gate,policy_hash):
    blocked=inventory(root,plan,plan_hash)
    for run in plan["runs"]:
        rid=run["runId"];receipt=root/".receipts"/(rid+".json");failure=root/(rid+"-orchestration-failure.json");deferred=root/(rid+"-deferred.json")
        if receipt.exists():
            need(not deferred.exists(),"Receipt/deferral conflict")
            receipt_result(root,run,plan,plan_hash,build_hash,repo,gate,policy_hash)
        elif failure.exists():timeout_record(failure,run,plan_hash,root)
        else:
            need(not (root/rid).exists() and not (root/".logs"/(rid+".log")).exists(),"Unresolved output without receipt")
            if deferred.exists():
                source,digest=blocked.get(run["caseId"],(None,None))
                expected=dict(schemaVersion="xuilab.gradient.deferred/v1",runId=rid,planSha256=plan_hash,resumePolicySha256=policy_hash,reason="prior_same_case_timeout",sourceFailureRunId=source,sourceFailureSha256=digest)
                need(source is not None and read(deferred)==expected,"Unproven deferral")
    return blocked


def resume(plan_path,root,gate_path,player,build_path,repo,policy_path):
    plan=contracts.validate_plan(read(plan_path),require_frozen=True);gate=read(gate_path);check_gate(gate,plan,repo)
    plan_hash=contracts.sha256_file(plan_path);build_hash=contracts.sha256_file(build_path);gate_hash=contracts.sha256_file(gate_path)
    policy=read(policy_path);policy_hash=contracts.sha256_file(policy_path);driver_hash=contracts.sha256_file(Path(__file__))
    need(policy.get("schemaVersion")=="xuilab.gradient.resume-policy/v1" and policy.get("planSha256")==plan_hash and policy.get("buildManifestSha256")==build_hash and policy.get("driverSha256")==driver_hash,"Resume policy identity mismatch")
    protocol_name=Path(policy["protocolPath"])
    need(not protocol_name.is_absolute() and ".." not in protocol_name.parts,"Unsafe recovery protocol path")
    protocol_path=repo/protocol_name;protocol_hash=contracts.sha256_file(protocol_path)
    need(protocol_hash==policy.get("protocolSha256"),"Recovery protocol hash mismatch")
    need(policy.get("timeoutAction")=="defer-remaining-same-case" and policy.get("otherFailureAction")=="stop" and policy.get("preservePlanOrder") is True,"Unsupported resume policy")
    need(all(r["parameters"]["preflightSha256"]==gate_hash and r["parameters"]["buildManifestSha256"]==build_hash for r in plan["runs"]),"Frozen plan control mismatch")
    token=uuid.uuid4().hex;lock=repo/"Artifacts/gradient-player.lock"
    contracts.write_json_new(lock,dict(schemaVersion="xuilab.gradient.launch-lock/v1",pid=os.getpid(),token=token,resumePolicySha256=policy_hash,createdUtc=dt.datetime.now(dt.timezone.utc).isoformat()))
    try:
        blocked=validate_existing(root,plan,plan_hash,build_hash,repo,gate,policy_hash)
        for run in plan["runs"]:
            need(contracts.sha256_file(plan_path)==plan_hash and contracts.sha256_file(build_path)==build_hash and contracts.sha256_file(gate_path)==gate_hash and contracts.sha256_file(policy_path)==policy_hash and contracts.sha256_file(Path(__file__))==driver_hash and contracts.sha256_file(protocol_path)==protocol_hash,"Resume control drift")
            manifest=check_build(build_path,player,plan,repo);need(manifest["sourceInputs"]==gate["sourceInputs"],"Gate/build source mismatch")
            rid=run["runId"];directory=root/rid;intent=root/(rid+"-intent.json");failure=root/(rid+"-orchestration-failure.json");deferred=root/(rid+"-deferred.json");receipt_path=root/".receipts"/(rid+".json");log=root/".logs"/(rid+".log")
            for path in (directory,intent,failure,deferred,receipt_path,log):contracts._assert_no_reparse_components(path,str(path))
            need(not intent.exists(),"Unresolved dispatch intent")
            if failure.exists():
                timeout_record(failure,run,plan_hash,root);need(not directory.exists() and not receipt_path.exists() and not deferred.exists(),"Conflicting failure/output status")
                print(json.dumps(dict(runId=rid,action="retained_timeout")),flush=True);continue
            if receipt_path.exists():
                need(not deferred.exists(),"Receipt/deferral conflict")
                receipt_result(root,run,plan,plan_hash,build_hash,repo,gate,policy_hash)
                print(json.dumps(dict(runId=rid,action="verified_existing")),flush=True);continue
            need(not directory.exists() and not log.exists(),"Uncertain output without receipt: preserve and investigate")
            if run["caseId"] in blocked:
                source,digest=blocked[run["caseId"]]
                value=dict(schemaVersion="xuilab.gradient.deferred/v1",runId=rid,planSha256=plan_hash,resumePolicySha256=policy_hash,reason="prior_same_case_timeout",sourceFailureRunId=source,sourceFailureSha256=digest)
                if deferred.exists():need(read(deferred)==value,"Deferral drift")
                else:contracts.write_json_new(deferred,value)
                print(json.dumps(dict(runId=rid,action="deferred_after_timeout")),flush=True);continue
            need(not deferred.exists(),"Deferral without a verified timeout")
            log.parent.mkdir(exist_ok=True)
            contracts.write_json_new(intent,dict(schemaVersion="xuilab.gradient.launch-intent/v1",runId=rid,planSha256=plan_hash,buildManifestSha256=build_hash,resumePolicySha256=policy_hash,token=token,ownerPid=os.getpid(),player=str(player),createdUtc=dt.datetime.now(dt.timezone.utc).isoformat()))
            command=[str(player),"-screen-fullscreen","0","-screen-width","960","-screen-height","540","-force-d3d11","-logFile",str(log),"--xuilab-run","--xuilab-run-id",rid,"--xuilab-output-root",str(root),"--gradient-plan",str(plan_path),"--gradient-plan-sha256",plan_hash,"--gradient-preflight",str(gate_path),"--gradient-build-manifest",str(build_path),"--gradient-build-manifest-sha256",build_hash]
            process=None;started=time.monotonic();timed_out=False
            try:
                startup=None
                if hasattr(subprocess,"STARTUPINFO"):
                    startup=subprocess.STARTUPINFO();startup.dwFlags|=subprocess.STARTF_USESHOWWINDOW;startup.wShowWindow=1
                process=subprocess.Popen(command,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,startupinfo=startup)
                try:code=process.wait(timeout=run["timeoutSeconds"])
                except subprocess.TimeoutExpired:
                    timed_out=True
                    if process.poll() is None:process.kill();process.wait(timeout=15)
                    raise RuntimeError("Player wall-clock timeout")
                need(code==0,"Player exit code "+str(code))
                result,detail=verify_run(directory,plan,run,plan_hash,repo,gate)
                contracts.write_json_new(receipt_path,dict(schemaVersion="xuilab.gradient.launch-receipt/v1",runId=rid,planSha256=plan_hash,buildManifestSha256=build_hash,resumePolicySha256=policy_hash,pid=process.pid,exitCode=code,durationSeconds=time.monotonic()-started,identitySha256=contracts.sha256_file(directory/"identity.json"),qualityStatus=result["qualityStatus"],completedUtc=dt.datetime.now(dt.timezone.utc).isoformat()))
                remove_owned(intent,token)
                print(json.dumps(dict(runId=rid,action="completed",p95=detail["frameP95"],qualityStatus=result["qualityStatus"])),flush=True)
            except Exception as exc:
                if process is not None and process.poll() is None:raise
                contracts.write_json_new(failure,dict(runId=rid,reason=str(exc),pid=None if process is None else process.pid,exitCode=None if process is None else process.returncode,durationSeconds=time.monotonic()-started,planSha256=plan_hash,resumePolicySha256=policy_hash))
                remove_owned(intent,token)
                if not timed_out:raise
                timeout_record(failure,run,plan_hash,root);blocked[run["caseId"]]=(rid,contracts.sha256_file(failure))
                print(json.dumps(dict(runId=rid,action="retained_timeout")),flush=True)
    finally:remove_owned(lock,token)


def main():
    p=argparse.ArgumentParser(description=__doc__)
    for name in ("plan","runs","gate","player","build-manifest","policy"):p.add_argument("--"+name,type=Path,required=True)
    p.add_argument("--repo",type=Path,default=Path.cwd());a=p.parse_args()
    resume(a.plan.resolve(),a.runs.absolute(),a.gate.resolve(),a.player.resolve(),a.build_manifest.resolve(),a.repo.resolve(),a.policy.resolve())
if __name__=="__main__":main()
