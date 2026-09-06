#!/usr/bin/env python3
"""Regression tests for the strict List Lab evidence verifier."""

from __future__ import annotations

import csv
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest import mock


MODULE_PATH = Path(__file__).with_name("verify_list_runs.py")
SPEC = importlib.util.spec_from_file_location("verify_list_runs", MODULE_PATH)
if SPEC is None or SPEC.loader is None:
    raise RuntimeError("cannot load verifier module")
verifier = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(verifier)


class ListVerifierFixture:
    def __init__(self, root: Path, measure_frames: int = 4, repeats: int = 5) -> None:
        self.root = root
        self.measure_frames = measure_frames
        self.repeats = repeats
        self.case_id = "list-virtual-100-scroll"
        self.manifest = {
            "candidateId": "candidate-test",
            "buildId": "build-test",
            "sourceRevision": "source-test",
            "runs": [],
        }
        for run_index in range(1, repeats + 1):
            run_id = "{}-r{}".format(self.case_id, run_index)
            spec = {
                "runId": run_id,
                "caseId": self.case_id,
                "targetFrameRate": -1,
                "runIndex": run_index,
                "plannedRepeatCount": repeats,
                "warmupFrames": 2,
                "measureFrames": measure_frames,
            }
            self.manifest["runs"].append(spec)
            self._write_run(spec)

    def _write_run(self, spec: dict) -> None:
        run_dir = self.root / spec["runId"]
        run_dir.mkdir()
        config = {
            "schemaVersion": "xuilab.benchmark.config/v1",
            "protocolVersion": "xuilab.benchmark.protocol/v1",
            "runId": spec["runId"],
            "seriesId": "list-test",
            "runIndex": spec["runIndex"],
            "plannedRepeatCount": spec["plannedRepeatCount"],
            "tier": "windows-development-player",
            "caseId": spec["caseId"],
            "caseVersion": "1",
            "seed": 1337,
            "warmupFrames": spec["warmupFrames"],
            "measureFrames": spec["measureFrames"],
            "sampleCapacity": spec["measureFrames"],
            "readyTimeoutFrames": 300,
            "frameBudgetMs": 16.6666667,
            "targetFrameRate": -1,
            "vSyncCount": 0,
            "enableProfilerRecorders": True,
            "requiredMetrics": ["Frame Interval"],
            "optionalMetrics": ["Main Thread", "GC Allocated In Frame", "System Used Memory"],
            "cpuIterationsPerFrame": 0,
            "allocationBytesPerFrame": 0,
            "outputDirectory": str(self.root),
            "candidateId": "candidate-test",
            "buildId": "build-test",
            "sourceRevision": "source-test",
            "dirty": True,
            "quitWhenDone": True,
            "faultPlan": {"mode": "none", "triggerMeasureFrame": 0, "shortageSampleCount": 1},
        }
        # JsonUtility writes a UTF-8 pretty artifact; the verifier only cares
        # about exact bytes for the identity hash, so this fixture uses a
        # deterministic equivalent.
        config_bytes = (json.dumps(config, indent=2, ensure_ascii=False) + "\n").encode("utf-8")
        (run_dir / "config.json").write_bytes(config_bytes)
        identity = {
            "schemaVersion": "xuilab.benchmark.identity/v1",
            "runId": spec["runId"],
            "candidateId": "candidate-test",
            "buildId": "build-test",
            "sourceRevision": "source-test",
            "dirty": True,
            "runnerVersion": "1",
            "configSha256": hashlib.sha256(config_bytes).hexdigest().upper(),
            "createdUtc": "2026-09-06T00:00:00.000000Z",
        }
        environment = {
            "schemaVersion": "xuilab.benchmark.environment/v1",
            "tier": "windows-development-player",
            "unityVersion": "2022.3.45f1c1",
            "operatingSystem": "Windows 11 64bit",
            "processorType": "fixture CPU",
            "processorCount": 8,
            "graphicsDeviceName": "fixture GPU",
            "graphicsDeviceType": "Direct3D11",
            "graphicsDeviceVersion": "fixture driver",
            "screenWidth": 960,
            "screenHeight": 540,
            "qualityLevel": "High Fidelity",
            "vSyncCount": 0,
            "targetFrameRate": -1,
            "scriptingBackend": "mono",
            "buildType": "development",
            "metricCapabilities": [
                {"name": "Frame Interval", "category": "BuiltIn", "unit": "Milliseconds", "required": True, "status": "available", "reason": ""},
                {"name": "Main Thread", "category": "Internal", "unit": "unknown", "required": False, "status": "unavailable", "reason": "fixture unavailable"},
                {"name": "GC Allocated In Frame", "category": "Memory", "unit": "unknown", "required": False, "status": "unavailable", "reason": "fixture unavailable"},
                {"name": "System Used Memory", "category": "Memory", "unit": "unknown", "required": False, "status": "unavailable", "reason": "fixture unavailable"},
            ],
        }
        intervals = [1.0, 2.0, 3.0, 4.0][: self.measure_frames]
        if self.measure_frames > len(intervals):
            intervals.extend([4.0] * (self.measure_frames - len(intervals)))
        elapsed = 0.0
        base_rows = []
        list_rows = []
        item_count = 100
        virtualized = True
        action_profile = "scroll"
        max_offset = max(0.0, item_count * verifier.ROW_HEIGHT - verifier.VIEWPORT_HEIGHT)
        measure_start_unique = 13
        initial_leased = verifier._expected_leased_count(
            item_count, verifier._expected_action_offset(action_profile, 0, max_offset), virtualized, True
        )
        measure_start_unbind = measure_start_unique - initial_leased
        for index, interval in enumerate(intervals):
            elapsed += interval
            base_rows.append([index, 101 + index, elapsed, interval, "", "", ""])
            offset = verifier._expected_action_offset(action_profile, index, max_offset)
            live = verifier._expected_live_state(action_profile, index)
            leased = verifier._expected_leased_count(item_count, offset, virtualized, live)
            visible = verifier._expected_visible_count(item_count, offset, live)
            cached = measure_start_unique - leased
            unbind_count = measure_start_unbind
            bind_count = unbind_count + leased
            list_rows.append([
                index, 100 + index, offset, visible, leased, leased, cached,
                measure_start_unique, 0, bind_count, unbind_count,
            ])
        final_leased = verifier._expected_leased_count(
            item_count, verifier._expected_action_offset(action_profile, self.measure_frames - 1, max_offset),
            virtualized, True,
        )
        p50 = verifier._percentile(intervals, 0.5)
        p95 = verifier._percentile(intervals, 0.95)
        p99 = verifier._percentile(intervals, 0.99)
        summary = {
            "schemaVersion": "xuilab.benchmark.summary/v1",
            "runId": spec["runId"],
            "state": "completed",
            "failureCode": "none",
            "failureReason": "",
            "correctness": "pass",
            "measurementValidity": "valid",
            "performanceComparison": "not_assessed",
            "processSuccess": True,
            "exitCode": 0,
            "enteredMeasure": True,
            "exportSucceeded": True,
            "cleanupSucceeded": True,
            "sampleCount": self.measure_frames,
            "p50FrameIntervalMs": p50,
            "p95FrameIntervalMs": p95,
            "p99FrameIntervalMs": p99,
            "maxFrameIntervalMs": max(intervals),
            "overBudgetRatio": 0.0,
            "meanMainThreadNanoseconds": None,
            "totalGcAllocatedBytes": None,
            "lastSystemUsedMemoryBytes": None,
        }
        metrics = {
            "schemaVersion": "xuilab.list.metrics/v1",
            "runId": spec["runId"],
            "caseId": self.case_id,
            "actionProfile": action_profile,
            "itemCount": item_count,
            "virtualized": virtualized,
            "coldBuildMs": 1.5,
            "firstInteractiveMs": 2.5,
            "correctness": "pass",
            "reason": "",
            "maxPositionErrorPixels": 0.0,
            "createdAtMeasureStart": measure_start_unique,
            "destroyedAtMeasureStart": 0,
            "finalCreated": measure_start_unique,
            "finalDestroyed": 0,
            "finalLeased": final_leased,
            "finalCached": measure_start_unique - final_leased,
            "finalUniqueTotal": measure_start_unique,
            "cleanupUniqueTotal": 0,
            "rejectedReturns": 0,
            "sampleCount": self.measure_frames,
            "uiRebuildMetric": "unavailable",
            "uiRebuildReason": "fixture unavailable",
        }
        self._write_json(run_dir / "environment.json", environment)
        self._write_json(run_dir / "identity.json", identity)
        self._write_json(run_dir / "summary.json", summary)
        self._write_json(run_dir / "list-metrics.json", metrics)
        with (run_dir / "samples.csv").open("w", encoding="utf-8", newline="") as handle:
            writer = csv.writer(handle, lineterminator="\n")
            writer.writerow(verifier.BASE_SAMPLE_HEADER)
            writer.writerows(base_rows)
        with (run_dir / "list-samples.csv").open("w", encoding="utf-8", newline="") as handle:
            writer = csv.writer(handle, lineterminator="\n")
            writer.writerow(verifier.LIST_SAMPLE_HEADER)
            writer.writerows(list_rows)
        (run_dir / "report.md").write_text("fixture report\n", encoding="utf-8")
        (run_dir / "events.log").write_text("fixture events\n", encoding="utf-8")

    @staticmethod
    def _write_json(path: Path, value: dict) -> None:
        path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


class VerifyListRunsTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = Path(tempfile.mkdtemp(prefix="xuilab-list-verifier-"))
        self.root = self.temp / "Artifacts"
        self.root.mkdir()
        self.fixture = ListVerifierFixture(self.root)

    def tearDown(self) -> None:
        shutil.rmtree(self.temp, ignore_errors=True)

    def assert_valid(self) -> dict:
        return verifier.verify(self.root, self.fixture.manifest, plan=verifier.FIXTURE_PLAN)

    def assert_invalid(self, mutate) -> None:
        mutate()
        with self.assertRaises(verifier.VerificationError):
            verifier.verify(self.root, self.fixture.manifest, plan=verifier.FIXTURE_PLAN)

    def test_fixture_is_rejected_by_production_matrix_plan(self) -> None:
        with self.assertRaises(verifier.VerificationError):
            verifier.verify(self.root, self.fixture.manifest, plan="matrix")

    def test_fixture_requires_explicit_programmatic_mode(self) -> None:
        with self.assertRaises(verifier.VerificationError):
            verifier.verify(self.root, self.fixture.manifest)

    def test_valid_five_run_aggregate(self) -> None:
        report = self.assert_valid()
        self.assertEqual(report["runCount"], 5)
        self.assertEqual(len(report["aggregates"]), 1)
        self.assertEqual(report["aggregates"][0]["repeatCount"], 5)
        self.assertEqual(report["aggregates"][0]["runIndexes"], [1, 2, 3, 4, 5])

    def test_rejects_json_type_and_enum_case(self) -> None:
        path = self.root / self.fixture.manifest["runs"][0]["runId"] / "list-metrics.json"
        data = json.loads(path.read_text(encoding="utf-8"))
        data["virtualized"] = "true"
        path.write_text(json.dumps(data), encoding="utf-8")
        with self.assertRaises(verifier.VerificationError):
            verifier.verify(self.root, self.fixture.manifest, plan=verifier.FIXTURE_PLAN)

        # Restore and mutate an exact case-sensitive enum.
        self.tearDown()
        self.setUp()
        path = self.root / self.fixture.manifest["runs"][0]["runId"] / "summary.json"
        data = json.loads(path.read_text(encoding="utf-8"))
        data["state"] = "COMPLETED"
        path.write_text(json.dumps(data), encoding="utf-8")
        with self.assertRaises(verifier.VerificationError):
            verifier.verify(self.root, self.fixture.manifest, plan=verifier.FIXTURE_PLAN)

    def test_rejects_extra_hidden_artifact(self) -> None:
        path = self.root / self.fixture.manifest["runs"][0]["runId"] / ".hidden"
        path.write_text("tamper", encoding="utf-8")
        with self.assertRaises(verifier.VerificationError):
            verifier.verify(self.root, self.fixture.manifest, plan=verifier.FIXTURE_PLAN)

    def test_rejects_config_hash_tamper(self) -> None:
        path = self.root / self.fixture.manifest["runs"][0]["runId"] / "identity.json"
        data = json.loads(path.read_text(encoding="utf-8"))
        data["configSha256"] = "0" * 64
        path.write_text(json.dumps(data), encoding="utf-8")
        with self.assertRaises(verifier.VerificationError):
            verifier.verify(self.root, self.fixture.manifest, plan=verifier.FIXTURE_PLAN)

    def test_rejects_case_identity_tamper(self) -> None:
        path = self.root / self.fixture.manifest["runs"][0]["runId"] / "list-metrics.json"
        data = json.loads(path.read_text(encoding="utf-8"))
        data["caseId"] = "list-virtual-100-lifecycle"
        path.write_text(json.dumps(data), encoding="utf-8")
        with self.assertRaises(verifier.VerificationError):
            verifier.verify(self.root, self.fixture.manifest, plan=verifier.FIXTURE_PLAN)

    def test_rejects_non_windows_or_non_64bit_environment(self) -> None:
        path = self.root / self.fixture.manifest["runs"][0]["runId"] / "environment.json"
        for value in ("Linux 64bit", "Windows 11 32bit", "Windows 11"):
            with self.subTest(operating_system=value):
                data = json.loads(path.read_text(encoding="utf-8"))
                data["operatingSystem"] = value
                path.write_text(json.dumps(data), encoding="utf-8")
                with self.assertRaises(verifier.VerificationError):
                    verifier.verify(self.root, self.fixture.manifest, plan=verifier.FIXTURE_PLAN)

    def test_rejects_list_ownership_tamper(self) -> None:
        path = self.root / self.fixture.manifest["runs"][0]["runId"] / "list-samples.csv"
        with path.open("r", encoding="utf-8", newline="") as handle:
            rows = list(csv.reader(handle))
        rows[1][5] = "12"  # leased no longer equals the frozen prefetch window.
        with path.open("w", encoding="utf-8", newline="") as handle:
            csv.writer(handle, lineterminator="\n").writerows(rows)
        with self.assertRaises(verifier.VerificationError):
            verifier.verify(self.root, self.fixture.manifest, plan=verifier.FIXTURE_PLAN)

    def test_rejects_scroll_action_trace_tamper(self) -> None:
        path = self.root / self.fixture.manifest["runs"][0]["runId"] / "list-samples.csv"
        with path.open("r", encoding="utf-8", newline="") as handle:
            rows = list(csv.reader(handle))
        rows[2][2] = "0"  # The second action must advance along the 600-frame triangle.
        with path.open("w", encoding="utf-8", newline="") as handle:
            csv.writer(handle, lineterminator="\n").writerows(rows)
        with self.assertRaises(verifier.VerificationError):
            verifier.verify(self.root, self.fixture.manifest, plan=verifier.FIXTURE_PLAN)

    def test_rejects_active_counter_tamper(self) -> None:
        path = self.root / self.fixture.manifest["runs"][0]["runId"] / "list-samples.csv"
        with path.open("r", encoding="utf-8", newline="") as handle:
            rows = list(csv.reader(handle))
        rows[1][4] = "0"  # active must equal the leased prefetch window.
        with path.open("w", encoding="utf-8", newline="") as handle:
            csv.writer(handle, lineterminator="\n").writerows(rows)
        with self.assertRaises(verifier.VerificationError):
            verifier.verify(self.root, self.fixture.manifest, plan=verifier.FIXTURE_PLAN)

    def test_rejects_visible_counter_tamper(self) -> None:
        path = self.root / self.fixture.manifest["runs"][0]["runId"] / "list-samples.csv"
        with path.open("r", encoding="utf-8", newline="") as handle:
            rows = list(csv.reader(handle))
        rows[2][3] = "8"  # The second action intersects nine rows at this offset.
        with path.open("w", encoding="utf-8", newline="") as handle:
            csv.writer(handle, lineterminator="\n").writerows(rows)
        with self.assertRaises(verifier.VerificationError):
            verifier.verify(self.root, self.fixture.manifest, plan=verifier.FIXTURE_PLAN)

    def test_rejects_lifecycle_middle_action_tamper(self) -> None:
        max_offset = 100 * verifier.ROW_HEIGHT - verifier.VIEWPORT_HEIGHT
        rows = []
        for index in range(1800):
            offset = verifier._expected_action_offset("lifecycle", index, max_offset)
            live = verifier._expected_live_state("lifecycle", index)
            leased = verifier._expected_leased_count(100, offset, True, live)
            rows.append({
                "offset": offset,
                "visible": verifier._expected_visible_count(100, offset, live),
                "active": leased,
                "leased": leased,
            })
        rows[700]["offset"] = 0.0  # A single changed action must invalidate the lifecycle trace.
        with self.assertRaises(verifier.VerificationError):
            verifier._validate_lifecycle_timeline(rows, 100, max_offset, True, "synthetic lifecycle")

    def test_rejects_sample_frame_alignment_tamper(self) -> None:
        path = self.root / self.fixture.manifest["runs"][0]["runId"] / "list-samples.csv"
        with path.open("r", encoding="utf-8", newline="") as handle:
            rows = list(csv.reader(handle))
        rows[2][1] = "999"
        with path.open("w", encoding="utf-8", newline="") as handle:
            csv.writer(handle, lineterminator="\n").writerows(rows)
        with self.assertRaises(verifier.VerificationError):
            verifier.verify(self.root, self.fixture.manifest, plan=verifier.FIXTURE_PLAN)

    def test_rejects_summary_stat_tamper(self) -> None:
        path = self.root / self.fixture.manifest["runs"][0]["runId"] / "summary.json"
        data = json.loads(path.read_text(encoding="utf-8"))
        data["p95FrameIntervalMs"] += 1.0
        path.write_text(json.dumps(data), encoding="utf-8")
        with self.assertRaises(verifier.VerificationError):
            verifier.verify(self.root, self.fixture.manifest, plan=verifier.FIXTURE_PLAN)

    def test_cli_writes_report_only_after_success(self) -> None:
        manifest_path = self.temp / "manifest.json"
        manifest_path.write_text(json.dumps(self.fixture.manifest), encoding="utf-8")
        report_path = self.temp / "report.json"
        command = [
            sys.executable, str(MODULE_PATH), "--root", str(self.root),
            "--manifest", str(manifest_path), "--out", str(report_path),
        ]
        completed = subprocess.run(command, capture_output=True, text=True, check=False)
        self.assertNotEqual(completed.returncode, 0)
        self.assertFalse(report_path.exists())

        fixture_report = verifier.verify(self.root, self.fixture.manifest, plan=verifier.FIXTURE_PLAN)
        report_path.write_text(json.dumps(fixture_report), encoding="utf-8")
        self.assertEqual(json.loads(report_path.read_text(encoding="utf-8"))["runCount"], 5)

        bad_path = self.root / self.fixture.manifest["runs"][0]["runId"] / ".hidden"
        bad_path.write_text("tamper", encoding="utf-8")
        previous = report_path.read_bytes()
        failed = subprocess.run(command, capture_output=True, text=True, check=False)
        self.assertNotEqual(failed.returncode, 0)
        self.assertEqual(report_path.read_bytes(), previous)

    def test_rejects_symlinked_root(self) -> None:
        link = self.temp / "Artifacts-link"
        try:
            os.symlink(str(self.root), str(link), target_is_directory=True)
        except (OSError, NotImplementedError) as exc:
            self.skipTest("directory symlink unavailable: {}".format(exc))
        with self.assertRaises(verifier.VerificationError):
            verifier.verify(link, self.fixture.manifest, plan=verifier.FIXTURE_PLAN)

    def test_rejects_symlinked_run_directory(self) -> None:
        run_id = self.fixture.manifest["runs"][0]["runId"]
        original = self.root / run_id
        outside = self.temp / "outside-run"
        shutil.copytree(original, outside)
        shutil.rmtree(original)
        try:
            os.symlink(str(outside), str(original), target_is_directory=True)
        except (OSError, NotImplementedError) as exc:
            self.skipTest("directory symlink unavailable: {}".format(exc))
        with self.assertRaises(verifier.VerificationError):
            verifier.verify(self.root, self.fixture.manifest, plan=verifier.FIXTURE_PLAN)

    def test_rejects_reparse_point_attribute(self) -> None:
        fake_stat = SimpleNamespace(st_mode=0, st_file_attributes=verifier.REPARSE_POINT_ATTRIBUTE)
        with mock.patch.object(verifier.os, "lstat", return_value=fake_stat):
            with self.assertRaises(verifier.VerificationError):
                verifier._assert_no_reparse_components(Path("synthetic-root"), "root")


if __name__ == "__main__":
    unittest.main()
