"""Freeze an exact M2 candidate/evidence closure in a new directory, without Git or Unity."""
from __future__ import annotations
import argparse
import datetime as dt
from pathlib import Path
import shutil
import sys
import gradient_experiment as contracts
from player_launch import tree_files,check_build
from player_verify import read,need,check_gate
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"UnityOperations"))
from operation_journal import local

def freeze(repo,output):
    repo=repo.absolute();output=output.absolute()
    contracts._assert_no_reparse_components(output,"archive destination")
    need(output.is_relative_to(repo/"Artifacts") and not output.exists(),"Destination must be new and inside repository Artifacts")
    base=repo/"Artifacts/gradient-player-r5"
    plan=contracts.validate_plan(read(base/"matrix-plan.json"),require_frozen=True);manifest=read(base/"build-manifest.json")
    check_build(base/"build-manifest.json",base/manifest["player"],plan,repo)
    check_gate(read(repo/"Artifacts/gradient-validation/preflight-r5.json"),plan,repo)
    need(not (repo/"Artifacts/gradient-player.lock").exists(),"Player lock remains; do not snapshot")
    selected=set(manifest["sourceInputs"])
    extras=("player_resume.py","player_matrix_report.py","test_player_resume.py","requirements-plot.txt","historical_verify.py","test_historical_verify.py","freeze_baseline.py")
    selected.update("Tools/GradientLab/"+name for name in extras)
    selected.update(("Docs/Experiments/GRADIENT_MATRIX_RECOVERY-r1.md","Docs/Experiments/GRADIENT_BENCHMARK_RESULTS.md","Docs/Experiments/GRADIENT_LAB_CASE_STUDY.md"))
    roots=("gradient-player-r4","gradient-player-r5","gradient-media-r1","gradient-quality-r1","gradient-quality-r2","gradient-quality-r3","gradient-quality-r4","gradient-quality-reference-r1","gradient-quality-runs","gradient-runner-tests","gradient-validation")
    for name in roots:
        selected.update(f.relative_to(repo).as_posix() for f in tree_files(repo/"Artifacts"/name))
    for directory in (repo/"Artifacts/unity-operations").iterdir():
        contracts._assert_no_reparse_components(directory,"journal")
        request=directory/"request.json"
        if request.is_file() and read(request).get("task","").startswith("M2-"):
            selected.update(f.relative_to(repo).as_posix() for f in tree_files(directory))
    metadata=dict(schemaVersion="xuilab.gradient.historical/v1",recordedRepoRoot=str(repo),createdUtc=dt.datetime.now(dt.timezone.utc).isoformat(),sourceInputs=manifest["sourceInputs"],planPath="Artifacts/gradient-player-r5/matrix-plan.json",gatePath="Artifacts/gradient-validation/preflight-r5.json",buildManifestPath="Artifacts/gradient-player-r5/build-manifest.json",policyPath="Artifacts/gradient-player-r5/resume-policy-r1.json",reportPath="Artifacts/gradient-player-r5/matrix-report-r1/matrix-review.json",runsPath="Artifacts/gradient-player-r5/matrix-runs",files={})
    metadata["prePolicyTimeouts"]={"gradient-matrix-r5-gradient-grid-2000-all-horizontal-25-r1":"b32bd0c6482ca92d538391e35808b267b716fd650137c22afd6296abce35e235"}
    metadata.update({k:plan[k] for k in ("candidateId","buildId","sourceRevision","dirty")})
    output.mkdir(parents=True,exist_ok=False)
    for name in sorted(selected):
        source=local(repo,name);contracts._assert_regular_file(source,name)
        sha=contracts.sha256_file(source)
        if name in manifest["sourceInputs"]:need(sha==manifest["sourceInputs"][name],"Source changed during freeze")
        target=local(output,name);target.parent.mkdir(parents=True,exist_ok=True)
        with source.open("rb") as inp,target.open("xb") as out:shutil.copyfileobj(inp,out)
        need(contracts.sha256_file(target)==sha==contracts.sha256_file(source),"File changed during copy")
        metadata["files"][name]=dict(sha256=sha,size=target.stat().st_size)
    contracts.write_json_new(output/"baseline-manifest.json",metadata)
    return dict(archive=str(output),sourceInputs=len(manifest["sourceInputs"]),files=len(selected),bytes=sum(x["size"] for x in metadata["files"].values()),manifestSha256=contracts.sha256_file(output/"baseline-manifest.json"))

if __name__=="__main__":
    import json
    p=argparse.ArgumentParser(description=__doc__);p.add_argument("--repo",type=Path,default=Path.cwd());p.add_argument("--output",type=Path,required=True);a=p.parse_args()
    print(json.dumps(freeze(a.repo,a.output)))
