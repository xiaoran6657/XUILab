"""Deterministic safety tests for the frozen List Lab plan resumer."""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, str(Path(__file__).parent))

import resume_list_plan as resume
import verify_list_runs as verifier


class FakeProcess:
    """Small controlled child used instead of a real Unity Player."""

    next_pid = 1000

    def __init__(self, command, root: Path, timeout: bool = False, exit_code: int = 0, write_run: bool = True):
        self.command = list(command)
        self.root = root
        self.timeout = timeout
        self.returncode = None
        self.pid = FakeProcess.next_pid
        FakeProcess.next_pid += 1
        self.kill_calls = 0
        self.write_run = write_run
        self._started = False
        if self.write_run and not self.timeout:
            run_id = self.command[self.command.index("--xuilab-run-id") + 1]
            run_root = Path(self.command[self.command.index("--xuilab-output-root") + 1])
            run_dir = run_root / run_id
            run_dir.mkdir()
            for name in verifier.LIST_ARTIFACTS:
                (run_dir / name).write_text("fake\n", encoding="utf-8")
            (run_dir / "config.json").write_text(
                json.dumps({
                    "seriesId": self.command[self.command.index("--xuilab-series-id") + 1],
                    "outputDirectory": str(run_root),
                }),
                encoding="utf-8",
            )

    def wait(self, timeout=None):
        if self.timeout and self.kill_calls == 0:
            raise __import__("subprocess").TimeoutExpired(self.command[0], timeout)
        if self.returncode is None:
            self.returncode = 0
        return self.returncode

    def poll(self):
        return self.returncode

    def kill(self):
        self.kill_calls += 1
        self.returncode = -9


class ResumeFixture:
    def __init__(self, base: Path, filename: str = "series-pilot-manifest.json"):
        self.base = base
        self.root = base / "artifacts"
        self.root.mkdir()
        self.manifest_path = self.root / filename
        self.plan = "pilot"
        self.series_id = "series-pilot"
        self.manifest = {
            "candidateId": "candidate-test",
            "buildId": "build-test",
            "sourceRevision": "source-test",
            "runs": [],
        }
        for index, expected in enumerate(verifier._expected_plan_specs(self.plan), 1):
            item = dict(expected)
            item["runId"] = "{}-{}".format(self.series_id, index)
            self.manifest["runs"].append(item)
        self.manifest_path.write_text(json.dumps(self.manifest, indent=2) + "\n", encoding="utf-8")
        self.player = base / "build" / "XUILab.exe"
        self.player.parent.mkdir()
        self.player.write_bytes(b"player-frozen")
        self.hash_path = self.root / "series-pilot-build-hashes.json"
        self.hash_path.write_text(
            json.dumps({str(self.player): hashlib.sha256(self.player.read_bytes()).hexdigest()}) + "\n",
            encoding="utf-8",
        )

    def record(self, run_index: int, artifact_hash: str = "A" * 64, output_directory: Path | None = None) -> None:
        spec = self.manifest["runs"][run_index - 1]
        run_dir = self.root / spec["runId"]
        run_dir.mkdir(exist_ok=True)
        for name in verifier.LIST_ARTIFACTS:
            path = run_dir / name
            if not path.exists():
                path.write_text("fake\n", encoding="utf-8")
        (run_dir / "config.json").write_text(
            json.dumps({
                "seriesId": self.series_id,
                "outputDirectory": str(output_directory or self.root),
            }),
            encoding="utf-8",
        )
        record = {"artifactSetSha256": artifact_hash}
        (self.root / (spec["runId"] + "-receipt.json")).write_text(
            json.dumps({
                "runId": spec["runId"], "pid": 1, "exitCode": 0,
                "durationSeconds": 1.0, "completedUtc": "2026-09-07T00:00:00Z",
                "artifactSetSha256": record["artifactSetSha256"],
            }),
            encoding="utf-8",
        )


class ResumeTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="xuilab-resume-")
        self.fixture = ResumeFixture(Path(self.temp.name))
        self.hash_value = "A" * 64
        self.validate_calls = []

        def fake_validate(root, spec, manifest, recorded_root=None):
            self.validate_calls.append((spec["runId"], recorded_root))
            return {"record": {"artifactSetSha256": self.hash_value}}

        self.validator_patch = mock.patch.object(resume.verifier, "_validate_run", side_effect=fake_validate)
        self.validator_patch.start()
        self.addCleanup(self.validator_patch.stop)

    def tearDown(self):
        self.temp.cleanup()

    def inspect(self, **kwargs):
        return resume.inspect_plan(
            self.fixture.root, self.fixture.manifest_path,
            build_hashes_path=self.fixture.hash_path, **kwargs,
        )

    def execute(self, **kwargs):
        return resume.execute_plan(
            self.fixture.root, self.fixture.manifest_path, self.fixture.player,
            build_hashes_path=self.fixture.hash_path, **kwargs,
        )

    def test_default_inspection_classifies_completed_failed_pending_and_blocked(self):
        self.fixture.record(1, self.hash_value)
        failed_id = self.fixture.manifest["runs"][1]["runId"]
        (self.fixture.root / (failed_id + resume.FAILURE_SUFFIX)).write_text(json.dumps({
            "runId": failed_id, "pid": 7, "timeout": False, "exitCode": 1,
            "reason": "fixture failure", "durationSeconds": 0.1,
        }), encoding="utf-8")
        partial_id = self.fixture.manifest["runs"][2]["runId"]
        (self.fixture.root / partial_id).mkdir()
        (self.fixture.root / partial_id / "samples.csv").write_text("partial", encoding="utf-8")
        result = self.inspect()
        self.assertEqual(
            [item["status"] for item in result["runs"]],
            ["completed", "failed", "invalid", "pending"],
        )
        self.assertEqual(result["counts"]["completed"], 1)

    def test_missing_or_mismatched_receipt_is_invalid(self):
        self.fixture.record(1, self.hash_value)
        (self.fixture.root / (self.fixture.manifest["runs"][0]["runId"] + resume.RECEIPT_SUFFIX)).unlink()
        self.assertEqual(self.inspect()["runs"][0]["status"], "invalid")
        self.fixture.record(1, "B" * 64)
        self.assertEqual(self.inspect()["runs"][0]["status"], "invalid")

    def test_explicit_series_cannot_override_frozen_filename(self):
        with self.assertRaisesRegex(resume.ResumeError, "conflicts with manifest filename"):
            self.execute(series_id="wrong-series")
        self.assertEqual(self.fixture.series_id, self.inspect(series_id=self.fixture.series_id)["seriesId"])
        self.assertFalse(list(self.fixture.root.glob("*" + resume.INTENT_SUFFIX)))

    def test_explicit_series_cannot_override_existing_generic_manifest_config(self):
        self.fixture.record(1, self.hash_value)
        generic=self.fixture.root/'manifest.json'
        generic.write_bytes(self.fixture.manifest_path.read_bytes())
        with self.assertRaisesRegex(resume.ResumeError, "conflicts with existing config"):
            resume.inspect_plan(self.fixture.root,generic,plan='pilot',series_id='wrong-series')

    def test_unknown_run_prefixed_remnant_blocks_pending_and_completed(self):
        run_id=self.fixture.manifest['runs'][0]['runId']
        unknown=self.fixture.root/(run_id+'-unknown.txt'); unknown.write_bytes(b'preserve me')
        for completed in (False,True):
            if completed: self.fixture.record(1,self.hash_value)
            self.assertEqual('invalid',self.inspect()['runs'][0]['status'])
            with self.assertRaisesRegex(resume.ResumeError, 'blocked runs'): self.execute()
            self.assertEqual(b'preserve me',unknown.read_bytes())

    def test_durable_intent_is_interrupted_and_never_auto_unlocked(self):
        run_id = self.fixture.manifest["runs"][0]["runId"]
        (self.fixture.root / (run_id + resume.INTENT_SUFFIX)).write_text("{}", encoding="utf-8")
        self.assertEqual(self.inspect()["runs"][0]["status"], "interrupted")
        with self.assertRaisesRegex(resume.ResumeError, "blocked runs"):
            self.execute()
        self.assertTrue((self.fixture.root / (run_id + resume.INTENT_SUFFIX)).exists())

    def test_second_resume_does_not_duplicate_completed_runs(self):
        processes = []

        def spawn(command, **kwargs):
            process = FakeProcess(command, self.fixture.root)
            processes.append(process)
            return process

        with mock.patch.object(resume.subprocess, "Popen", side_effect=spawn):
            result = self.execute()
            again = self.execute()
        self.assertEqual(result["counts"], {"completed": 4})
        self.assertEqual(again["counts"], {"completed": 4})
        self.assertEqual(len(processes), 4)
        self.assertFalse(list(self.fixture.root.glob("*" + resume.INTENT_SUFFIX)))
        self.assertFalse((self.fixture.root / (self.fixture.manifest_path.name + resume.LOCK_SUFFIX)).exists())

    def test_changed_build_is_rejected_before_child_or_intent(self):
        spawned = []

        def spawn(command, **kwargs):
            spawned.append(command)
            return FakeProcess(command, self.fixture.root)

        self.fixture.record(1, self.hash_value)
        self.fixture.player.write_bytes(b"changed")
        with mock.patch.object(resume.subprocess, "Popen", side_effect=spawn):
            with self.assertRaisesRegex(resume.ResumeError, "build changed"):
                self.execute()
        self.assertEqual(spawned, [])
        self.assertFalse(list(self.fixture.root.glob("*" + resume.INTENT_SUFFIX)))

    def test_last_child_drift_in_hashes_and_binary_is_rejected_before_success(self):
        for index in (1, 2, 3):
            self.fixture.record(index, self.hash_value)

        def spawn(command, **kwargs):
            return FakeProcess(command, self.fixture.root)

        original_execute_one = resume._execute_one

        def execute_then_drift(*args, **kwargs):
            original_execute_one(*args, **kwargs)
            self.fixture.player.write_bytes(b"changed-after-last-child")
            self.fixture.hash_path.write_text(json.dumps({
                str(self.fixture.player): hashlib.sha256(self.fixture.player.read_bytes()).hexdigest(),
            }), encoding="utf-8")

        with mock.patch.object(resume.subprocess, "Popen", side_effect=spawn):
            with mock.patch.object(resume, "_execute_one", side_effect=execute_then_drift):
                with self.assertRaisesRegex(resume.ResumeError, "build-hashes JSON changed"):
                    self.execute()
        self.assertFalse((self.fixture.root / (self.fixture.manifest_path.name + resume.LOCK_SUFFIX)).exists())

    def test_timeout_kills_only_exact_child_and_persists_failure(self):
        holder = []

        def spawn(command, **kwargs):
            process = FakeProcess(command, self.fixture.root, timeout=True, write_run=False)
            holder.append(process)
            return process

        with mock.patch.object(resume.subprocess, "Popen", side_effect=spawn):
            with self.assertRaisesRegex(resume.ResumeError, "timed out"):
                self.execute()
        self.assertEqual(len(holder), 1)
        self.assertEqual(holder[0].kill_calls, 1)
        run_id = self.fixture.manifest["runs"][0]["runId"]
        self.assertEqual(self.inspect()["runs"][0]["status"], "failed")
        self.assertFalse((self.fixture.root / (run_id + resume.INTENT_SUFFIX)).exists())

    def test_controlled_child_exit_writes_durable_failure(self):
        command = [sys.executable, "-c", "raise SystemExit(7)"]
        with mock.patch.object(resume, "_player_command", return_value=command):
            with self.assertRaisesRegex(resume.ResumeError, "Player exit 7"):
                self.execute()
        run_id = self.fixture.manifest["runs"][0]["runId"]
        sidecar = self.fixture.root / (run_id + resume.FAILURE_SUFFIX)
        self.assertTrue(sidecar.exists())
        self.assertEqual(json.loads(sidecar.read_text(encoding="utf-8"))["exitCode"], 7)
        self.assertFalse((self.fixture.root / (run_id + resume.INTENT_SUFFIX)).exists())

    def test_controlled_child_timeout_is_terminated(self):
        command = [sys.executable, "-c", "import time; time.sleep(2)"]
        with mock.patch.object(resume, "_player_command", return_value=command):
            with self.assertRaisesRegex(resume.ResumeError, "timed out"):
                self.execute(timeout_seconds=1)
        run_id = self.fixture.manifest["runs"][0]["runId"]
        failure = json.loads((self.fixture.root / (run_id + resume.FAILURE_SUFFIX)).read_text(encoding="utf-8"))
        self.assertTrue(failure["timeout"])
        self.assertFalse((self.fixture.root / (run_id + resume.INTENT_SUFFIX)).exists())

    def test_failure_requires_explicit_continue_and_pending_runs_continue_without_retry(self):
        first = []

        def timeout_spawn(command, **kwargs):
            process = FakeProcess(command, self.fixture.root, timeout=True, write_run=False)
            first.append(process)
            return process

        with mock.patch.object(resume.subprocess, "Popen", side_effect=timeout_spawn):
            with self.assertRaises(resume.ResumeError):
                self.execute()
        run_id = self.fixture.manifest["runs"][0]["runId"]
        sidecar = self.fixture.root / (run_id + resume.FAILURE_SUFFIX)
        before = sidecar.read_bytes()
        with self.assertRaisesRegex(resume.ResumeError, "continue-after-failure"):
            self.execute()

        def success_spawn(command, **kwargs):
            return FakeProcess(command, self.fixture.root)

        with mock.patch.object(resume.subprocess, "Popen", side_effect=success_spawn):
            result = self.execute(continue_after_failure=True)
        self.assertEqual(result["runs"][0]["status"], "failed")
        self.assertEqual(result["counts"], {"failed": 1, "completed": 3})
        self.assertEqual(sidecar.read_bytes(), before)
        self.assertEqual(len(first), 1)

    def test_failure_and_receipt_conflict_is_invalid(self):
        self.fixture.record(1, self.hash_value)
        run_id = self.fixture.manifest["runs"][0]["runId"]
        (self.fixture.root / (run_id + resume.FAILURE_SUFFIX)).write_text(json.dumps({
            "runId": run_id, "pid": 8, "timeout": False, "exitCode": 1,
            "reason": "conflicting evidence", "durationSeconds": 0.1,
        }), encoding="utf-8")
        self.assertEqual(self.inspect()["runs"][0]["status"], "invalid")

    def test_existing_plan_lock_blocks_without_replacing_lock(self):
        lock = self.fixture.root / (self.fixture.manifest_path.name + resume.LOCK_SUFFIX)
        lock.write_text("stale operator lock", encoding="utf-8")
        with self.assertRaisesRegex(resume.ResumeError, "plan lock already exists"):
            self.execute()
        self.assertEqual(lock.read_text(encoding="utf-8"), "stale operator lock")

    @unittest.skipUnless(os.name == "nt", "Windows short-path identity")
    def test_short_path_build_key_matches_resolved_player_and_rejects_alias_conflict(self):
        import ctypes
        from ctypes import wintypes
        get_short = ctypes.windll.kernel32.GetShortPathNameW
        get_short.argtypes = [wintypes.LPCWSTR, wintypes.LPWSTR, wintypes.DWORD]
        get_short.restype = wintypes.DWORD
        long_path = self.fixture.player.resolve()
        buffer = ctypes.create_unicode_buffer(32768)
        length = get_short(str(long_path), buffer, len(buffer))
        if not length or length >= len(buffer) or os.path.normcase(buffer.value) == os.path.normcase(str(long_path)):
            self.skipTest("Filesystem does not expose a distinct 8.3 alias")
        short_path = Path(buffer.value)
        digest = hashlib.sha256(long_path.read_bytes()).hexdigest()
        self.fixture.hash_path.write_text(json.dumps({str(short_path): digest}), encoding="utf-8")
        mapped = resume.verify_build_hashes(self.fixture.hash_path, long_path)
        self.assertEqual({str(long_path): digest.upper()}, mapped)
        self.fixture.hash_path.write_text(json.dumps({str(short_path): digest, str(long_path): "0" * 64}), encoding="utf-8")
        with self.assertRaisesRegex(resume.ResumeError, "two different hashes"):
            resume.verify_build_hashes(self.fixture.hash_path, long_path)

    def test_absolute_build_hashes_map_from_recorded_root(self):
        old_root = Path(self.temp.name) / "old-build"
        new_root = Path(self.temp.name) / "new-build"
        new_root.mkdir()
        physical = new_root / "XUILab.exe"
        physical.write_bytes(b"relocated-player")
        old_name = old_root / "XUILab.exe"
        hash_path = Path(self.temp.name) / "portable-build-hashes.json"
        hash_path.write_text(json.dumps({str(old_name): hashlib.sha256(physical.read_bytes()).hexdigest()}), encoding="utf-8")
        mapped = resume.verify_build_hashes(hash_path, physical, build_root=new_root, recorded_build_root=old_root)
        mapped_hash = next(value for name, value in mapped.items() if os.path.normcase(name) == os.path.normcase(str(physical.resolve())))
        self.assertEqual(mapped_hash, hashlib.sha256(physical.read_bytes()).hexdigest().upper())

    def test_relocated_completed_runs_and_new_runs_use_per_run_root_mapping(self):
        old_root = Path(self.temp.name) / "recorded-artifacts"
        old_root.mkdir()
        self.fixture.record(1, self.hash_value, output_directory=old_root)
        calls = []

        def fake_validate(root, spec, manifest, recorded_root=None):
            calls.append((spec["runId"], recorded_root))
            return {"record": {"artifactSetSha256": self.hash_value}}

        with mock.patch.object(resume.verifier, "_validate_run", side_effect=fake_validate):
            result = self.inspect(recorded_root=str(old_root))
        self.assertEqual(result["runs"][0]["status"], "completed")
        self.assertEqual(calls[0][1], str(old_root))
        self.assertTrue(result["relocation"]["mixedRoots"])
        self.assertEqual(result["relocation"]["aggregateStatus"], "not_aggregated_mixed_roots")


if __name__ == "__main__":
    unittest.main()
