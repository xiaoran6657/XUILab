"""Publish selected historical raw data and recalculate frame statistics without Unity.

Config outputDirectory alone is redacted; original identity hashes are retained and
mapped to original/export hashes. This is not a replacement for the original
receipt, full quality verifier, or a new performance run.
"""
from __future__ import annotations
import argparse,csv,io,json,math,re,statistics
from pathlib import Path
import public_assets as assets

REDACTED='[local output directory omitted]'
COMMON=('config.json','environment.json','identity.json','samples.csv','summary.json')
LIST=('refresh-metrics.json','refresh-samples.csv')
GRADIENT=('gradient-metrics.json','gradient-mesh.json','gradient-samples.csv','quality-scan.csv','quality.json','selection-samples.csv')

def quantile(values,q):
    values=sorted(values)
    if not values:raise ValueError('empty samples')
    x=(len(values)-1)*q;lo=int(x);hi=min(lo+1,len(values)-1)
    return values[lo]+(values[hi]-values[lo])*(x-lo)

def measure(directory, expected, kind):
    config=assets.read_json(directory/'config.json');summary=assets.read_json(directory/'summary.json');identity=assets.read_json(directory/'identity.json')
    rid=expected['runId']
    if any(d.get('runId')!=rid for d in (config,summary,identity)):raise ValueError('run identity mismatch')
    if config['candidateId']!='m4-final-b017672' or config['warmupFrames']!=300 or config['measureFrames']!=1800:
        raise ValueError('protocol mismatch')
    revision='b0176724d58c7cda86b472340845d239714888d0'
    if any(d.get('sourceRevision') != revision or d.get('dirty') is not False or d.get('candidateId') != 'm4-final-b017672' for d in (config,identity)):
        raise ValueError('historical source identity mismatch')
    if config.get('buildId') != identity.get('buildId') or config.get('buildId') != expected['expectedBuildId'] or config.get('caseId') != expected['expectedCaseId']:
        raise ValueError('build identity mismatch')
    if summary.get('state','').lower() != 'completed' or summary.get('exitCode') != 0 or summary.get('processSuccess') is not True:
        raise ValueError('unsuccessful terminal')
    if summary['correctness'].lower()!='pass' or summary['measurementValidity'].lower()!='valid' or not summary['processSuccess']:
        raise ValueError('invalid historical run')
    with (directory/'samples.csv').open(encoding='utf-8-sig',newline='') as f:rows=list(csv.DictReader(f))
    if len(rows)!=1800 or summary['sampleCount']!=1800:raise ValueError('sample count mismatch')
    values=[]
    for i,row in enumerate(rows):
        if int(row['sample_index'])!=i:raise ValueError('sample sequence mismatch')
        value=float(row['frame_interval_ms'])
        if not math.isfinite(value) or value<0:raise ValueError('invalid frame interval')
        values.append(value)
    out={}
    for q,key in ((.5,'p50'),(.95,'p95'),(.99,'p99')):
        value=quantile(values,q);report_key='frame'+key.upper()+'Ms' if kind=='list' else key
        if not math.isclose(value,expected[report_key],rel_tol=1e-7,abs_tol=1e-7):raise ValueError('report quantile mismatch: '+rid)
        if not math.isclose(value,summary[key+'FrameIntervalMs'],rel_tol=1e-7,abs_tol=1e-7):raise ValueError('summary quantile mismatch: '+rid)
        out[key]=value
    return out

def reports(root):
    result=[]
    for kind in ('list','gradient'):
        report=assets.read_json(root/'Docs/Showcase/Data'/f'{kind}-report.json')
        runs=report['runs']
        if len(runs)!=(50 if kind=='list' else 80):raise ValueError('report run count mismatch')
        shared=report['identity'] if kind=='list' else report
        for r in runs:
            row=dict(r);row['expectedBuildId']=shared['buildId']
            row['expectedCaseId']=r['caseId'] if kind=='list' else 'gradient-adaptive-'+r['scenario']+'-'+r['variant']
            result.append((kind,row))
    if len({r['runId'] for _,r in result})!=130:raise ValueError('duplicate run ID')
    return result

