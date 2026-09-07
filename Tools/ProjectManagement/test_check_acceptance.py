import json
from pathlib import Path
import shutil
import tempfile
import unittest

from check_acceptance import check


class AcceptanceTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name);original=Path(__file__).resolve().parents[2]
        shutil.copytree(original/'Docs/MVP',self.root/'Docs/MVP')
        (self.root/'Docs/Agents').mkdir(parents=True)
        self.path=self.root/'Docs/Agents/acceptance-map.json'
        shutil.copyfile(original/'Docs/Agents/acceptance-map.json',self.path)
        self.data=json.loads(self.path.read_text(encoding='utf-8'))
    def save(self):self.path.write_text(json.dumps(self.data),encoding='utf-8')
    def test_valid_and_read_only(self):
        before=self.path.read_bytes();self.assertEqual(check(self.root),[]);self.assertEqual(self.path.read_bytes(),before)
    def test_task_missing_duplicate_or_unknown(self):
        for edit in ('remove','duplicate','unknown'):
            with self.subTest(edit=edit):
                backup=json.loads(json.dumps(self.data))
                if edit=='remove':self.data['tasks'].pop()
                elif edit=='duplicate':self.data['tasks'].append(self.data['tasks'][0])
                else:self.data['tasks'][0]['taskId']='M9-01'
                self.save();self.assertTrue(check(self.root));self.data=backup
    def test_required_cannot_be_removed_or_weakened(self):
        self.data['criteria'][0]['requirement']='not_applicable';self.save();self.assertTrue(check(self.root))
        self.data['criteria'][0]['requirement']='required'
        last=self.data['criteria'].pop();self.data['tasks'][-1]['acceptanceIds'].remove(last['id'])
        self.save();self.assertTrue(check(self.root))
    def test_source_drift_and_escape(self):
        self.data['criteria'][0]['sourceText']='invented';self.save();self.assertTrue(check(self.root))
        self.data['tasks'][0]['source']='../../escape';self.save();self.assertTrue(check(self.root))
    def test_unknown_dependency_and_cycle(self):
        self.data['tasks'][0]['dependsOn']=['UNKNOWN'];self.save();self.assertTrue(check(self.root))
        self.data['tasks'][0]['dependsOn']=['M0-02'];self.save();self.assertTrue(check(self.root))
    def test_dynamic_state_not_allowed(self):
        self.data['tasks'][0]['state']='done';self.save();self.assertTrue(check(self.root))
    def test_new_brief_requires_required_binding(self):
        folder=self.root/'Docs/PM/Tasks/M2-01';folder.mkdir(parents=True)
        (folder/'TASK_STATUS.md').write_text('- pm_schema: xuilab.pm/v1',encoding='utf-8')
        brief=folder/'TASK_BRIEF.md';brief.write_text('## 验收矩阵\n| A1 | required | condition |',encoding='utf-8')
        self.assertTrue(check(self.root))
        brief.write_text('## 验收矩阵\n| A1 | required | condition |\n## 路线图验收映射\n| M2-01-DELIVERY | A1 |',encoding='utf-8')
        self.assertEqual(check(self.root),[])
        brief.write_text(brief.read_text(encoding='utf-8').replace('required','not_applicable'),encoding='utf-8');self.assertTrue(check(self.root))
    def test_legacy_not_reaccepted(self):
        folder=self.root/'Docs/PM/Tasks/M0-01';folder.mkdir(parents=True)
        (folder/'TASK_STATUS.md').write_text('historical content',encoding='utf-8')
        self.assertEqual(check(self.root),[])
    def test_broken_skill_reference(self):
        folder=self.root/'.agents/skills/test';folder.mkdir(parents=True)
        (folder/'SKILL.md').write_text('[missing](../../../Docs/missing.md)',encoding='utf-8')
        self.assertTrue(check(self.root))


if __name__=='__main__':unittest.main()
