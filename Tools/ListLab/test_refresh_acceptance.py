"""Negative checks for supplemental acceptance; synthetic files only."""
import contextlib,json,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
import refresh_acceptance as a

class AcceptanceFailures(unittest.TestCase):
    def test_unknown_root_and_missing_log(self):
        with tempfile.TemporaryDirectory() as t:
            p=Path(t);(p/'r').mkdir();(p/'.receipts').mkdir();(p/'.logs').mkdir()
            (p/'.receipts/r.json').write_text('{}');(p/'.logs/r.log').write_text('log')
            plan=dict(runs=[dict(runId='r')]);a.tree_contract(p,plan)
            (p/'r-intent.json').write_text('{}')
            with self.assertRaises(ValueError):a.tree_contract(p,plan)
            (p/'r-intent.json').unlink();(p/'.logs/r.log').unlink()
            with self.assertRaises(ValueError):a.tree_contract(p,plan)
    def test_truncated_gate(self):
        evidence={'response':{'data':{'result':{'summary':dict(total=32,passed=32),'results':[]}}}}
        with patch.object(a,'read',side_effect=[dict(parameters={}),evidence]):
            with self.assertRaises(ValueError):a.complete_test_details(dict(checks=[dict(kind='core',requestPath='q',terminalPath='e')]),Path('.'))
    def test_duplicate_gate(self):
        evidence={'response':{'data':{'result':{'summary':dict(total=22,passed=22),'results':[dict(fullName='same',state='Passed')]*22}}}}
        with patch.object(a,'read',side_effect=[dict(parameters={}),evidence]):
            with self.assertRaises(ValueError):a.complete_test_details(dict(checks=[dict(kind='functional-runner',requestPath='q',terminalPath='e')]),Path('.'))
    def test_wrong_receipt(self):
        for key,value in (('schemaVersion','wrong'),('pid',True),('pid',0),('identitySha256','wrong')):
            with self.subTest(key=key,value=value),tempfile.TemporaryDirectory() as t:
                p=Path(t);root=p/'runs';(root/'r').mkdir(parents=True);(root/'r/identity.json').write_text('{}')
                (root/'r/events.log').write_text('');(root/'.receipts').mkdir();(root/'.logs').mkdir();(root/'.logs/r.log').write_text('log')
                for n in ('plan','gate','build'):(p/n).write_text('{}')
                h=a.sha(p/'plan');run=dict(runId='r',timeoutSeconds=180)
                r=dict(schemaVersion='xuilab.list-refresh.launch-receipt/v1',runId='r',pid=1,exitCode=0,correctness='pass',planSha256=h,buildManifestSha256=h,identitySha256=h,durationSeconds=1,completedUtc='2026-09-08T00:00:00+00:00')
                r[key]=value;(root/'.receipts/r.json').write_text(json.dumps(r))
                original=a.read
                def read(path):return dict(runs=[run]) if path==p/'plan' else original(path)
                with patch.object(a,'verify',return_value=dict(status='pass')),patch.object(a,'check_gate'),patch.object(a,'complete_test_details',return_value={}),patch.object(a,'read',side_effect=read):
                    with self.assertRaises(ValueError):a.supplement(p/'plan',root,p,p/'gate',p/'build')
    def test_raw_failure_not_pass(self):
        with patch.object(a,'verify',return_value=dict(status='not_ready')):
            with self.assertRaises(ValueError):a.supplement(None,None,None,None,None)

if __name__=='__main__':unittest.main()
