import copy
from concurrent.futures import ThreadPoolExecutor
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from operation_journal import Journal, JournalError, digest


class JournalTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        (self.root / 'XUILab').mkdir()
        (self.root / 'source.cs').write_text('frozen')
        self.j = Journal(self.root)
        self.req = dict(schema='xuilab.unity-operation/v1', kind='build', task='INFRA-003', candidate='fixture',
                        attempt='one', instance='fixture-instance', operator='fixture-operator', project='XUILab', editor='2022.3.45f1c1',
                        parameters={'platform': 'StandaloneWindows64', 'output_path': 'player.exe'},
                        inputs={'source.cs': digest(self.root / 'source.cs')}, artifacts=['player.exe'],
                        before={k: False for k in ('playing', 'paused', 'compiling', 'importing', 'tests_running', 'build_running', 'prefab_stage', 'dirty_scene')},
                        restore_expected={'playing': False, 'scene': 'original'})
        self.op = self.j.prepare(self.req)

    def envelope(self, data):
        return dict(operation=self.op, project_root=str(self.root / 'XUILab'), candidate='fixture', instance='fixture-instance',
                    observed_at='2026-09-07T01:00:00+00:00', response={'success': True, 'data': data})

    def start(self):
        self.j.claim(self.op)
        self.j.receipt(self.op, self.envelope({'job_id': 'job-one'}))

    def success(self):
        (self.root / 'player.exe').write_bytes(b'fixture-only-not-a-player')
        return self.envelope(dict(job_id='job-one', result='succeeded', platform='StandaloneWindows64', output_path='player.exe', errors=0, completed_at='2026-09-07T01:00:00+00:00'))

    def restoration(self):
        return dict(operation=self.op, project_root=str(self.root / 'XUILab'), observed_at='2026-09-07T01:01:00+00:00',
                    state=dict(playing=False, scene='original', compiling=False, importing=False, tests_running=False, build_running=False), raw={'fixture': True})

    def test_resume_prepared_lost_receipt_poll_terminal_restore(self):
        self.assertEqual(self.j.inspect(self.op)['action'], 'claim_after_live_preflight')
        self.j.claim(self.op)
        j = Journal(self.root)
        self.assertEqual(j.inspect(self.op)['action'], 'reconcile_lost_receipt_do_not_resend')
        with self.assertRaises(JournalError): j.claim(self.op)
        j.receipt(self.op, self.envelope({'job_id': 'job-one'}))
        self.assertEqual(j.inspect(self.op)['action'], 'poll_existing_job')
        j.terminal(self.op, self.success())
        self.assertEqual(j.inspect(self.op)['restoration'], 'not_run')
        j.restore(self.op, self.restoration())
        self.assertEqual(j.inspect(self.op)['action'], 'closed_do_not_resend')
        with self.assertRaises(JournalError): j.claim(self.op)

    def test_concurrent_claim_only_one_winner(self):
        def claim(_):
            try: Journal(self.root).claim(self.op); return True
            except JournalError: return False
        with ThreadPoolExecutor(max_workers=8) as pool:
            self.assertEqual(sum(pool.map(claim, range(16))), 1)

    def test_separate_process_claim_blocks_second_process(self):
        script = Path(__file__).with_name('operation_journal.py')
        command = [sys.executable, '-B', str(script), '--root', str(self.root), 'claim', '--operation', self.op]
        self.assertEqual(subprocess.run(command, capture_output=True).returncode, 0)
        self.assertEqual(subprocess.run(command, capture_output=True).returncode, 1)

    def test_volatile_fields_do_not_bypass_claim(self):
        self.j.claim(self.op)
        new = copy.deepcopy(self.req); new.update(instance='reconnected', operator='another')
        self.assertEqual(self.j.prepare(new), self.op)
        with self.assertRaises(JournalError): self.j.claim(self.op)

    def test_torn_claim_blocks_resume(self):
        (self.j.directory(self.op) / 'claim.json').write_bytes(b'{')
        with self.assertRaises(JournalError): self.j.claim(self.op)
        with self.assertRaises(JournalError): self.j.inspect(self.op)

    def test_input_drift_and_existing_output_block_claim(self):
        (self.root / 'source.cs').write_text('changed')
        with self.assertRaises(JournalError): self.j.claim(self.op)
        (self.root / 'source.cs').write_text('frozen')
        (self.root / 'player.exe').write_text('old')
        with self.assertRaises(JournalError): self.j.claim(self.op)

    def test_wrong_identity_and_unknown_job_rejected(self):
        self.start()
        good = self.success()
        for field in ('operation', 'project_root', 'candidate', 'instance'):
            bad = copy.deepcopy(good); bad[field] = 'wrong'
            with self.subTest(field=field), self.assertRaises(JournalError): self.j.terminal(self.op, bad)
        for field, value in [('job_id', 'wrong'), ('platform', 'wrong'), ('output_path', 'wrong'), ('result', 'building')]:
            bad = copy.deepcopy(good); bad['response']['data'][field] = value
            with self.subTest(field=field), self.assertRaises(JournalError): self.j.terminal(self.op, bad)
        bad = copy.deepcopy(good); bad['response'] = {'success': False, 'error': 'job unknown'}
        with self.assertRaises(JournalError): self.j.terminal(self.op, bad)

    def test_missing_artifact_and_post_terminal_drift(self):
        self.start(); good = self.success(); (self.root / 'player.exe').unlink()
        with self.assertRaises(JournalError): self.j.terminal(self.op, good)
        good = self.success(); self.j.terminal(self.op, good)
        (self.root / 'player.exe').write_bytes(b'changed')
        self.assertEqual(self.j.inspect(self.op)['outcome'], 'fail')

    def test_failed_cancelled_skipped_never_pass(self):
        for status in ('failed', 'cancelled', 'skipped'):
            with self.subTest(status=status):
                req = copy.deepcopy(self.req); req['attempt'] = status
                self.op = self.j.prepare(req); self.start()
                data = dict(job_id='job-one', result=status, platform='StandaloneWindows64', output_path='player.exe')
                self.j.terminal(self.op, self.envelope(data))
                self.assertEqual(self.j.inspect(self.op)['outcome'], 'fail')

    def test_restore_requires_terminal_and_matching_idle_state(self):
        with self.assertRaises(JournalError): self.j.restore(self.op, self.restoration())
        self.start(); self.j.terminal(self.op, self.success())
        for field, value in [('scene', 'other'), ('build_running', True)]:
            bad = self.restoration(); bad['state'][field] = value
            with self.assertRaises(JournalError): self.j.restore(self.op, bad)
        bad = self.restoration(); bad['observed_at'] = '2026-09-07T00:00:00+00:00'
        with self.assertRaises(JournalError): self.j.restore(self.op, bad)

    def test_test_summary_failure_skips_empty_not_pass(self):
        for total, passed, failed, skipped, expected in [(2, 2, 0, 0, 'pass'), (2, 1, 1, 0, 'fail'), (2, 1, 0, 1, 'fail'), (0, 0, 0, 0, 'fail')]:
            req = copy.deepcopy(self.req); req.update(kind='test', artifacts=[], parameters={'mode': 'EditMode'}, attempt=str((total, passed, failed, skipped)))
            self.op = self.j.prepare(req); self.start()
            data = dict(job_id='job-one', status='succeeded', mode='EditMode', finished_unix_ms=100,
                        result={'summary': dict(total=total, passed=passed, failed=failed, skipped=skipped, resultState='Passed')})
            self.j.terminal(self.op, self.envelope(data))
            self.assertEqual(self.j.inspect(self.op)['outcome'], expected)

    def test_escape_and_unsafe_preflight_rejected(self):
        for path in ('../escape', '/absolute', 'C:/other', 'a/../../escape'):
            bad = copy.deepcopy(self.req); bad['inputs'] = {path: '0' * 64}
            with self.assertRaises(JournalError): self.j.prepare(bad)
        bad = copy.deepcopy(self.req); bad['before']['dirty_scene'] = True
        with self.assertRaises(JournalError): self.j.prepare(bad)

    def test_invalid_native_completion_types_do_not_pass(self):
        self.start(); bad = self.success()
        bad['response']['data']['completed_at'] = True
        with self.assertRaises(JournalError): self.j.terminal(self.op, bad)
        req = copy.deepcopy(self.req); req.update(kind='test', artifacts=[], parameters={'mode': 'EditMode'}, attempt='bad-time')
        self.op = self.j.prepare(req); self.start()
        data = dict(job_id='job-one', status='succeeded', mode='EditMode', finished_unix_ms=True,
                    result={'summary': dict(total=1, passed=1, failed=0, skipped=0, resultState='Passed')})
        self.j.terminal(self.op, self.envelope(data))
        self.assertEqual(self.j.inspect(self.op)['outcome'], 'fail')

    def test_inconclusive_or_missing_summary_state_never_passes(self):
        for state in ('Inconclusive', 'Failed', None):
            req=copy.deepcopy(self.req);req.update(kind='test',artifacts=[],parameters={'mode':'EditMode'},attempt=str(state))
            self.op=self.j.prepare(req);self.start()
            data=dict(job_id='job-one',status='succeeded',mode='EditMode',finished_unix_ms=100,
                      result={'summary':dict(total=1,passed=1,failed=0,skipped=0,resultState=state)})
            self.j.terminal(self.op,self.envelope(data))
            self.assertEqual(self.j.inspect(self.op)['outcome'],'fail')

    def test_malformed_top_level_cli_reports_reconcile_json(self):
        path=self.root/'bad.json';path.write_text('[]')
        script=Path(__file__).with_name('operation_journal.py')
        result=subprocess.run([sys.executable,'-B',str(script),'--root',str(self.root),'prepare','--file',str(path)],capture_output=True,text=True)
        self.assertEqual(result.returncode,1)
        self.assertEqual(json.loads(result.stdout)['action'],'reconcile_do_not_resend')
        self.assertNotIn('Traceback',result.stderr)

    def test_corrupt_terminal_and_restoration_cannot_report_pass(self):
        self.start(); self.j.terminal(self.op, self.success())
        path = self.j.directory(self.op) / 'terminal.json'
        value = json.loads(path.read_text()); value['evidence']['response']['data']['job_id'] = 'wrong'
        path.write_text(json.dumps(value))
        with self.assertRaises(JournalError): self.j.inspect(self.op)


if __name__ == '__main__': unittest.main()
