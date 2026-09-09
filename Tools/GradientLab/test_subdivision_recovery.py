"""Recovery policy checks use isolated fixtures, never mutable campaign output."""
import copy,json,tempfile,unittest
from pathlib import Path
from gradient_experiment import sha256_file
from subdivision_recovery import TOOL_FILES,validate_policy

class RecoveryPolicyTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.repo=Path(self.tmp.name);self.old=self.repo/'original';self.target=self.repo/'continued'
        self.plan={'runs':[{'runId':x} for x in ('first','failed','last')], 'artifacts':['config.json','summary.json','events.log','identity.json']}
        self.plan_path=self.write('plan.json',self.plan);self.gate=self.write('gate.json',{});self.build=self.write('build.json',{})
        for name in TOOL_FILES:self.write(name,'fixture input')
        self.write('original/first/summary.json',{'state':'completed'});self.write('original/.receipts/first.json',{})
        for name in ('first','failed'):
            self.write('original/.logs/'+name+'.log','fixture log');self.write('original/.launches/'+name+'.json',{'pid':123})
        self.write('original/failed/config.json',{})
        self.write('original/failed/summary.json',dict(runId='failed',state='completed',correctness='pass',measurementValidity='invalid',exitCode=3,exportSucceeded=True,cleanupSucceeded=True))
        self.write('original/failed/events.log','focus_lost'+chr(10)+'measure_started'+chr(10))
        self.write('original/failed/identity.json',dict(runId='failed',planSha256=sha256_file(self.plan_path),buildManifestSha256=sha256_file(self.build),configSha256=sha256_file(self.old/'failed/config.json'),artifactSha256={n:sha256_file(self.old/'failed'/n) for n in self.plan['artifacts'] if n!='identity.json'}))
        self.write('original/failed-orchestration-failure.json',dict(runId='failed',planSha256=sha256_file(self.plan_path),exitCode=3,pid=123))
        self.policy=dict(schemaVersion='xuilab.gradient.subdivision-recovery/v1',planSha256=sha256_file(self.plan_path),preflightSha256=sha256_file(self.gate),buildManifestSha256=sha256_file(self.build),resumeIndex=1,selectedRunIds=['failed','last'],failedRunId='failed',originalRoot='original',continuedRoot='continued',retainedFiles={p.relative_to(self.old).as_posix():sha256_file(p) for p in self.old.rglob('*') if p.is_file()},toolInputs={n:sha256_file(self.repo/n) for n in TOOL_FILES})
    def write(self,name,value):
        p=self.repo/name;p.parent.mkdir(parents=True,exist_ok=True);p.write_text(value if isinstance(value,str) else json.dumps(value),encoding='utf-8');return p
    def validate(self,policy):
        return validate_policy(self.write('policy.json',policy),self.plan,self.plan_path,self.gate,self.build,self.repo,self.target)
    def test_exact_policy_and_reject_mutations(self):
        self.assertEqual(self.validate(self.policy),self.policy)
        for change in (
            lambda p:p.update(planSha256='0'*64),lambda p:p.update(resumeIndex=0),
            lambda p:p['selectedRunIds'].pop(),lambda p:p['selectedRunIds'].reverse(),
            lambda p:p.update(continuedRoot=p['originalRoot']),
            lambda p:p['retainedFiles'].pop(next(iter(p['retainedFiles']))),lambda p:p.update(toolInputs={}),
        ):
            bad=copy.deepcopy(self.policy);change(bad)
            with self.assertRaises(ValueError):self.validate(bad)
    def test_unresolved_continued_attempt_is_rejected(self):
        self.write('continued/failed-orchestration-failure.json',{})
        with self.assertRaisesRegex(ValueError,'Unselected or unresolved continued run'):self.validate(self.policy)

if __name__=='__main__':unittest.main()
