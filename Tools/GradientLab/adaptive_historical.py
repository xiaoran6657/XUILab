"""Recompute archived G2 evidence without rewriting native paths or dispatching work."""
import argparse,json,sys
from pathlib import Path,PureWindowsPath
import gradient_experiment as c
from adaptive_verify import read,need,near,check_gate,verify_run,quantile
from adaptive_plan import validate_adaptive,ARTIFACTS,SCENARIOS
from adaptive_recovery import validate_policy
from adaptive_policy import validate_policy as base_policy
from adaptive_attempt_audit import audit
from subdivision_launch import tree_files,check_inventory
from subdivision_focus_launch import verify_startup_focus
from subdivision_report import distribution,compare
from historical_verify import build_provenance,gate_closure,recorded_path

BASE='Artifacts/gradient-adaptive-player-r1'

def report_identity(saved,plan,pilot):
    for k in ('candidateId','buildId','sourceRevision','dirty'):need(type(saved.get(k)) is type(plan[k]) and saved[k]==plan[k],'Saved candidate identity '+k)
    need(saved.get('pilot') is pilot,'Saved pilot classification')

def receipt(root,recorded,relative,run,plan_path,build_path,launcher,policy_hash):
    base=root/relative;directory=base/run['runId'];rid=run['runId'];build=read(build_path)
    r=read(base/'.receipts'/(rid+'.json'));launch_path=base/'.launches'/(rid+'.json');log=base/'.logs'/(rid+'.log');launch=read(launch_path)
    ph=c.sha256_file(plan_path);bh=c.sha256_file(build_path)
    need(r['schemaVersion']=='xuilab.gradient.launch-receipt/v2' and r['runId']==rid,'Receipt identity')
    need(type(r['pid']) is int and r['pid']>0 and type(r['exitCode']) is int and r['exitCode']==0 and r['correctness']=='pass','Receipt outcome')
    need(r['planSha256']==ph and r['buildManifestSha256']==bh and 0<r['durationSeconds']<=run['timeoutSeconds']+15,'Receipt controls')
    recorded_path(r['player'],recorded/PureWindowsPath(BASE)/PureWindowsPath(build['player']))
    need(r['playerSha256']==build['files'][build['player']] and r['launcherSha256']==c.sha256_file(root/'Tools/GradientLab'/launcher),'Receipt executable/tool')
    need(r['identitySha256']==c.sha256_file(directory/'identity.json') and r['files']=={n:c.sha256_file(directory/n) for n in ARTIFACTS},'Receipt raw hashes')
    need(log.stat().st_size>0 and r['logSha256']==c.sha256_file(log) and r['launchRecordSha256']==c.sha256_file(launch_path),'Receipt sidecars')
    need(launch['schemaVersion']=='xuilab.gradient.launch-start/v2','Start schema')
    for k in ('runId','pid','planSha256','buildManifestSha256','player','playerSha256','command','launcherSha256','dispatchPolicySha256'):need(launch[k]==r[k],'Start/receipt '+k)
    need(r['dispatchPolicySha256']==policy_hash,'Receipt dispatch policy')
    cmd=r['command'];need(isinstance(cmd,list) and cmd[0]==r['player'],'Command executable')
    for flag,value in {'-screen-fullscreen':'0','-screen-width':'960','-screen-height':'540','--xuilab-run-id':rid,'--gradient-plan-sha256':ph,'--gradient-build-manifest-sha256':bh}.items():need(cmd.count(flag)==1 and cmd[cmd.index(flag)+1]==value,'Command scalar')
    paths={'-logFile':recorded/PureWindowsPath(relative)/'.logs'/(rid+'.log'),'--xuilab-output-root':recorded/PureWindowsPath(relative),'--gradient-plan':recorded/PureWindowsPath(plan_path.relative_to(root).as_posix()),'--gradient-preflight':recorded/'Artifacts/gradient-adaptive-validation/preflight-r1.json','--gradient-build-manifest':recorded/PureWindowsPath(BASE)/'build-manifest.json'}
    for flag,value in paths.items():need(cmd.count(flag)==1,'Command path count');recorded_path(cmd[cmd.index(flag)+1],value)
    need(cmd.count('-force-d3d11')==cmd.count('--xuilab-run')==1,'Command switches');verify_startup_focus(r['startupFocus'],directory,r['pid'])
    return r

