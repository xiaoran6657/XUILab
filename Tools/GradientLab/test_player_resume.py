"""Recovery policy safety tests using temporary synthetic artifacts only."""
import json
from pathlib import Path
import tempfile
import unittest
from player_resume import inventory,timeout_record
from player_verify import EvidenceError

class ResumeTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.root=Path(self.temp.name);(self.root/".logs").mkdir()
        self.run=dict(runId="stress-r1",caseId="stress",timeoutSeconds=180);self.plan=dict(runs=[self.run,dict(runId="stress-r2",caseId="stress",timeoutSeconds=180),dict(runId="control-r1",caseId="control",timeoutSeconds=180)])
        self.failure=self.root/"stress-r1-orchestration-failure.json";self.value=dict(runId="stress-r1",planSha256="a"*64,reason="Player wall-clock timeout",exitCode=1,pid=123,durationSeconds=180.1)
        self.failure.write_text(json.dumps(self.value));(self.root/".logs/stress-r1.log").write_text("controlled timeout fixture")
    def tearDown(self):self.temp.cleanup()
    def test_retained_timeout_blocks_only_its_case(self):
        before={p.relative_to(self.root).as_posix():p.read_bytes() for p in self.root.rglob("*") if p.is_file()}
        self.assertEqual(set(inventory(self.root,self.plan,"a"*64)),{"stress"})
        self.assertEqual(before,{p.relative_to(self.root).as_posix():p.read_bytes() for p in self.root.rglob("*") if p.is_file()})
    def test_unresolved_intent_prevents_any_resume(self):
        (self.root/"control-r1-intent.json").write_text("{}")
        with self.assertRaises(EvidenceError):inventory(self.root,self.plan,"a"*64)
    def test_non_timeout_failure_is_not_skipped(self):
        self.value["reason"]="Player exit code 2";self.failure.write_text(json.dumps(self.value))
        with self.assertRaises(EvidenceError):inventory(self.root,self.plan,"a"*64)
    def test_missing_process_termination_is_not_skipped(self):
        for value in (None,False,0):
            with self.subTest(value=value):
                self.value["exitCode"]=value;self.failure.write_text(json.dumps(self.value))
                with self.assertRaises(EvidenceError):timeout_record(self.failure,self.run,"a"*64,self.root)
    def test_short_duration_or_wrong_plan_rejected(self):
        self.value["durationSeconds"]=179;self.failure.write_text(json.dumps(self.value))
        with self.assertRaises(EvidenceError):inventory(self.root,self.plan,"a"*64)
        self.value["durationSeconds"]=180.1;self.failure.write_text(json.dumps(self.value))
        with self.assertRaises(EvidenceError):inventory(self.root,self.plan,"b"*64)
    def test_conflicting_receipt_rejected(self):
        (self.root/".receipts").mkdir();(self.root/".receipts/stress-r1.json").write_text("{}")
        with self.assertRaises(EvidenceError):inventory(self.root,self.plan,"a"*64)
    def test_timeout_with_partial_directory_rejected(self):
        (self.root/"stress-r1").mkdir()
        with self.assertRaises(EvidenceError):inventory(self.root,self.plan,"a"*64)
        with self.assertRaises(EvidenceError):timeout_record(self.failure,self.run,"a"*64,self.root)
    def test_later_timeout_cannot_defer_earlier_pending_run(self):
        self.plan["runs"]=[self.plan["runs"][1],self.plan["runs"][0],self.plan["runs"][2]]
        with self.assertRaises(EvidenceError):inventory(self.root,self.plan,"a"*64)
    def test_unknown_artifact_rejected(self):
        (self.root/"unknown.json").write_text("{}")
        with self.assertRaises(EvidenceError):inventory(self.root,self.plan,"a"*64)
if __name__=="__main__":unittest.main()
