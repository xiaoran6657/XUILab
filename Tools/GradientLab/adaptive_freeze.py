"""Copy the closed G2 source/evidence set into a new immutable archive."""
import argparse,datetime as dt,json,shutil
from pathlib import Path
import gradient_experiment as contracts
from adaptive_verify import read,need,check_gate
from adaptive_launch import tree_files,check_build
from adaptive_recovery import validate_policy

def freeze(repo,output):
    repo=repo.resolve();output=output.absolute();contracts._assert_no_reparse_components(output,"Archive destination")
    need(output.is_relative_to(repo/"Artifacts/baselines") and not output.exists(),"New archive must be inside Artifacts/baselines")
    base=repo/"Artifacts/gradient-adaptive-player-r1";plan_path=base/"matrix-plan-r1.json";plan=read(plan_path)
    gate_path=repo/"Artifacts/gradient-adaptive-validation/preflight-r1.json";build_path=base/"build-manifest.json";build=read(build_path)
    check_build(build_path,base/build["player"],plan,repo);check_gate(read(gate_path),plan,repo)
    policy_path=base/"matrix-policy-recovery2.json";policy=read(policy_path)
    validate_policy(policy_path,plan,plan_path,gate_path,build_path,repo,repo/policy["runRoot"])
    report=read(base/"matrix-report-r1.json")
    need(report["status"]=="pass" and report["runCount"]==80 and report["dispatchPolicySha256"]==contracts.sha256_file(policy_path),"Complete bound report required")
    need(not (repo/"Artifacts/gradient-player.lock").exists(),"Unresolved Player lock")
    selected=set(build["sourceInputs"])
    def include(directory):
        for p in tree_files(directory):
            name=p.relative_to(repo).as_posix()
            if not name.startswith("Docs/References/") and "/__pycache__/" not in name and "/.matplotlib-cache/" not in name and p.suffix!=".pyc":selected.add(name)
    for folder in ("Tools","Docs"):include(repo/folder)
    for folder in ("Artifacts/gradient-adaptive-player-r1","Artifacts/gradient-adaptive-validation","Artifacts/gradient-runner-tests","Artifacts/gradient-quality-runs/20260908T0722306794804Z-d0af911b7d424ae1ac9b6a7f45ae0d32"):include(repo/folder)
    for directory in (repo/"Artifacts/unity-operations").iterdir():
        contracts._assert_no_reparse_components(directory,"Journal directory");request=directory/"request.json"
        if request.is_file() and read(request).get("task")=="M3-G2":include(directory)
    selected.update(("README.md","AGENTS.md",".gitignore",".gitattributes"))
    metadata=dict(schemaVersion="xuilab.gradient.adaptive-historical/v1",recordedRepoRoot=str(repo),createdUtc=dt.datetime.now(dt.timezone.utc).isoformat(),sourceInputs=build["sourceInputs"],policyPath=policy_path.relative_to(repo).as_posix(),files={})
    metadata.update({k:plan[k] for k in ("candidateId","buildId","sourceRevision","dirty")})
    output.mkdir(parents=True,exist_ok=False)
    for name in sorted(selected):
        source=repo/name;contracts._assert_regular_file(source,name);h=contracts.sha256_file(source)
        if name in build["sourceInputs"]:need(h==build["sourceInputs"][name],"Frozen source drift: "+name)
        target=output/name;target.parent.mkdir(parents=True,exist_ok=True)
        with source.open("rb") as inp,target.open("xb") as out:shutil.copyfileobj(inp,out)
        need(contracts.sha256_file(target)==h==contracts.sha256_file(source),"Copy/source drift: "+name)
        metadata["files"][name]=dict(sha256=h,size=target.stat().st_size)
    contracts.write_json_new(output/"baseline-manifest.json",metadata)
    return dict(archive=str(output),files=len(selected),sourceInputs=len(build["sourceInputs"]),bytes=sum(v["size"] for v in metadata["files"].values()),manifestSha256=contracts.sha256_file(output/"baseline-manifest.json"))

if __name__=="__main__":
    p=argparse.ArgumentParser(description=__doc__);p.add_argument("--repo",type=Path,default=Path.cwd());p.add_argument("--output",type=Path,required=True);a=p.parse_args();print(json.dumps(freeze(a.repo,a.output)))
