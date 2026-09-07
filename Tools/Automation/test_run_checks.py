"""Offline tests for the explicit check scheduler.

The executor is mocked, so this suite never launches the scheduler recursively
and never invokes Unity, a Player, or a network client.
"""

from __future__ import annotations

import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import Mock

from run_checks import (
    ALLOWED_CHECKS,
    AutomationError,
    build_plan,
    inspect_run,
    run_checks,
)


class OfflineChecksTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory(prefix="xuilab-automation-")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        tools = self.root / "Tools"
        tools.mkdir(parents=True)
        (tools / "check_offline.py").write_text("# fixture\n", encoding="utf-8")
        for name in ALLOWED_CHECKS[1:]:
            (tools / name).mkdir(parents=True)
            (tools / name / "test_placeholder.py").write_text("import unittest" + chr(10) + "class Placeholder(unittest.TestCase):" + chr(10) + "    def test_fixture(self):" + chr(10) + "        self.assertTrue(True)" + chr(10), encoding="utf-8")

    def executor(self, returncodes=(0,)) -> Mock:
        values = iter(returncodes)

        def complete(*_args, **_kwargs):
            return subprocess.CompletedProcess(
                args=_args[0], returncode=next(values), stdout="ok\n", stderr=""
            )

        return Mock(side_effect=complete)

    def test_plan_is_fixed_order_and_uses_no_shell(self) -> None:
        plan = build_plan(
            self.root,
            ["Automation", "check_offline", "Archiving"],
            timeout_seconds=17,
        )
        self.assertEqual(plan["checks"], ["check_offline", "Archiving", "Automation"])
        self.assertEqual(
            plan["commands"][0]["argv"][1:3],
            ["-B", str(self.root / "Tools/check_offline.py")],
        )
        self.assertTrue(
            all(command["kind"] in {"script", "unittest"} for command in plan["commands"])
        )

    def test_run_persists_terminal_records_and_returns_failure_for_nonzero(self) -> None:
        executor = self.executor((0, 3))
        result = run_checks(
            "nonzero-case",
            self.root,
            ["check_offline", "ProjectManagement"],
            timeout_seconds=9,
            executor=executor,
        )
        run_dir = self.root / "Artifacts/offline-checks/nonzero-case"
        self.assertEqual(result["status"], "failed")
        self.assertEqual(
            json.loads((run_dir / "state.json").read_text())["status"], "failed"
        )
        self.assertEqual(
            len(json.loads((run_dir / "result.json").read_text())["commands"]), 2
        )
        self.assertTrue(
            all(call.kwargs["shell"] is False for call in executor.call_args_list)
        )

    def test_timeout_is_a_terminal_failure_without_retry(self) -> None:
        executor = Mock(
            side_effect=subprocess.TimeoutExpired(["fixed"], 1, output="partial")
        )
        result = run_checks(
            "timeout-case", self.root, ["check_offline"], executor=executor
        )
        self.assertEqual(result["status"], "failed")
        self.assertEqual(result["commands"][0]["status"], "timeout")
        self.assertEqual(executor.call_count, 1)

    def test_duplicate_run_id_is_rejected_before_execution(self) -> None:
        executor = self.executor()
        run_checks("same-id", self.root, ["check_offline"], executor=executor)
        with self.assertRaises(AutomationError):
            run_checks("same-id", self.root, ["check_offline"], executor=executor)
        self.assertEqual(executor.call_count, 1)

    def test_interrupted_run_is_needs_review_and_inspect_does_not_retry(self) -> None:
        executor = Mock(side_effect=KeyboardInterrupt)
        with self.assertRaises(KeyboardInterrupt):
            run_checks("interrupted-case", self.root, ["check_offline"], executor=executor)
        observed = inspect_run("interrupted-case", self.root)
        self.assertEqual(observed["status"], "needs_review")
        self.assertEqual(executor.call_count, 1)

    def test_rejects_empty_selected_directory(self) -> None:
        (self.root / "Tools/Archiving/test_placeholder.py").unlink()
        with self.assertRaises(AutomationError):
            build_plan(self.root, ["Archiving"])

    def test_rejects_arbitrary_check_and_invalid_ids(self) -> None:
        with self.assertRaises(AutomationError):
            build_plan(self.root, ["echo", "check_offline"])
        with self.assertRaises(AutomationError):
            run_checks(
                "../escape", self.root, ["check_offline"], executor=self.executor()
            )

    def test_inspect_rejects_tampered_terminal_identity(self) -> None:
        executor = self.executor()
        run_checks("tamper-case", self.root, ["check_offline"], executor=executor)
        result_path = self.root / "Artifacts/offline-checks/tamper-case/result.json"
        value = json.loads(result_path.read_text(encoding="utf-8"))
        value["run_id"] = "other"
        result_path.write_text(json.dumps(value), encoding="utf-8")
        with self.assertRaises(AutomationError):
            inspect_run("tamper-case", self.root)


    def test_inspect_accepts_genuine_terminal_records(self) -> None:
        executor = self.executor((0,))
        run_checks("genuine-pass", self.root, ["check_offline"], executor=executor)
        observed = inspect_run("genuine-pass", self.root)
        self.assertEqual(observed["status"], "passed")
        self.assertEqual(observed["commands"][0]["exit_code"], 0)

    def test_inspect_rejects_double_file_status_forgery(self) -> None:
        executor = self.executor((7,))
        run_checks("double-status-forgery", self.root, ["check_offline"], executor=executor)
        run_dir = self.root / "Artifacts/offline-checks/double-status-forgery"
        state_path = run_dir / "state.json"
        result_path = run_dir / "result.json"
        state = json.loads(state_path.read_text(encoding="utf-8"))
        result = json.loads(result_path.read_text(encoding="utf-8"))
        state["status"] = "passed"
        result["status"] = "passed"
        state_path.write_text(json.dumps(state), encoding="utf-8")
        result_path.write_text(json.dumps(result), encoding="utf-8")
        with self.assertRaisesRegex(AutomationError, "status does not match command evidence"):
            inspect_run("double-status-forgery", self.root)

    def test_inspect_rejects_plan_command_identity_tamper(self) -> None:
        executor = self.executor()
        run_checks("command-tamper", self.root, ["check_offline"], executor=executor)
        plan_path = self.root / "Artifacts/offline-checks/command-tamper/plan.json"
        plan = json.loads(plan_path.read_text(encoding="utf-8"))
        plan["commands"][0]["argv"][0] = "powershell.exe"
        plan_path.write_text(json.dumps(plan), encoding="utf-8")
        with self.assertRaisesRegex(AutomationError, "command identity"):
            inspect_run("command-tamper", self.root)

    def test_inspect_rejects_exit_code_and_status_disagreement(self) -> None:
        executor = self.executor((5,))
        run_checks("exit-tamper", self.root, ["check_offline"], executor=executor)
        result_path = self.root / "Artifacts/offline-checks/exit-tamper/result.json"
        result = json.loads(result_path.read_text(encoding="utf-8"))
        result["commands"][0]["exit_code"] = 0
        result_path.write_text(json.dumps(result), encoding="utf-8")
        with self.assertRaisesRegex(AutomationError, "status and exit_code disagree"):
            inspect_run("exit-tamper", self.root)


if __name__ == "__main__":
    unittest.main()
