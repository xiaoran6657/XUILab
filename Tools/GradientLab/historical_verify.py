"""Read-only historical Gradient verification. No Player dispatch or raw path rewriting."""
from __future__ import annotations
import argparse
import json
from pathlib import Path, PureWindowsPath
import statistics
import sys
import gradient_experiment as contracts
from player_launch import tree_files
from player_resume import inventory, receipt_result, timeout_record
from player_verify import check_gate, need, near, quantile, read
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"UnityOperations"))
from operation_journal import Journal, local, timestamp

def recorded_path(value,expected):
    need(isinstance(value,str),"Recorded path absent")
    p=PureWindowsPath(value)
    need(p.is_absolute() and ".." not in p.parts and p==expected,"Recorded native path mismatch")

def build_provenance(root,manifest,plan,recorded_repo):
    journal=Journal(root); operation=manifest["buildOperation"]; directory=journal.directory(operation)
    request=journal.request(operation)
    need(contracts.sha256_file(directory/"request.json")==manifest["buildRequestSha256"],"Build request hash mismatch")
    need(contracts.sha256_file(directory/"terminal.json")==manifest["buildTerminalSha256"],"Build terminal hash mismatch")
    claim=read(directory/"claim.json");receipt=read(directory/"receipt.json");terminal=read(directory/"terminal.json");restore=read(directory/"restore.json")
    need(claim.get("operation")==operation,"Build claim mismatch")
    need(request["kind"]=="build" and request["candidate"]==plan["candidateId"] and request["inputs"]==manifest["sourceInputs"],"Build request provenance mismatch")
    need(journal.inputs_match(request),"Archived build source drift")
    for evidence in (receipt,terminal["evidence"]):
        need(evidence.get("operation")==operation and evidence.get("candidate")==request["candidate"] and evidence.get("instance")==request["instance"],"Build envelope identity mismatch")
        recorded_path(evidence.get("project_root"),recorded_repo/"XUILab");timestamp(evidence.get("observed_at"))
        need(evidence.get("response",{}).get("success") is True and isinstance(evidence["response"].get("data"),dict),"Build native response invalid")
    received=receipt["response"]["data"];native=terminal["evidence"]["response"]["data"]
    need(isinstance(received.get("job_id"),str) and received["job_id"] and native.get("job_id")==received["job_id"],"Build job mismatch")
    need(timestamp(terminal["evidence"]["observed_at"])>=timestamp(receipt["observed_at"]),"Build terminal predates receipt")
    need(native.get("result")=="succeeded" and type(native.get("errors")) is int and native["errors"]==0 and terminal.get("outcome")=="pass","Build did not pass")
    need(native.get("platform")==request["parameters"]["platform"]=="StandaloneWindows64","Build platform mismatch")
    need(timestamp(native.get("completed_at"))<=timestamp(terminal["evidence"]["observed_at"]),"Build completion after observation")
    output=request["artifacts"][0]
    if native.get("output_path")!=output:recorded_path(native.get("output_path"),recorded_repo/PureWindowsPath(output))
    expected={name:contracts.sha256_file(local(root,name)) for name in request["artifacts"]}
    need(terminal.get("artifacts")==expected,"Build terminal artifacts mismatch")
    need(restore.get("operation")==operation,"Build restoration identity mismatch")
    recorded_path(restore.get("project_root"),recorded_repo/"XUILab")
    need(timestamp(restore.get("observed_at"))>timestamp(terminal["evidence"]["observed_at"]),"Restoration predates terminal")
    state=restore.get("state",{})
    need(all(state.get(k)==v for k,v in request["restore_expected"].items()),"Build restoration mismatch")
    need(all(state.get(k) is False for k in ("compiling","importing","tests_running","build_running")) and isinstance(restore.get("raw"),dict) and restore["raw"],"Build restoration not proven idle")
    return output


def archive_tooling(root):
    """Refuse a live verifier or dependencies even when their bytes look familiar."""
    need(Path(__file__).absolute()==root/"Tools/GradientLab/historical_verify.py","Invoke the copied archive verifier, not the live script")
    for name,relative in (("gradient_experiment","Tools/GradientLab/gradient_experiment.py"),("player_launch","Tools/GradientLab/player_launch.py"),("player_resume","Tools/GradientLab/player_resume.py"),("player_verify","Tools/GradientLab/player_verify.py"),("operation_journal","Tools/UnityOperations/operation_journal.py"),("gradient_recovery","Tools/GradientLab/gradient_recovery.py")):
        need(Path(sys.modules[name].__file__).absolute()==root/relative,"Historical dependency loaded outside archive: "+name)


