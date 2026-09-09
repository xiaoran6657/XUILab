"""Synthetic historical provenance regressions; these do not constitute Player evidence."""
import copy
import hashlib
import json
from pathlib import Path, PureWindowsPath
import tempfile
import unittest
from historical_verify import build_provenance, recorded_path
from operation_journal import Journal, canonical

class HistoricalTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.root=Path(self.temp.name);self.original=PureWindowsPath("<repo>")
        source=self.root/"XUILab/Assets/a.cs";source.parent.mkdir(parents=True);source.write_text("fixture")
        output=self.root/"Artifacts/build/app.exe";output.parent.mkdir(parents=True);output.write_bytes(b"synthetic fixture, not Player")
        self.output="Artifacts/build/app.exe"
        false={k:False for k in ("playing","paused","compiling","importing","tests_running","build_running","prefab_stage","dirty_scene")}
        self.request=dict(schema="xuilab.unity-operation/v1",kind="build",task="M2-04",candidate="fixture",attempt="r1",instance="fixture-instance",operator="fixture",project="XUILab",editor="2022.3.45f1c1",parameters=dict(output_path=self.output,platform="StandaloneWindows64"),inputs={"XUILab/Assets/a.cs":self.sha(source)},before=false,restore_expected=false,artifacts=[self.output])
        self.journal=Journal(self.root);self.operation=self.journal.prepare(self.request);self.dir=self.journal.directory(self.operation)
        self.receipt=self.envelope({"job_id":"fixture-job"},"2026-09-07T10:00:00Z")
        self.terminal=dict(evidence=self.envelope(dict(job_id="fixture-job",result="succeeded",errors=0,platform="StandaloneWindows64",output_path=str(self.original/PureWindowsPath(self.output)),completed_at="2026-09-07T10:00:01Z"),"2026-09-07T10:00:02Z"),outcome="pass",artifacts={self.output:self.sha(output)})
        self.restore=dict(operation=self.operation,project_root=str(self.original/"XUILab"),observed_at="2026-09-07T10:00:03Z",state=false,raw={"fixture":True})
        self.manifest=dict(buildOperation=self.operation,sourceInputs=self.request["inputs"])
        self.write()
    def tearDown(self):self.temp.cleanup()
    @staticmethod
    def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
    def envelope(self,data,at):return dict(operation=self.operation,candidate="fixture",instance="fixture-instance",project_root=str(self.original/"XUILab"),observed_at=at,response=dict(success=True,data=data))
    def write(self):
        for name,data in (("claim",{"operation":self.operation}),("receipt",self.receipt),("terminal",self.terminal),("restore",self.restore)):
            (self.dir/(name+".json")).write_bytes(canonical(data)+b"\n")
        self.manifest.update(buildRequestSha256=self.sha(self.dir/"request.json"),buildTerminalSha256=self.sha(self.dir/"terminal.json"))
    def verify(self):return build_provenance(self.root,self.manifest,{"candidateId":"fixture"},self.original)
    def test_relocated_archive_accepts_recorded_path_without_rewrite(self):
        before=(self.dir/"terminal.json").read_bytes();self.assertEqual(self.verify(),self.output);self.assertEqual(before,(self.dir/"terminal.json").read_bytes())
    def test_changed_native_project_root_rejected_even_rehashed(self):
        self.terminal["evidence"]["project_root"]="H:/wrong/XUILab";self.write()
        with self.assertRaises(ValueError):self.verify()
    def test_changed_native_output_rejected_even_rehashed(self):
        self.terminal["evidence"]["response"]["data"]["output_path"]="G:/Programming/Other/app.exe";self.write()
        with self.assertRaises(ValueError):self.verify()
    def test_wrong_job_rejected_even_rehashed(self):
        self.terminal["evidence"]["response"]["data"]["job_id"]="another";self.write()
        with self.assertRaises(ValueError):self.verify()
    def test_failed_build_rejected_even_rehashed(self):
        self.terminal["evidence"]["response"]["data"]["errors"]=1;self.write()
        with self.assertRaises(ValueError):self.verify()
    def test_restore_before_terminal_rejected(self):
        self.restore["observed_at"]="2026-09-07T09:00:00Z";self.write()
        with self.assertRaises(ValueError):self.verify()
    def test_source_drift_rejected(self):
        (self.root/"XUILab/Assets/a.cs").write_text("changed")
        with self.assertRaises(ValueError):self.verify()
    def test_output_drift_rejected(self):
        (self.root/self.output).write_bytes(b"changed")
        with self.assertRaises(ValueError):self.verify()
    def test_path_traversal_not_normalized_into_success(self):
        with self.assertRaises(ValueError):recorded_path("G:/Programming/foo/../XUILab",self.original)


    def test_copied_tooling_is_required(self):
        from historical_verify import archive_tooling
        with self.assertRaisesRegex(ValueError,"copied archive verifier"):archive_tooling(self.root)
    def test_wrong_external_manifest_anchor_is_rejected(self):
        from historical_verify import verify
        from unittest.mock import patch
        (self.root/"baseline-manifest.json").write_text("{}")
        with patch("historical_verify.archive_tooling"):
            with self.assertRaisesRegex(ValueError,"External archive manifest"):verify(self.root,"0"*64)
    def test_prepolicy_timeout_requires_exact_pinned_bytes(self):
        from historical_verify import timeout_policy
        path=self.root/"failure.json";path.write_text("original")
        timeout_policy({"runId":"original"},path,"1"*64,{"original":self.sha(path)})
        path.write_text("modified")
        with self.assertRaises(ValueError):timeout_policy({"runId":"original"},path,"1"*64,{"original":"0"*64})
    def test_resumed_timeout_requires_correct_policy(self):
        from historical_verify import timeout_policy
        path=self.root/"failure.json";path.write_text("resumed")
        timeout_policy({"runId":"resumed","resumePolicySha256":"1"*64},path,"1"*64,{})
        with self.assertRaises(ValueError):timeout_policy({"runId":"resumed","resumePolicySha256":"2"*64},path,"1"*64,{})
    def test_resumed_timeout_missing_policy_rejected(self):
        from historical_verify import timeout_policy
        path=self.root/"failure.json";path.write_text("resumed")
        with self.assertRaises(ValueError):timeout_policy({"runId":"resumed"},path,"1"*64,{})
    def make_gate(self):
        self.request["kind"]="test";self.request["parameters"]={"mode":"PlayMode","assembly_names":["Fixture.Tests"]};self.request["artifacts"]=[]
        self.operation=self.journal.prepare(self.request);self.dir=self.journal.directory(self.operation)
        self.receipt=self.envelope({"job_id":"test-job"},"2026-09-07T10:00:00Z")
        self.terminal=dict(evidence=self.envelope(dict(job_id="test-job",status="succeeded",mode="PlayMode",finished_unix_ms=1),"2026-09-07T10:00:02Z"),outcome="pass",artifacts={})
        self.restore["operation"]=self.operation;self.write()
        evidence=self.root/"gate-terminal.json";evidence.write_bytes(canonical(self.terminal["evidence"])+b"\n")
        return {"terminalPath":"gate-terminal.json","requestSha256":self.sha(self.dir/"request.json")}
    def test_gate_journal_closure(self):
        from historical_verify import gate_closure
        check=self.make_gate();gate_closure(self.root,check,self.original)
    def test_gate_missing_restore_rejected(self):
        from historical_verify import gate_closure
        check=self.make_gate();(self.dir/"restore.json").unlink()
        with self.assertRaises((ValueError,OSError)):gate_closure(self.root,check,self.original)
    def test_gate_wrong_receipt_job_rejected(self):
        from historical_verify import gate_closure
        check=self.make_gate();self.receipt["response"]["data"]["job_id"]="other";self.write()
        with self.assertRaises(ValueError):gate_closure(self.root,check,self.original)
    def test_gate_missing_claim_rejected(self):
        from historical_verify import gate_closure
        check=self.make_gate();(self.dir/"claim.json").unlink()
        with self.assertRaises((ValueError,OSError)):gate_closure(self.root,check,self.original)


    def test_after_timeout_only_deferrals_are_allowed(self):
        from historical_verify import recovery_order
        runs=self.root/"runs";runs.mkdir()
        plan={"runs":[{"runId":"a1","caseId":"a"},{"runId":"b1","caseId":"b"},{"runId":"a2","caseId":"a"}]}
        (runs/"a1-orchestration-failure.json").write_text("{}")
        (runs/"a2-deferred.json").write_text("{}")
        recovery_order(plan,runs)
    def test_receipt_after_same_case_timeout_rejected(self):
        from historical_verify import recovery_order
        runs=self.root/"runs";runs.mkdir();(runs/".receipts").mkdir()
        plan={"runs":[{"runId":"a1","caseId":"a"},{"runId":"a2","caseId":"a"}]}
        (runs/"a1-orchestration-failure.json").write_text("{}")
        (runs/".receipts/a2.json").write_text("{}")
        with self.assertRaises(ValueError):recovery_order(plan,runs)
    def test_second_same_case_timeout_rejected(self):
        from historical_verify import recovery_order
        runs=self.root/"runs";runs.mkdir()
        plan={"runs":[{"runId":"a1","caseId":"a"},{"runId":"a2","caseId":"a"}]}
        for rid in ("a1","a2"):(runs/(rid+"-orchestration-failure.json")).write_text("{}")
        with self.assertRaises(ValueError):recovery_order(plan,runs)

if __name__=="__main__":unittest.main()
