"""Canonical fixed subdivision coverage plan, with exact order and parameters."""
import argparse,copy,hashlib,json
from pathlib import Path
import gradient_experiment as contracts
from player_plan import groups as baseline_groups,ARTIFACTS

SCENARIOS=(('large-static-05','large',1,'static','Horizontal',.05),('large-static-50','large',1,'static','Vertical',.5),('large-static-95','large',1,'static','Horizontal',.95),('grid-static-05','grid',100,'static','Vertical',.05),('grid-static-50','grid',100,'static','Horizontal',.5),('grid-static-95','grid',100,'static','Vertical',.95),('large-dynamic','large',1,'all','Horizontal',.05),('grid-dynamic','grid',100,'all','Vertical',.05))

def planned_runs(plan_id,gate_hash,build_hash,protocol_hash,pilot=False):
    runs=[];repeats=1 if pilot else 5
    templates=baseline_groups()
    for repeat in range(1,repeats+1):
        for scenario,layout,count,state,direction,bias in SCENARIOS:
            for segments in ((8,16,32,64) if repeat%2 else (64,32,16,8)):
                if pilot and (state!='all' or segments not in (8,64)):continue
                params=copy.deepcopy(next(p for _,p in templates if p['layout']==layout and p['count']==count and p['state']==state))
                params.update(scenario=scenario,direction=direction,bias=bias,segments=segments,effectMode='fixed',expectedVertices=2*(segments+1),expectedTriangles=2*segments,transitionFrom=.05,transitionTo=.95,continueWarmup=True,preflightSha256=gate_hash,buildManifestSha256=build_hash,experimentProtocolSha256=protocol_hash)
                group='gradient-subdivision-'+scenario+'-s'+str(segments)
                runs.append(dict(runId=plan_id+'-'+group+'-r'+str(repeat),groupId=group,caseId=group,variant='fixed'+str(segments),runIndex=repeat,plannedRepeatCount=repeats,warmupFrames=300,measureFrames=1800,sampleCapacity=1800,frameBudgetMs=16.6666667,timeoutSeconds=180,parameters=params))
    return runs

def validate_subdivision(plan):
    contracts.validate_plan(plan,require_frozen=True)
    if plan['experimentId']!='gradient-subdivision-v1' or plan['contractId']!='gradient-schlick-v1' or plan['artifacts']!=ARTIFACTS:raise ValueError('Wrong subdivision protocol/artifacts')
    if plan['quality']!=dict(metricId='rgba-max-absolute-error',threshold=.01,referenceId='schlick-dense4097-v1',aggregation='max-absolute-rgba'):raise ValueError('Quality contract changed')
    if len(plan['runs']) not in (4,160):raise ValueError('Incomplete pilot or matrix')
    p=plan['runs'][0]['parameters']
    for key in ('preflightSha256','buildManifestSha256','experimentProtocolSha256'):
        if not isinstance(p.get(key),str) or not contracts.HASH_RE.fullmatch(p[key]):raise ValueError('Missing control SHA')
    expected=planned_runs(plan['planId'],p['preflightSha256'],p['buildManifestSha256'],p['experimentProtocolSha256'],len(plan['runs'])==4)
    if plan['runs']!=expected:raise ValueError('Run order/coverage/parameters changed')
    if plan['budget']!=dict(perRunWallClockSeconds=180,totalWallClockSeconds=180*len(expected)) or plan['comparison'] is not None:raise ValueError('Budget/comparison changed')
    return plan

def make_plan(plan_id,candidate,build,source,dirty,contract,protocol,gate,manifest,pilot=False):
    m=contracts.read_json(manifest)
    if any(m.get(k)!=v for k,v in dict(schemaVersion='xuilab.gradient.build/v1',candidateId=candidate,buildId=build,sourceRevision=source,dirty=dirty).items()):raise ValueError('Build identity')
    runs=planned_runs(plan_id,contracts.sha256_file(gate),contracts.sha256_file(manifest),contracts.sha256_file(protocol),pilot)
    result=dict(schemaVersion='xuilab.gradient.plan/v1',status='frozen',planId=plan_id,experimentId='gradient-subdivision-v1',protocolVersion='xuilab.benchmark.protocol/v1',contractId='gradient-schlick-v1',contractSha256=contracts.sha256_file(contract),candidateId=candidate,buildId=build,sourceRevision=source,dirty=dirty,evidenceKind='windows-development-player',budget=dict(perRunWallClockSeconds=180,totalWallClockSeconds=180*len(runs)),quality=dict(metricId='rgba-max-absolute-error',threshold=.01,referenceId='schlick-dense4097-v1',aggregation='max-absolute-rgba'),comparison=None,artifacts=ARTIFACTS,runs=runs)
    return validate_subdivision(result)

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for n in ('plan-id','candidate','build','source','gate','build-manifest','output'):p.add_argument('--'+n,required=True)
    p.add_argument('--dirty',choices=['true','false'],required=True);p.add_argument('--pilot',action='store_true');p.add_argument('--contract',default='Docs/Experiments/GRADIENT_CONTRACT.md');p.add_argument('--protocol',default='Docs/Experiments/GRADIENT_SUBDIVISION_PROTOCOL-r1.md');a=p.parse_args()
    plan=make_plan(a.plan_id,a.candidate,a.build,a.source,a.dirty=='true',Path(a.contract),Path(a.protocol),Path(a.gate),Path(a.build_manifest),a.pilot);contracts.write_json_new(Path(a.output),plan);print(json.dumps(dict(runs=len(plan['runs']),sha256=contracts.sha256_file(a.output))))