def export(root,output):
    root=Path(root).absolute();output=Path(output).absolute()
    if output.exists():raise ValueError('output must be new')
    entries=re.findall(r'\[([^\]]+)\]\(\.\./\.\./(Artifacts/[^)]+)/\)',(root/'Docs/Showcase/RUN_INDEX.md').read_text(encoding='utf-8'))
    mapping=dict(entries)
    if len(entries)!=130 or len(mapping)!=130:raise ValueError('run index is not exactly 130 unique entries')
    prepared=[];run_records=[]
    for kind,row in reports(root):
        rid=row['runId']
        if not re.fullmatch('[A-Za-z0-9._-]+',rid):raise ValueError('unsafe run ID')
        directory=assets.safe_join(root,mapping[rid]);measure(directory,row,kind)
        config_hash=assets.digest(directory/'config.json')
        identity=assets.read_json(directory/'identity.json')
        if identity['configSha256'].lower()!=config_hash:raise ValueError('original config hash mismatch')
        receipt_path=assets.safe_join(root,str(Path(mapping[rid]).parent.as_posix())+'/.receipts/'+rid+'.json')
        receipt=assets.read_json(receipt_path)
        if receipt.get('runId') != rid or receipt.get('exitCode') != 0:raise ValueError('receipt identity/terminal mismatch')
        quantiles=measure(directory,row,kind)
        run_records.append({'runId':rid,'kind':kind,'expected':row,'quantiles':quantiles,'originalReceiptSha256':assets.digest(receipt_path)})
        for name in COMMON+(LIST if kind=='list' else GRADIENT):
            source=assets.safe_join(root,mapping[rid]+'/'+name);content=source.read_bytes();original_hash=assets.digest(source)
            if receipt['files'].get(name,'').lower()!=original_hash:raise ValueError('original receipt file hash mismatch')
            transformation='none'
            if name=='config.json':
                config=assets.read_json(source);config['outputDirectory']=REDACTED
                content=(json.dumps(config,ensure_ascii=False,indent=2)+'\n').encode('utf-8');transformation='outputDirectory redacted; JSON reserialized'
            path=f'runs/{rid}/{name}';assets.safe_join(output,path)
            prepared.append((path,content,original_hash,transformation))
    output.mkdir(parents=True)
    import hashlib
    files=[]
    for path,content,original_hash,transformation in prepared:
        target=assets.safe_join(output,path);target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(content);assets.inspect_text(target)
        files.append({'path':path,'sha256':hashlib.sha256(content).hexdigest(),'bytes':len(content),'originalSha256':original_hash,'transformation':transformation})
    manifest={'schema':assets.SCHEMA,'candidate':'m4-final-b017672','scope':'Historical selected raw evidence. Original logs, receipts, paths and full build are omitted. Only outputDirectory is redacted from config; original hash mappings retained. Frame statistics rechecked; not new Unity runs or full quality revalidation.','files':files,'runs':run_records}
    (output/'manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    return verify(output)

def verify(root, expected_manifest_sha256=None):
    root=Path(root);integrity=assets.verify(root,expected_manifest_sha256);manifest=assets.read_json(root/'manifest.json')
    if len(manifest['runs'])!=130 or len({r['runId'] for r in manifest['runs']})!=130:raise ValueError('130 unique runs required')
    for run in manifest['runs']:
        directory=assets.safe_join(root,'runs/'+run['runId']);measure(directory,run['expected'],run['kind'])
        item=next(f for f in manifest['files'] if f['path']==f"runs/{run['runId']}/config.json")
        if assets.read_json(directory/'identity.json')['configSha256'].lower()!=item['originalSha256']:raise ValueError('original hash mapping mismatch')
        if assets.read_json(directory/'config.json')['outputDirectory']!=REDACTED:raise ValueError('config was not redacted')
    return {**integrity,'runs':130,'frameStatistics':'pass','unity':'not_run','fullOriginalReceiptValidation':'not_run'}

def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('command',choices=('export','verify'));parser.add_argument('--root',type=Path,required=True);parser.add_argument('--output',type=Path);parser.add_argument('--expected-manifest-sha256');a=parser.parse_args()
    try:
        if a.command=='export' and a.output is None:raise ValueError('--output required')
        if a.command=='verify' and a.expected_manifest_sha256 is None:raise ValueError('--expected-manifest-sha256 required')
        print(json.dumps(export(a.root,a.output) if a.command=='export' else verify(a.root,a.expected_manifest_sha256)));return 0
    except (ValueError,OSError,KeyError,TypeError) as e:
        print(json.dumps({'status':'fail','error':str(e)}));return 1
if __name__=='__main__':raise SystemExit(main())
