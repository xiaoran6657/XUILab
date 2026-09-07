import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


class LauncherBoundaryTests(unittest.TestCase):
    def test_new_launcher_respects_resume_lock_before_freezing(self):
        with tempfile.TemporaryDirectory() as temp:
            base=Path(temp); root=base/'root'; root.mkdir(); player=base/'fake.exe'; player.write_bytes(b'fixture')
            lock=root/'test-pilot-manifest.json.resume.lock'; lock.write_text('held by another operator')
            command=[sys.executable,'-B',str(Path(__file__).with_name('run_list_matrix.py')),
                     '--player',str(player),'--root',str(root),'--candidate','test','--build','test',
                     '--source','test','--stamp','test','--plan','pilot']
            result=subprocess.run(command,capture_output=True,text=True)
            self.assertNotEqual(0,result.returncode)
            self.assertIn('lock already exists',result.stderr)
            self.assertEqual([lock],list(root.iterdir()))

    @unittest.skipUnless(os.name == 'nt', 'Windows junction regression')
    def test_root_junction_rejected_before_any_output(self):
        with tempfile.TemporaryDirectory() as temp:
            base=Path(temp); target=base/'target'; target.mkdir(); link=base/'link'
            made=subprocess.run(['cmd','/c','mklink','/J',str(link),str(target)],capture_output=True)
            self.assertEqual(0,made.returncode,made.stderr)
            try:
                command=[sys.executable,str(Path(__file__).with_name('run_list_matrix.py')),
                         '--player',str(base/'missing.exe'),'--root',str(link),
                         '--candidate','test','--build','test','--source','test','--stamp','test','--plan','pilot']
                result=subprocess.run(command,capture_output=True,text=True)
                self.assertNotEqual(0,result.returncode)
                self.assertIn('reparse point',result.stderr)
                self.assertEqual([],list(target.iterdir()))
            finally:
                os.rmdir(link)  # Removes only the junction entry, never its target.


if __name__=='__main__':unittest.main()