def recovery_order(plan,runs_root):
    """Once a case times out, every later occurrence must be a deferral."""
    timed_out=set()
    for run in plan["runs"]:
        rid=run["runId"];case=run["caseId"]
        failure=runs_root/(rid+"-orchestration-failure.json")
        receipt=runs_root/".receipts"/(rid+".json")
        deferred=runs_root/(rid+"-deferred.json")
        if case in timed_out:
            need(deferred.is_file() and not receipt.exists() and not failure.exists(),"Historical same-case run was executed after timeout")
        if failure.exists():timed_out.add(case)

def timeout_policy(value,path,policy_hash,legacy):
    if "resumePolicySha256" in value:
        need(value["resumePolicySha256"]==policy_hash,"Historical timeout recovery policy mismatch")
    else:
        need(legacy.get(value["runId"])==contracts.sha256_file(path),"Historical timeout has no proven pre-policy identity")

def gate_closure(root,check,recorded_repo):
    gate_evidence=read(local(root,check["terminalPath"]));operation=gate_evidence["operation"];journal=Journal(root);directory=journal.directory(operation)
    request=journal.request(operation)
    need(contracts.sha256_file(directory/"request.json")==check["requestSha256"],"Gate journal request mismatch")
    claim=read(directory/"claim.json");receipt=read(directory/"receipt.json");terminal=read(directory/"terminal.json");restore=read(directory/"restore.json")
    need(claim.get("operation")==operation and terminal.get("outcome")=="pass" and terminal.get("evidence")==gate_evidence,"Gate journal terminal/claim mismatch")
    for envelope in (receipt,gate_evidence):
        need(envelope.get("operation")==operation and envelope.get("instance")==request["instance"] and envelope.get("candidate")==request["candidate"],"Gate envelope identity mismatch")
        recorded_path(envelope.get("project_root"),recorded_repo/"XUILab")
        need(envelope.get("response",{}).get("success") is True,"Gate native response invalid")
        timestamp(envelope.get("observed_at"))
    received=receipt["response"]["data"];native=gate_evidence["response"]["data"]
    need(isinstance(received.get("job_id"),str) and received["job_id"] and native.get("job_id")==received["job_id"],"Gate job mismatch")
    need(timestamp(gate_evidence["observed_at"])>=timestamp(receipt["observed_at"]),"Gate terminal predates receipt")
    need(native.get("status")=="succeeded" and native.get("mode")==request["parameters"]["mode"] and type(native.get("finished_unix_ms")) is int and native["finished_unix_ms"]>0,"Gate native terminal mismatch")
    need(terminal.get("artifacts")=={name:contracts.sha256_file(local(root,name)) for name in request["artifacts"]},"Gate artifact mismatch")
    need(restore.get("operation")==operation,"Gate restoration identity mismatch");recorded_path(restore.get("project_root"),recorded_repo/"XUILab")
    need(timestamp(restore.get("observed_at"))>timestamp(gate_evidence["observed_at"]),"Gate restoration predates terminal")
    state=restore.get("state",{})
    need(all(state.get(k)==v for k,v in request["restore_expected"].items()),"Gate restoration mismatch")
    need(all(state.get(k) is False for k in ("compiling","importing","tests_running","build_running")) and isinstance(restore.get("raw"),dict) and restore["raw"],"Gate restoration not proven idle")
    # Only the explicit unchanged semantic source scope is carried forward.
    # Old full request inputs may belong to an older candidate; check_gate binds the scope.

