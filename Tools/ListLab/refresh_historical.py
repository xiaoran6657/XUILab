"""Verify copied List refresh evidence using its recorded repository identity."""
import argparse,json,statistics,sys
from pathlib import Path,PureWindowsPath
from refresh_launch import tree_files,contracts
from refresh_verify import read,need,verify_run,check_gate
from refresh_plan import validate_plan,ARTIFACTS
from refresh_acceptance import tree_contract,complete_test_details
from historical_verify import build_provenance,gate_closure


def verify(root,expected):
    root=root.absolute()
    need(Path(__file__).absolute()==root/'Tools/ListLab/refresh_historical.py','Invoke archived verifier')
    for module,relative in [('refresh_launch','Tools/ListLab/refresh_launch.py'),('refresh_verify','Tools/ListLab/refresh_verify.py'),('refresh_plan','Tools/ListLab/refresh_plan.py'),('refresh_acceptance','Tools/ListLab/refresh_acceptance.py'),('historical_verify','Tools/GradientLab/historical_verify.py'),('gradient_experiment','Tools/GradientLab/gradient_experiment.py'),('operation_journal','Tools/UnityOperations/operation_journal.py')]:
        need(Path(sys.modules[module].__file__).absolute()==root/relative,'Dependency outside archive: '+module)
    sha=contracts.sha256_file
    need(sha(root/'baseline-manifest.json')==expected,'External archive manifest hash')
    metadata=read(root/'baseline-manifest.json');need(metadata['schemaVersion']=='xuilab.list-refresh.historical/v1','Archive schema')
    recorded=PureWindowsPath(metadata['recordedRepoRoot']);need(recorded.is_absolute() and '..' not in recorded.parts,'Recorded root')
    files=metadata['files'];actual={f.relative_to(root).as_posix() for f in tree_files(root)}-{'baseline-manifest.json'}
    need(actual==set(files),'Missing or extra archive files')
    for name,value in files.items():
        need(not Path(name).is_absolute() and '..' not in Path(name).parts,'Unsafe archive member')
        need((root/name).stat().st_size==value['size'] and sha(root/name)==value['sha256'],'Archive payload drift: '+name)
    base=root/'Artifacts/list-refresh-player-r4';build=read(base/'build-manifest.json');gate=read(root/'Artifacts/list-refresh-validation/preflight-r3.json')
    need(build['schemaVersion']=='xuilab.list-refresh.build/v1' and build['sourceInputs']==metadata['sourceInputs']==gate['sourceInputs'],'Build source scope')
    for name,digest in build['sourceInputs'].items():need(sha(root/name)==digest,'Source drift')
    need({f.relative_to(base).as_posix() for f in tree_files(base/'build')}==set(build['files']),'Build tree set')
    for name,digest in build['files'].items():need(sha(base/name)==digest,'Build file drift')
    output={}
    for kind in ('matrix','pilot'):
        plan_path=base/(kind+'-r4.json');plan=validate_plan(read(plan_path),require_frozen=True);runs=base/(kind+'-runs');ph=sha(plan_path);bh=sha(base/'build-manifest.json')
        for key in ('candidateId','buildId','sourceRevision','dirty'):need(plan[key]==build[key]==metadata[key],'Candidate identity')
        check_gate(gate,plan,root);tests=complete_test_details(gate,root);tree_contract(runs,plan)
        need(not (root/'Artifacts/list-refresh-player.lock').exists(),'Player lock retained')
        if kind=='matrix':
            build_provenance(root,build,plan,recorded)
            for check in gate['checks']:
                # Export and journal serialize identical JSON differently. check_gate has
                # already verified the exported bytes and operation digest; retain both.
                envelope=read(root/check['terminalPath'])
                journal_request=root/'Artifacts/unity-operations'/envelope['operation']/'request.json'
                need(read(journal_request)==read(root/check['requestPath']),'Export/journal request differs')
                closure_check=dict(check,requestSha256=sha(journal_request))
                gate_closure(root,closure_check,recorded)
        saved=read(base/(kind+'-verification-r1.json'));supplement=read(base/(kind+'-supplement-r2.json'))
        need(saved['status']==supplement['status']=='pass' and saved['planSha256']==supplement['planSha256']==ph,'Saved verification identity')
        need(len(saved['details'])==len(supplement['runs'])==len(plan['runs']) and not saved['failures'],'Saved verification count')
        byid={d['runId']:d for d in saved['details']};sr={d['runId']:d for d in supplement['runs']};details=[]
        need(set(byid)==set(sr)=={r['runId'] for r in plan['runs']},'Saved run set')
        for run in plan['runs']:
            name=run['runId'];directory=runs/name;receipt=runs/'.receipts'/(name+'.json');log=runs/'.logs'/(name+'.log');r=read(receipt)
            need(run['parameters']['buildManifestSha256']==bh and run['parameters']['preflightSha256']==sha(root/'Artifacts/list-refresh-validation/preflight-r3.json'),'Plan controls')
            result,detail=verify_run(directory,plan,run,ph,root,gate);details.append(detail)
            need(detail==byid[name],'Saved raw recomputation differs')
            need(r['schemaVersion']=='xuilab.list-refresh.launch-receipt/v1' and r['runId']==name,'Receipt schema/run')
            need(type(r['pid']) is int and r['pid']>0 and type(r['exitCode']) is int and r['exitCode']==0 and r['correctness']=='pass','Receipt process/outcome')
            need(r['planSha256']==ph and r['buildManifestSha256']==bh and 0<r['durationSeconds']<=run['timeoutSeconds']+15,'Receipt control/duration')
            need(r['identitySha256']==sha(directory/'identity.json') and r['files']=={n:sha(directory/n) for n in ARTIFACTS},'Receipt raw binding')
            need(log.stat().st_size>0 and sr[name]==dict(runId=name,pid=r['pid'],exitCode=0,receiptSha256=sha(receipt),logSha256=sha(log),identitySha256=r['identitySha256']),'Supplement receipt/log binding')
        for d in details:
            for key in ('operatingSystem','processorType','processorCount','graphicsDeviceName','graphicsDeviceVersion'):need(d['environment'][key]==details[0]['environment'][key],'Machine drift')
        comparisons=[]
        for group in sorted({r['groupId'] for r in plan['runs']}):
            members=sorted([r for r in plan['runs'] if r['groupId']==group],key=lambda r:r['runIndex'])
            a=[byid[r['runId']]['frameP95'] for r in members if r['variant']=='window'];b=[byid[r['runId']]['frameP95'] for r in members if r['variant']=='target']
            threshold=max(.05*statistics.median(a),.5*max(max(a)-min(a),max(b)-min(b)));delta=statistics.median(b)-statistics.median(a)
            decision='improved' if len(a)==5 and sum(y<x for x,y in zip(a,b))>=4 and delta < -threshold else 'regressed' if len(a)==5 and sum(y>x for x,y in zip(a,b))>=4 and delta>threshold else 'inconclusive'
            comparisons.append(dict(group=group,windowP95=a,targetP95=b,medianDifference=delta,threshold=threshold,result=decision))
        need(comparisons==saved['comparisons'],'Saved comparison differs')
        output[kind]=dict(runs=len(details),tests=tests,comparisons={k:sum(c['result']==k for c in comparisons) for k in ('improved','regressed','inconclusive')})
    return dict(schemaVersion='xuilab.list-refresh.historical-verification/v1',integrity='pass',correctness='pass',candidateId=metadata['candidateId'],archiveManifestSha256=expected,verifierSha256=sha(Path(__file__)),results=output,limitation='Historical recorded evidence only; no new Player execution or current workspace acceptance')

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--archive',type=Path,required=True);p.add_argument('--manifest-sha256',required=True);p.add_argument('--output',type=Path);a=p.parse_args();result=verify(a.archive,a.manifest_sha256)
    if a.output:
        need(not a.output.absolute().is_relative_to(a.archive.resolve()),'Write verification outside archive');contracts.write_json_new(a.output,result)
    print(json.dumps(result))