def pilot_failures(root,recorded):
    base=root/BASE;excluded=[]
    for version,folder in (('r1','pilot'),('recovery1','pilot-recovery1'),('recovery2','pilot-recovery2')):
        pp=base/('pilot-plan-'+version+'.json');polpath=base/('pilot-policy-'+version+'.json');plan=validate_adaptive(read(pp));policy=read(polpath);old=base/folder;rid=plan['runs'][0]['runId'];directory=old/rid
        need(policy['schemaVersion']=='xuilab.gradient.adaptive-dispatch/v1' and policy['candidateId']==plan['candidateId'] and policy['runIds']==[r['runId'] for r in plan['runs']],'Old pilot policy identity')
        need(policy['runRoot']==old.relative_to(root).as_posix() and policy['planSha256']==c.sha256_file(pp) and policy['buildManifestSha256']==c.sha256_file(base/'build-manifest.json') and policy['preflightSha256']==c.sha256_file(root/'Artifacts/gradient-adaptive-validation/preflight-r1.json'),'Old pilot controls')
        sources=base/('pilot-tool-sources-'+version)
        need({f.relative_to(sources).as_posix() for f in tree_files(sources)}==set(policy['toolInputs']),'Old pilot exact tool source set')
        for name,digest in policy['toolInputs'].items():need(c.sha256_file(sources/name)==digest,'Old pilot tool SHA')
        allowed={rid,rid+'-orchestration-failure.json','.launches','.logs'}
        need({x.name for x in old.iterdir()} in (allowed,allowed|{'.receipts'}),'Old pilot exact tree')
        if (old/'.receipts').exists():need(not list((old/'.receipts').iterdir()),'Excluded pilot has a receipt')
        for side,suffix in (('.logs','.log'),('.launches','.json')):need({x.name for x in (old/side).iterdir()}=={rid+suffix},'Old pilot sidecar set')
        need({x.name for x in directory.iterdir()}==set(ARTIFACTS),'Old pilot exact raw set')
        identity=read(directory/'identity.json');failure=read(old/(rid+'-orchestration-failure.json'));launch=read(old/'.launches'/(rid+'.json'));summary=read(directory/'summary.json')
        need(identity['runId']==rid and identity['planSha256']==policy['planSha256'] and identity['buildManifestSha256']==policy['buildManifestSha256'],'Old pilot raw identity')
        need(set(identity['artifactSha256'])==set(ARTIFACTS)-{'identity.json'},'Old pilot raw inventory')
        for name,digest in identity['artifactSha256'].items():need(c.sha256_file(directory/name)==digest,'Old pilot raw SHA')
        need(launch['schemaVersion']=='xuilab.gradient.launch-start/v2' and launch['runId']==failure['runId']==summary['runId']==rid and type(launch['pid']) is int and launch['pid']>0 and launch['pid']==failure['pid'],'Old pilot launch identity')
        for k in ('planSha256','buildManifestSha256'):need(launch[k]==policy[k],'Old pilot launch controls')
        need(launch['dispatchPolicySha256']==c.sha256_file(polpath) and launch['launcherSha256']==policy['toolInputs']['Tools/GradientLab/adaptive_launch.py'],'Old pilot launcher binding')
        build=read(base/'build-manifest.json');recorded_path(launch['player'],recorded/PureWindowsPath(BASE)/PureWindowsPath(build['player']));need(launch['playerSha256']==build['files'][build['player']],'Old pilot player binding')
        need(summary['state']=='completed' and summary['correctness']=='pass' and failure['exitCode']==summary['exitCode']==(3 if version=='r1' else 0),'Old pilot classification')
        need(summary['measurementValidity']==('invalid' if version=='r1' else 'valid'),'Old pilot validity')
        expected={'r1':'Player exit code 3','recovery1':'Owned Player exited before foreground acquisition','recovery2':"No module named 'numpy'"}
        need(failure['reason']==expected[version],'Old pilot failure reason')
        excluded.append(dict(root=old.relative_to(root).as_posix(),runId=rid,reason=failure['reason'],excludedFromStatistics=True,completeStartupReceipt=False,toolSources='hash-matched reconstructed copies'))
    return excluded