def verify(root, expected_manifest_sha256):
    root=root.absolute()
    archive_tooling(root)
    need(isinstance(expected_manifest_sha256,str) and len(expected_manifest_sha256)==64 and contracts.sha256_file(root/"baseline-manifest.json")==expected_manifest_sha256.lower(),"External archive manifest SHA mismatch")
    metadata=read(root/"baseline-manifest.json")
    need(metadata.get("schemaVersion")=="xuilab.gradient.historical/v1","Unknown archive schema")
    recorded_repo=PureWindowsPath(metadata["recordedRepoRoot"])
    need(recorded_repo.is_absolute() and ".." not in recorded_repo.parts,"Invalid recorded repository path")
    files=metadata["files"];actual={f.relative_to(root).as_posix() for f in tree_files(root)}-{"baseline-manifest.json"}
    need(actual==set(files),"Archive contains missing or undeclared files")
    for name,entry in files.items():
        item=local(root,name)
        need(type(entry["size"]) is int and entry["size"]>=0 and item.stat().st_size==entry["size"] and contracts.sha256_file(item)==entry["sha256"],f"Archive payload drift: {name}")
    paths={k:local(root,metadata[k]) for k in ("planPath","gatePath","buildManifestPath","policyPath","reportPath","runsPath")}
    plan=contracts.validate_plan(read(paths["planPath"]),require_frozen=True)
    gate=read(paths["gatePath"]);manifest=read(paths["buildManifestPath"]);policy=read(paths["policyPath"]);report=read(paths["reportPath"])
    for key in ("candidateId","buildId","sourceRevision","dirty"):need(manifest[key]==plan[key]==metadata[key]==report[key],f"Historical identity mismatch: {key}")
    need(manifest["schemaVersion"]=="xuilab.gradient.build/v1" and metadata["sourceInputs"]==manifest["sourceInputs"]==gate["sourceInputs"],"Historical source inventory mismatch")
    sources={f.relative_to(root).as_posix() for folder in ("XUILab/Assets","XUILab/Packages","XUILab/ProjectSettings") for f in tree_files(root/folder)}
    need(sources=={name for name in manifest["sourceInputs"] if name.startswith(("XUILab/Assets/","XUILab/Packages/","XUILab/ProjectSettings/"))},"Historical Unity source set mismatch")
    base=paths["buildManifestPath"].parent;player=local(base,manifest["player"])
    need(player.parent!=base and base in player.parents,"Build has no dedicated directory")
    build_files={f.relative_to(base).as_posix() for f in tree_files(player.parent)}
    need(build_files==set(manifest["files"]) and manifest["player"] in build_files,"Historical build tree mismatch")
    for name,sha in manifest["files"].items():need(contracts.sha256_file(local(base,name))==sha,"Historical build payload drift")
    output=build_provenance(root,manifest,plan,recorded_repo)
    need(local(root,output)==player,"Historical build output does not identify archived Player")
    check_gate(gate,plan,root)
    for check in gate["checks"]:gate_closure(root,check,recorded_repo)
    plan_hash=contracts.sha256_file(paths["planPath"]);build_hash=contracts.sha256_file(paths["buildManifestPath"]);gate_hash=contracts.sha256_file(paths["gatePath"]);policy_hash=contracts.sha256_file(paths["policyPath"])
    need(policy["planSha256"]==report["planSha256"]==plan_hash and policy["buildManifestSha256"]==report["buildManifestSha256"]==build_hash and report["resumePolicySha256"]==policy_hash,"Historical plan/policy/report binding mismatch")
    need(policy["driverSha256"]==contracts.sha256_file(root/"Tools/GradientLab/player_resume.py") and policy["protocolSha256"]==contracts.sha256_file(local(root,policy["protocolPath"])),"Historical recovery driver drift")
    need(report["reportToolSha256"]==contracts.sha256_file(root/"Tools/GradientLab/player_matrix_report.py"),"Historical report tool drift")
    need(all(r["parameters"]["preflightSha256"]==gate_hash and r["parameters"]["buildManifestSha256"]==build_hash for r in plan["runs"]),"Historical run control mismatch")
    runs_root=paths["runsPath"];blocked=inventory(runs_root,plan,plan_hash)
    recovery_order(plan,runs_root)
    need([r["runId"] for r in report["runs"]]==[r["runId"] for r in plan["runs"]],"Historical report run set/order mismatch")
    counts=dict(completed=0,timeout=0,deferred=0,not_run=0);environment=None
    for run,row in zip(plan["runs"],report["runs"]):
        rid=run["runId"]
        for key in ("groupId","caseId","runIndex","plannedRepeatCount"):need(row[key]==run[key],"Historical report run identity mismatch")
        directory=runs_root/rid;failure=runs_root/(rid+"-orchestration-failure.json");deferred=runs_root/(rid+"-deferred.json");receipt=runs_root/".receipts"/(rid+".json")
        if receipt.exists():
            need(not failure.exists() and not deferred.exists(),"Conflicting historical terminal states")
            result,detail=receipt_result(runs_root,run,plan,plan_hash,build_hash,root,gate,policy_hash)
            need(row["state"]=="completed" and row["correctness"]=="pass" and row["measurementValidity"]=="valid" and row["qualityStatus"]==result["qualityStatus"],"Historical accepted run mismatch")
            if environment is None:environment=detail["environment"]
            need(detail["environment"]==environment==report["environment"],"Historical cross-run environment mismatch")
            summary=read(directory/"summary.json");metrics=read(directory/"gradient-metrics.json")
            values=dict(p50=detail["frameP50"],p95=detail["frameP95"],p99=detail["frameP99"],maximum=summary["maxFrameIntervalMs"],overBudgetRatio=summary["overBudgetRatio"],qualityMaxError=detail["quality"]["maxError"],quantizationMaxError=detail["quality"]["quantizationMaxError"],componentDirtyTotal=metrics["totalDirty"],componentRebuildTotal=metrics["totalRebuild"],visibleVertices=run["parameters"]["visibleCount"]*run["parameters"]["expectedVertices"])
            for key,value in values.items():near(row[key],value,1e-10,f"Historical report metric mismatch: {key}")
            for key in ("meanMainThreadNanoseconds","totalGcAllocatedBytes","lastSystemUsedMemoryBytes"):need(row[key]==summary[key],"Historical missing metric changed")
        elif failure.exists():
            need(not deferred.exists(),"Historical timeout/deferral conflict");value=timeout_record(failure,run,plan_hash,runs_root)
            timeout_policy(value,failure,policy_hash,metadata["prePolicyTimeouts"])
            need(row["state"]=="timeout" and row["correctness"]=="unknown" and row["measurementValidity"]=="invalid" and row["qualityStatus"]=="unavailable" and row["failure"]==read(failure),"Historical timeout report mismatch")
        elif deferred.exists():
            need(not directory.exists() and not (runs_root/".logs"/(rid+".log")).exists(),"Historical deferral contains output")
            source,digest=blocked.get(run["caseId"],(None,None))
            expected=dict(schemaVersion="xuilab.gradient.deferred/v1",runId=rid,planSha256=plan_hash,resumePolicySha256=policy_hash,reason="prior_same_case_timeout",sourceFailureRunId=source,sourceFailureSha256=digest)
            need(source is not None and read(deferred)==expected and row["state"]=="deferred" and row["sourceFailureRunId"]==source and all(row[k]=="not_run" for k in ("correctness","measurementValidity","qualityStatus")),"Historical deferral mismatch")
        else:raise ValueError("Unresolved historical run; snapshot is not closed")
        counts[row["state"]]+=1
    need(counts==report["counts"],"Historical report totals mismatch")
    groups={}
    for row in report["runs"]:groups.setdefault(row["groupId"],[]).append(row)
    need([g["groupId"] for g in report["groups"]]==list(groups),"Historical report group set/order mismatch")
    complete_groups=0
    for group in report["groups"]:
        rows=groups[group["groupId"]];planned=next(r for r in plan["runs"] if r["groupId"]==group["groupId"]);good=[r for r in rows if r["state"]=="completed"];complete=len(good)==planned["plannedRepeatCount"]
        need(group["runs"]==rows and group["parameters"]==planned["parameters"] and group["expectedRuns"]==planned["plannedRepeatCount"] and group["verifiedRuns"]==len(good) and group["complete"] is complete,"Historical report group mismatch")
        quality="pass" if good and all(r["qualityStatus"]=="pass" for r in good) else "quality_limited" if good else "unavailable"
        need(group["qualityStatus"]==quality,"Historical group quality mismatch")
        if not complete:
            need("statistics" not in group,"Incomplete historical group has statistics");continue
        complete_groups+=1
        for metric in ("p50","p95","p99","maximum","overBudgetRatio"):
            values=[r[metric] for r in good];median=statistics.median(values)
            expected=dict(median=median,minimum=min(values),maximum=max(values),mad=statistics.median(abs(v-median) for v in values),iqr=quantile(values,.75)-quantile(values,.25))
            need(group["statistics"][metric]==expected,"Historical group statistics mismatch")
    need(report["completeGroups"]==complete_groups and report["status"]==("complete" if counts["completed"]==len(plan["runs"]) else "partial"),"Historical complete/partial status mismatch")
    return dict(schemaVersion="xuilab.gradient.historical-verification/v1",integrity="pass",correctness="pass_for_completed_runs",matrixStatus=report["status"],counts=counts,completeGroups=complete_groups,candidateId=plan["candidateId"],archiveManifestSha256=contracts.sha256_file(root/"baseline-manifest.json"),verifierSha256=contracts.sha256_file(Path(__file__)),limitation="Historical recorded evidence only; no new Player execution or current workspace acceptance")

def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument("--archive",type=Path,required=True);parser.add_argument("--output",type=Path);parser.add_argument("--manifest-sha256",required=True);args=parser.parse_args()
    result=verify(args.archive,args.manifest_sha256)
    if args.output:
        need(not args.output.absolute().is_relative_to(args.archive.resolve()),"Verification output must be outside frozen archive")
        contracts.write_json_new(args.output,result)
    print(json.dumps(result));return 0

if __name__=="__main__":raise SystemExit(main())
