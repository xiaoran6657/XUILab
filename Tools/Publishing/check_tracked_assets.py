"""Check the exact small showcase files included in Git; videos remain Release assets."""
import argparse,json
from pathlib import Path
import public_assets as a

def check(root):
    root=Path(root)
    plan_path=a.safe_join(root,'Docs/Showcase/PUBLISHING_INPUTS.json')
    plan=a.read_json(plan_path);a.validate_plan(plan)
    manifest=a.read_json(a.safe_join(root,'Docs/Showcase/Data/showcase-manifest.json'))
    if manifest['inputPlanSha256']!=a.digest(plan_path):raise ValueError('input plan bytes changed')
    projected=[{k:v for k,v in row.items() if k!='source'} for row in plan['files']]
    if manifest['files']!=projected:raise ValueError('showcase manifest selection drift')
    count=0
    for row in plan['files']:
        name=row['path']
        if name.startswith('images/'):target='Docs/Showcase/Media/'+name.removeprefix('images/')
        elif name.startswith('data/'):target='Docs/Showcase/Data/'+name.removeprefix('data/')
        elif name.startswith('videos/'):continue
        else:raise ValueError('unknown asset category')
        path=a.safe_join(root,target)
        if path.stat().st_size!=row['bytes'] or a.digest(path)!=row['sha256']:raise ValueError('tracked asset bytes changed: '+target)
        count+=1
    if count!=15:raise ValueError('15 tracked image/report inputs required')
    return {'status':'pass','trackedInputs':count,'videos':'not_checked; versioned Release assets','unity':'not_run'}

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--root',type=Path,default=Path(__file__).resolve().parents[2]);args=p.parse_args()
    try:print(json.dumps(check(args.root)));return 0
    except (ValueError,OSError,KeyError,TypeError) as exc:print(json.dumps({'status':'fail','error':str(exc)}));return 1
if __name__=='__main__':raise SystemExit(main())
