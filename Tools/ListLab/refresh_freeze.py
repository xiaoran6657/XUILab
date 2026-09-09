"""Freeze List refresh historical evidence without rewriting recorded paths."""
import argparse,datetime as dt,json,shutil
from pathlib import Path
from refresh_launch import tree_files,check_build,contracts
from refresh_verify import read,need,check_gate


def freeze(repo,out):
    repo=repo.resolve();out=out.absolute();contracts._assert_no_reparse_components(out,str(out))
    need(out.is_relative_to(repo/'Artifacts') and not out.exists(),'New archive must be inside Artifacts')
    base=repo/'Artifacts/list-refresh-player-r4';plan=read(base/'matrix-r4.json');build=read(base/'build-manifest.json')
    check_build(base/'build-manifest.json',base/build['player'],plan,repo)
    check_gate(read(repo/'Artifacts/list-refresh-validation/preflight-r3.json'),plan,repo)
    need(not (repo/'Artifacts/list-refresh-player.lock').exists(),'Unresolved Player lock')
    selected=set(build['sourceInputs'])
    for folder in ('Tools','Docs'):
        for f in tree_files(repo/folder):
            rel=f.relative_to(repo).as_posix()
            if '/__pycache__/' not in rel and f.suffix!='.pyc' and not rel.startswith('Docs/References/'):
                selected.add(rel)
    for folder in ('list-refresh-player-r3','list-refresh-player-r4','list-refresh-validation','list-refresh-test-runs','list-refresh-negative-fixtures','list-refresh-trace-r1'):
        selected.update(f.relative_to(repo).as_posix() for f in tree_files(repo/'Artifacts'/folder))
    for directory in (repo/'Artifacts/unity-operations').iterdir():
        contracts._assert_no_reparse_components(directory,str(directory))
        q=directory/'request.json'
        if q.is_file() and read(q).get('task','').startswith(('M3-L','M2-')):
            selected.update(f.relative_to(repo).as_posix() for f in tree_files(directory))
    selected.update(('README.md','AGENTS.md','.gitignore','.gitattributes'))
    metadata=dict(schemaVersion='xuilab.list-refresh.historical/v1',recordedRepoRoot=str(repo),createdUtc=dt.datetime.now(dt.timezone.utc).isoformat(),sourceInputs=build['sourceInputs'],files={})
    metadata.update({k:plan[k] for k in ('candidateId','buildId','sourceRevision','dirty')})
    out.mkdir(parents=True,exist_ok=False)
    for name in sorted(selected):
        source=repo/name;contracts._assert_regular_file(source,name);h=contracts.sha256_file(source)
        if name in build['sourceInputs']:need(h==build['sourceInputs'][name],'Frozen source drift: '+name)
        target=out/name;target.parent.mkdir(parents=True,exist_ok=True)
        with source.open('rb') as inp,target.open('xb') as dest:shutil.copyfileobj(inp,dest)
        need(contracts.sha256_file(target)==h==contracts.sha256_file(source),'Copy/source drift: '+name)
        metadata['files'][name]=dict(sha256=h,size=target.stat().st_size)
    contracts.write_json_new(out/'baseline-manifest.json',metadata)
    return dict(archive=str(out),files=len(selected),sourceInputs=len(build['sourceInputs']),bytes=sum(v['size'] for v in metadata['files'].values()),manifestSha256=contracts.sha256_file(out/'baseline-manifest.json'))

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--repo',type=Path,default=Path.cwd());p.add_argument('--output',type=Path,required=True);a=p.parse_args();print(json.dumps(freeze(a.repo,a.output)))
