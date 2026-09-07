"""Contract regressions using isolated Markdown repositories, never live PM."""
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from check_pm import check


class PMContractTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="xuilab-pm-")
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name).resolve()
        for name in ("AGENTS.md", "README.md", "Docs/README.md"):
            self.write(name, "# Navigation\n")
        self.write("Docs/MVP/ROADMAP.md", "# Roadmap\n| M2-01 | Contract |\n")
        self.task = self.make_task("INFRA-001")
        self.write("Docs/PM/PROJECT_STATUS.md", "- current_task: none\n- latest_task: [Last](Tasks/INFRA-001/TASK_STATUS.md)\n- unity_owner: none\n- unity_task: none\n")
        self.write("Docs/PM/Next_Actions.md", "# Next Actions\n")

    def write(self, name, text):
        path = self.root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
        return path

    def replace(self, path, old, new):
        text = path.read_text(encoding="utf-8")
        self.assertIn(old, text)
        path.write_text(text.replace(old, new), encoding="utf-8")

    def make_task(self, task_id, state="done", kind="infra"):
        base = f"Docs/PM/Tasks/{task_id}/"
        self.write(base + "TASK_BRIEF.md", f"""# Brief
- brief_revision: r1
- task_type: {kind}
- risk: R1
- review_required: false
- execution_required: false

## 验收矩阵

| ID | requirement | 判据 |
| --- | --- | --- |
| A1 | required | Verify the actual navigation. |
""")
        self.write(base + "EVIDENCE.md", "# Evidence\n- candidate: candidate-1\n- brief_revision: r1\nActual checks.\n")
        return self.write(base + "TASK_STATUS.md", f"""# Status
- pm_schema: xuilab.pm/v1
- task_id: {task_id}
- task_type: {kind}
- state: {state}
- brief: [Brief](TASK_BRIEF.md)
- brief_revision: r1
- candidate: candidate-1
- dependencies: none
- blockers: none
- recovery: none
- next_action: Await new authorization.
- review: not_run
- verification: not_run
- review_independence: self-check
- execution_independence: self-check

## 验收状态

| ID | result | candidate | evidence |
| --- | --- | --- | --- |
| A1 | pass | candidate-1 | [Evidence](EVIDENCE.md) |
""")

    def rejected(self, fragment):
        result = check(self.root)
        self.assertTrue(any(fragment in error for error in result.errors), result.errors)

    def test_valid_repository_and_checker_is_read_only(self):
        before = {p.relative_to(self.root): p.read_bytes() for p in self.root.rglob("*") if p.is_file()}
        result = check(self.root)
        self.assertEqual([], result.errors)
        self.assertEqual(1, result.strict_tasks)
        after = {p.relative_to(self.root): p.read_bytes() for p in self.root.rglob("*") if p.is_file()}
        self.assertEqual(before, after)

    def test_r0_can_link_inline_self_check(self):
        self.replace(self.task.with_name("TASK_BRIEF.md"), "risk: R1", "risk: R0")
        self.replace(self.task, "[Evidence](EVIDENCE.md)", "[Self check](TASK_STATUS.md#交接)")
        self.task.write_text(self.task.read_text(encoding="utf-8") + "\n## 交接\nChecked target documents; source hash recorded here.\n", encoding="utf-8")
        self.assertEqual([], check(self.root).errors)

    def test_invalid_missing_or_duplicate_fields(self):
        original = self.task.read_text(encoding="utf-8")
        for old, new, error in (
            ("state: done", "state: DONE", "invalid state"),
            ("- state: done\n", "", "missing field state"),
            ("state: done", "state: done\n- state: running", "duplicate field state"),
            ("pm_schema: xuilab.pm/v1", "pm_schema: xuilab.pm/v9", "unknown or missing pm_schema"),
            ("- pm_schema: xuilab.pm/v1\n", "", "unknown or missing pm_schema"),
        ):
            with self.subTest(error=error):
                self.task.write_text(original.replace(old, new), encoding="utf-8")
                self.rejected(error)

    def test_mvp_type_requires_roadmap_id(self):
        self.make_task("M2-01", kind="mvp")
        self.assertEqual([], check(self.root).errors)
        self.make_task("M2-99", kind="mvp")
        self.rejected("MVP IDs must be in roadmap")

    def test_done_cannot_bypass_required_or_omit_acceptance(self):
        original = self.task.read_text(encoding="utf-8")
        for replacement, message in (
            ("| A1 | not_run | candidate-1 | [Evidence](EVIDENCE.md) |", "required acceptance not passed"),
            ("| A1 | not_applicable | candidate-1 | [Evidence](EVIDENCE.md) |", "required acceptance not passed"),
            ("| A2 | pass | candidate-1 | [Evidence](EVIDENCE.md) |", "acceptance IDs differ"),
        ):
            with self.subTest(replacement=replacement):
                self.task.write_text(original.replace("| A1 | pass | candidate-1 | [Evidence](EVIDENCE.md) |", replacement), encoding="utf-8")
                self.rejected(message)

    def test_evidence_must_exist_be_file_and_match_candidate(self):
        original = self.task.read_text(encoding="utf-8")
        for old, new, error in (
            ("| pass | candidate-1 |", "| pass | candidate-2 |", "acceptance candidate mismatch"),
            ("[Evidence](EVIDENCE.md)", "[Missing](absent.md)", "existing evidence files"),
            ("[Evidence](EVIDENCE.md)", "[Directory](.)", "existing evidence files"),
            ("[Evidence](EVIDENCE.md)", "[Remote](https://example.com/report)", "existing evidence files"),
        ):
            with self.subTest(new=new):
                self.task.write_text(original.replace(old, new), encoding="utf-8")
                self.rejected(error)

    def test_review_acceptance_and_identity(self):
        self.replace(self.task.with_name("TASK_BRIEF.md"), "review_required: false", "review_required: true")
        self.rejected("done requires independent accepted review")
        self.write("Docs/PM/Tasks/INFRA-001/REVIEW.md", "- candidate: candidate-1\n- brief_revision: r1\n- verdict: accept\n")
        self.replace(self.task, "review: not_run", "review: [Review](REVIEW.md)")
        self.replace(self.task, "review_independence: self-check", "review_independence: independent")
        self.assertEqual([], check(self.root).errors)
        report = self.task.with_name("REVIEW.md")
        self.replace(report, "verdict: accept", "verdict: changes_requested")
        self.rejected("done conflicts with review verdict")
        self.replace(report, "candidate: candidate-1", "candidate: wrong-candidate")
        self.rejected("review candidate mismatch")
        self.replace(report, "brief_revision: r1", "brief_revision: r2")
        self.rejected("review brief_revision mismatch")

    def test_execution_independence_is_separate_from_review(self):
        self.replace(self.task.with_name("TASK_BRIEF.md"), "execution_required: false", "execution_required: true")
        self.replace(self.task, "verification: not_run", "verification: [Evidence](EVIDENCE.md)")
        self.rejected("done requires independent verification")
        self.replace(self.task, "execution_independence: self-check", "execution_independence: independent")
        self.assertEqual([], check(self.root).errors)

    def test_r2_requires_review_contract(self):
        self.replace(self.task.with_name("TASK_BRIEF.md"), "risk: R1", "risk: R2")
        self.rejected("R2/R3 requires independent review")

    def test_missing_unfinished_and_cyclic_dependencies(self):
        self.replace(self.task, "dependencies: none", "dependencies: [Dependency](../INFRA-002/TASK_STATUS.md)")
        self.rejected("dependency is not a known")
        other = self.make_task("INFRA-002", "proposed")
        self.rejected("unfinished dependency")
        self.replace(other, "state: proposed", "state: done")
        self.assertEqual([], check(self.root).errors)
        self.replace(other, "dependencies: none", "dependencies: [Dependency](../INFRA-001/TASK_STATUS.md)")
        self.rejected("dependency cycle")

    def test_blocked_requires_recovery(self):
        self.replace(self.task, "state: done", "state: blocked")
        self.rejected("blocked requires blockers and recovery")

    def test_global_owner_pairing_duplicates_and_terminal_pointer(self):
        path = self.root / "Docs/PM/PROJECT_STATUS.md"
        original = path.read_text(encoding="utf-8")
        for old, new, message in (
            ("unity_owner: none", "unity_owner: a\n- unity_owner: b", "duplicate field unity_owner"),
            ("unity_owner: none", "unity_owner: a,b", "one owner ID"),
            ("unity_owner: none", "unity_owner: a", "owner/task must be paired"),
            ("current_task: none", "current_task: [Current](Tasks/INFRA-001/TASK_STATUS.md)", "current_task contradicts"),
        ):
            with self.subTest(new=new):
                path.write_text(original.replace(old, new), encoding="utf-8")
                self.rejected(message)

    def test_terminal_or_duplicate_task_cannot_be_queued(self):
        self.write("Docs/PM/Next_Actions.md", "1. [Task](Tasks/INFRA-001/TASK_STATUS.md)\n2. [Task](Tasks/INFRA-001/TASK_STATUS.md)\n")
        self.rejected("terminal task in Next Actions")
        self.rejected("duplicate queued task")

    def test_legacy_is_explicit_limited_coverage(self):
        self.write("Docs/PM/Tasks/M0-04/TASK_STATUS.md", "- state：done（r7 accepted）\n")
        self.replace(self.task, "dependencies: none", "dependencies: [Legacy](../M0-04/TASK_STATUS.md)")
        result = check(self.root)
        self.assertEqual([], result.errors)
        self.assertEqual(1, result.legacy_tasks)
        self.assertTrue(any("legacy state only" in warning for warning in result.warnings))
        self.write("Docs/PM/Tasks/INFRA-999/TASK_STATUS.md", "- state：done\n")
        self.rejected("unknown or missing pm_schema")

    def test_navigation_links_and_optional_artifacts(self):
        self.write("README.md", "# Navigation\n[Missing](Docs/no-such-file.md)\n[Optional](Artifacts/unavailable.csv)\n```markdown\n[Example](not-a-file.md)\n```\n[Placeholder](<path>)\n")
        result = check(self.root)
        self.assertTrue(any("Docs/no-such-file" in error for error in result.errors))
        self.assertFalse(any("not-a-file" in error or "<path>" in error for error in result.errors))
        self.assertTrue(any("Artifacts/unavailable" in warning for warning in result.warnings))

    def test_repository_escape_is_rejected(self):
        self.write("README.md", "[Escape](../outside.md)\n")
        self.rejected("link outside repository")

    def test_malformed_link_reports_error_without_crashing(self):
        self.write("README.md", "[Malformed](http://[)\n")
        self.rejected("malformed link")

    def test_cli_root_from_another_working_directory_and_exit_codes(self):
        command = [sys.executable, "-B", str(Path(__file__).with_name("check_pm.py").resolve()), "--root", str(self.root)]
        valid = subprocess.run(command, cwd=self.root, capture_output=True, text=True)
        self.assertEqual(0, valid.returncode, valid.stdout + valid.stderr)
        self.assertIn("PM structure PASS", valid.stdout)
        self.replace(self.task, "state: done", "state: fabricated")
        invalid = subprocess.run(command, cwd=self.root, capture_output=True, text=True)
        self.assertEqual(1, invalid.returncode, invalid.stdout + invalid.stderr)
        self.assertIn("PM structure FAIL", invalid.stdout)


if __name__ == "__main__":
    unittest.main()
