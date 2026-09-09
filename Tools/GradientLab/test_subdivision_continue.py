"""Mock process failures: never launches Unity or a Player."""
import contextlib,json,tempfile,unittest
from pathlib import Path
from unittest.mock import patch,Mock
import subdivision_continue as m
import subdivision_recovery

class DispatchSafety(unittest.TestCase):
    def exercise(self,mode):
        with tempfile.TemporaryDirectory() as tmp:
            repo=Path(tmp);(repo/'Artifacts').mkdir();root=repo/'runs'
            plan_path=repo/'plan.json';gate=repo/'gate.json';build=repo/'build.json';player=repo/'p.exe'
            for p in (plan_path,gate,build,player):p.write_text('{}')
            h=m.contracts.sha256_file(plan_path)
            run=dict(runId='r',timeoutSeconds=1,parameters=dict(preflightSha256=h,buildManifestSha256=h))
            plan=dict(runs=[run]);proc=Mock(pid=123,returncode=0)
            proc.wait.return_value=0;proc.poll.return_value=None
            if mode=='interrupt':proc.wait.side_effect=KeyboardInterrupt()
            if mode=='timeout':proc.wait.side_effect=[m.subprocess.TimeoutExpired('p',1),0]
            if mode=='kill_failed':proc.wait.side_effect=m.subprocess.TimeoutExpired('p',1);proc.kill.side_effect=OSError('kill failed')
            def result(*args):
                d=root/'r';d.mkdir()
                for n in m.ARTIFACTS:(d/n).write_text('{}')
                (root/'.logs/r.log').write_text('log')
                return dict(state='completed',correctness='pass',measurementValidity='valid',qualityStatus='quality_limited'),dict(frameP95=1)
            original=m.contracts.write_json_new
            def write(path,value):
                if mode=='start_write_failed' and path.parent.name=='.launches':raise OSError('disk')
                original(path,value)
            with contextlib.ExitStack() as stack:
                stack.enter_context(patch.object(m,'validate_plan',return_value=plan))
                stack.enter_context(patch.object(subdivision_recovery,'validate_policy',return_value=dict(resumeIndex=0)))
                stack.enter_context(patch.object(m,'check_gate'))
                stack.enter_context(patch.object(m,'read',side_effect=lambda p:dict(sourceInputs={}) if p==gate else json.loads(p.read_text())))
                stack.enter_context(patch.object(m,'check_build',return_value=dict(sourceInputs={})))
                stack.enter_context(patch.object(m,'verify_run',side_effect=result))
                stack.enter_context(patch.object(m.contracts,'write_json_new',side_effect=write))
                popen=stack.enter_context(patch.object(m.subprocess,'Popen',side_effect=OSError('unknown spawn') if mode=='spawn_failed' else None,return_value=proc))
                if mode=='success':m.launch(plan_path,root,gate,player,build,repo,plan_path,h)
                else:
                    with self.assertRaises(BaseException):m.launch(plan_path,root,gate,player,build,repo,plan_path,h)
                self.assertEqual(popen.call_count,1)
            uncertain=mode in ('interrupt','kill_failed','start_write_failed','spawn_failed')
            self.assertEqual((repo/'Artifacts/gradient-player.lock').exists(),uncertain)
            self.assertEqual((root/'r-intent.json').exists(),uncertain)
            self.assertEqual((root/'r-orchestration-failure.json').exists(),mode=='timeout')
            if mode=='success':
                receipt=json.loads((root/'.receipts/r.json').read_text())
                self.assertEqual(receipt['pid'],123)
                self.assertEqual(receipt['command'][0],str(player))
                self.assertEqual(receipt['logSha256'],m.contracts.sha256_file(root/'.logs/r.log'))
            if mode=='timeout':proc.kill.assert_called_once()
    def test_success(self):self.exercise('success')
    def test_interrupt(self):self.exercise('interrupt')
    def test_timeout(self):self.exercise('timeout')
    def test_kill_failed(self):self.exercise('kill_failed')
    def test_start_write_failed(self):self.exercise('start_write_failed')
    def test_spawn_failed(self):self.exercise('spawn_failed')

if __name__=='__main__':unittest.main()