def verify(root,expected):
    root=root.absolute();sha=c.sha256_file
    need(Path(__file__).absolute()==root/'Tools/GradientLab/adaptive_historical.py','Invoke archived verifier')
    need(sha(root/'baseline-manifest.json')==expected,'External manifest hash')
    meta=read(root/'baseline-manifest.json');need(meta['schemaVersion']=='xuilab.gradient.adaptive-historical/v1','Archive schema')
    recorded=PureWindowsPath(meta['recordedRepoRoot']);need(recorded.is_absolute() and '..' not in recorded.parts,'Recorded root')
    actual={x.relative_to(root).as_posix() for x in tree_files(root)}-{'baseline-manifest.json'};need(actual==set(meta['files']),'Exact archive tree')
    for n,v in meta['files'].items():
        need(not PureWindowsPath(n).is_absolute() and '..' not in Path(n).parts,'Archive path')
        need((root/n).stat().st_size==v['size'] and sha(root/n)==v['sha256'],'Archive member drift '+n)
    base=root/BASE;bp=base/'build-manifest.json';build=read(bp);gp=root/'Artifacts/gradient-adaptive-validation/preflight-r1.json';gate=read(gp)
    need(build['schemaVersion']=='xuilab.gradient.build/v1' and build['sourceInputs']==gate['sourceInputs']==meta['sourceInputs'],'Source identity')
    sources={x.relative_to(root).as_posix() for folder in ('XUILab/Assets','XUILab/Packages','XUILab/ProjectSettings') for x in tree_files(root/folder)}
    need(sources=={n for n in build['sourceInputs'] if n.startswith(('XUILab/Assets/','XUILab/Packages/','XUILab/ProjectSettings/'))},'Exact Unity sources')
    for n,h in build['sourceInputs'].items():need(sha(root/n)==h,'Source drift')
    need({x.relative_to(base).as_posix() for x in tree_files(base/'build')}==set(build['files']),'Exact build tree')
    for n,h in build['files'].items():need(sha(base/n)==h,'Build drift')
    results={}
    for kind in ('matrix','pilot'):
        pp=base/('matrix-plan-r1.json' if kind=='matrix' else 'pilot-plan-recovery3.json');plan=validate_adaptive(read(pp));ph=sha(pp);bh=sha(bp)
        for k in ('candidateId','buildId','sourceRevision','dirty'):need(plan[k]==build[k]==meta[k],'Candidate mismatch')
        check_gate(gate,plan,root)
        if kind=='matrix':
            build_provenance(root,build,plan,recorded)
            for check in gate['checks']:
                evidence=read(root/check['terminalPath']);request=root/'Artifacts/unity-operations'/evidence['operation']/'request.json'
                need(read(request)==read(root/check['requestPath']),'Gate exported request mismatch');gate_closure(root,dict(check,requestSha256=sha(request)),recorded)
            polpath=root/meta['policyPath'];policy=read(polpath);runroot=root/policy['runRoot'];validate_policy(polpath,plan,pp,gp,bp,root,runroot)
            ids=set(policy['selectedRunIds']);locations={r['runId']:(policy['runRoot'],'adaptive_continue.py',sha(polpath)) for r in plan['runs'][policy['resumeIndex']: ]}
            for prior in policy['history']:
                for r in plan['runs'][prior['start']:prior['end']]:locations[r['runId']]=(prior['root'],'adaptive_launch.py' if prior['start']==0 else 'adaptive_continue.py',prior['policySha256'])
        else:
            polpath=base/'pilot-policy-recovery3.json';policy=read(polpath);runroot=base/'pilot-recovery3';base_policy(polpath,plan,pp,gp,bp,root,runroot)
            ids={r['runId'] for r in plan['runs']};locations={rid:(runroot.relative_to(root).as_posix(),'adaptive_launch.py',sha(polpath)) for rid in ids}
        check_inventory(runroot,plan);need({x.name for x in runroot.iterdir()}==ids|{'.receipts','.logs','.launches'},'Exact current run tree')
        for folder,suffix in (('.receipts','.json'),('.logs','.log'),('.launches','.json')):need({x.name for x in (runroot/folder).iterdir()}=={n+suffix for n in ids},'Exact sidecar tree')
        saved=read(base/(kind+'-report-r1.json'));need(saved['status']==saved['correctness']=='pass' and saved['measurementValidity']=='valid' and saved['runCount']==len(plan['runs']),'Saved status')
        report_identity(saved,plan,kind=='pilot')
        need(saved['planSha256']==ph and saved['preflightSha256']==sha(gp) and saved['buildManifestSha256']==bh and saved['dispatchPolicySha256']==sha(polpath),'Saved controls')
        need(saved['reportToolSha256']==sha(root/'Tools/GradientLab'/('adaptive_campaign_report.py' if kind=='matrix' else 'adaptive_report.py')),'Report tool SHA')
        need([r['runId'] for r in saved['runs']]==[r['runId'] for r in plan['runs']],'Run order')
        for run,row in zip(plan['runs'],saved['runs']):
            relative,launcher,policyhash=locations[run['runId']];r=receipt(root,recorded,relative,run,pp,bp,launcher,policyhash)
            result,detail=verify_run(root/relative/run['runId'],plan,run,ph,root,gate)
            need(row['correctness']==result['correctness']=='pass' and row['measurementValidity']==result['measurementValidity']=='valid' and row['qualityStatus']==result['qualityStatus']==r['qualityStatus'],'Row outcome')
            need(row['scenario']==run['parameters']['scenario'] and row['variant']==run['variant'] and row['repeat']==run['runIndex'],'Row grouping')
            need(all(detail['environment'][k]==saved['environment'][k] for k in ('operatingSystem','processorType','processorCount','graphicsDeviceName','graphicsDeviceVersion')),'Environment mismatch')
            values=result['metrics']['frameIntervalMs'];q=detail['quality'];cost=result['metrics']['costMetrics']
            derived=dict(p50=quantile(values,.5),p95=quantile(values,.95),p99=quantile(values,.99),maximum=max(values),overBudgetRatio=sum(x>run['frameBudgetMs'] for x in values)/len(values),coldPrepareMs=detail['coldPrepareMs'],qualityMaxError=q['maxError'],qualityRmsError=q['rmsError'],quantizationMaxError=q['quantizationMaxError'],componentDirtyTotal=cost['componentDirtyTotal'],componentRebuildTotal=cost['componentRebuildTotal'],maximumVisibleVertices=cost['visibleVertices'],**detail['selection'])
            for k,v in derived.items():near(row[k],v,1e-10,'Row metric '+k)
        groups=[];comparisons=[];pilot=kind=='pilot'
        metrics=('p50','p95','p99','maximum','overBudgetRatio','coldPrepareMs','qualityMaxError','qualityRmsError','quantizationMaxError','selectionMs','coldSelectionMs','minSegments','maxSegments','maximumVisibleVertices')
        for scenario,*_ in SCENARIOS:
            subset=[r for r in saved['runs'] if r['scenario']==scenario]
            if not subset:continue
            for variant in ('fixed32','adaptive64'):
                runs=sorted([r for r in subset if r['variant']==variant],key=lambda r:r['repeat']);need([r['repeat'] for r in runs]==list(range(1,2 if pilot else 6)),'Repeat coverage')
                groups.append(dict(scenario=scenario,variant=variant,runs=runs,qualityStatus='pass' if all(r['qualityStatus']=='pass' for r in runs) else 'quality_limited',statistics={metric:distribution([r[metric] for r in runs]) for metric in metrics}))
            if not pilot:comparisons.append(dict(scenario=scenario,**compare([r['p95'] for r in sorted(subset,key=lambda r:r['repeat']) if r['variant']=='fixed32'],[r['p95'] for r in sorted(subset,key=lambda r:r['repeat']) if r['variant']=='adaptive64'])))
        need(saved['groups']==groups and saved['comparisons']==comparisons,'Groups/comparisons mismatch')
        if not pilot:
            need(saved['invalidAttempts']==audit(root,pp,bp,polpath,recorded),'Excluded attempts mismatch')
            need(saved['finalReportToolSha256']==sha(root/'Tools/GradientLab/adaptive_final_report.py') and saved['attemptAuditToolSha256']==sha(root/'Tools/GradientLab/adaptive_attempt_audit.py'),'Final report tool identities')
            need(saved['runRoots']=={n:v[0] for n,v in locations.items()} and saved['history']==policy['history'],'Historical root mapping')
        results[kind]=dict(runs=len(plan['runs']),comparisons={k:sum(x['result']==k for x in comparisons) for k in ('improved','regressed','inconclusive')})
    excluded_pilot=pilot_failures(root,recorded)
    for name,module in list(sys.modules.items()):
        location=getattr(module,'__file__',None)
        if location and ('/Tools/GradientLab/' in str(location).replace('\\','/') or '/Tools/UnityOperations/' in str(location).replace('\\','/')):need(Path(location).absolute().is_relative_to(root),'Dependency outside archive '+name)
    return dict(schemaVersion='xuilab.gradient.adaptive-historical-verification/v1',integrity='pass',correctness='pass',candidateId=meta['candidateId'],manifestSha256=expected,verifierSha256=sha(Path(__file__)),results=results,excludedPilotAttempts=excluded_pilot,limitation='Historical exploratory dirty-source evidence; no new execution. Cross-day first pair remains a limitation.')

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--archive',type=Path,required=True);p.add_argument('--manifest-sha256',required=True);p.add_argument('--output',type=Path);a=p.parse_args();r=verify(a.archive,a.manifest_sha256)
    if a.output:need(not a.output.absolute().is_relative_to(a.archive.absolute()),'Output must be outside archive');c.write_json_new(a.output,r)
    print(json.dumps(r))
