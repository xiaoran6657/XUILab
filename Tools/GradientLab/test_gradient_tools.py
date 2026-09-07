"""Targeted offline tests for Gradient Lab contracts and recovery."""

from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

import gradient_experiment as ge
import gradient_recovery as gr

HASH = "a" * 64


def make_plan(status="frozen", evidence="fixture", dirty=False):
    runs = []
    for group, variant in (("base", "fixed"), ("adaptive", "adaptive")):
        for index in (1, 2):
            runs.append({
                "runId": f"{group}-{index}",
                "groupId": group,
                "caseId": "static",
                "variant": variant,
                "runIndex": index,
                "plannedRepeatCount": 2,
                "warmupFrames": 2,
                "measureFrames": 4,
                "sampleCapacity": 4,
                "frameBudgetMs": 16.6666667,
                "timeoutSeconds": 5,
                "parameters": {"segments": 32 if group == "base" else "auto"},
            })
    return {
        "schemaVersion": ge.PLAN_SCHEMA,
        "status": status,
        "planId": "gradient-plan",
        "experimentId": "m3-g",
        "protocolVersion": ge.PROTOCOL_VERSION,
        "contractId": "m2-01-contract" if status == "frozen" else "",
        "contractSha256": HASH if status == "frozen" else None,
        "candidateId": "candidate",
        "buildId": "build",
        "sourceRevision": "revision",
        "dirty": dirty,
        "evidenceKind": evidence,
        "budget": {"perRunWallClockSeconds": 5, "totalWallClockSeconds": 40},
        "quality": {
            "metricId": "rgba.max_abs",
            "threshold": 0.01,
            "referenceId": "reference",
            "aggregation": "sample",
        },
        "comparison": {
            "leftGroupId": "base",
            "rightGroupId": "adaptive",
            "metricId": "frameIntervalMs.p95",
            "lowerIsBetter": True,
            "rule": "disjoint_range_and_mad",
        },
        "artifacts": ["identity.json", "summary.json"],
        "runs": runs,
    }


def make_quality(plan, run_id="base-1", delta=0.001):
    return {
        "schemaVersion": ge.QUALITY_SCHEMA,
        "runId": run_id,
        "contractId": plan["contractId"],
        "contractSha256": plan["contractSha256"],
        "evidenceKind": plan["evidenceKind"],
        "referenceId": "reference",
        "metricId": "rgba.max_abs",
        "threshold": 0.01,
        "aggregation": "sample",
        "colorSpace": "linear",
        "alphaMode": "straight",
        "samples": [
            {"t": 0.0, "expectedRgba": [0, 0, 0, 1], "actualRgba": [delta, 0, 0, 1]},
            {"t": 0.5, "expectedRgba": [0.5, 0.5, 0.5, 1], "actualRgba": [0.5, 0.5, 0.5, 1]},
            {"t": 1.0, "expectedRgba": [1, 1, 1, 1], "actualRgba": [1, 1, 1, 1]},
        ],
    }


def make_results(plan, state="completed", quality="pass", left=(10, 11, 12, 13), right=(5, 6, 7, 8)):
    rows = []
    for run in plan["runs"]:
        values = left if run["groupId"] == "base" else right
        rows.append({
            "runId": run["runId"],
            "groupId": run["groupId"],
            "caseId": run["caseId"],
            "variant": run["variant"],
            "runIndex": run["runIndex"],
            "plannedRepeatCount": run["plannedRepeatCount"],
            "state": state,
            "correctness": "pass" if state == "completed" else "not_run",
            "measurementValidity": "valid" if state == "completed" else "not_assessed",
            "qualityStatus": quality,
            "failureCode": "" if state == "completed" else "runner_failure",
            "failureReason": "" if state == "completed" else "fixture failure",
            "metrics": {"frameIntervalMs": list(values), "costMetrics": {"meshRebuild": [1, 2]}},
        })
    return {
        "schemaVersion": ge.RESULTS_SCHEMA,
        "planId": plan["planId"],
        "contractId": plan["contractId"],
        "contractSha256": plan["contractSha256"],
        "evidenceKind": plan["evidenceKind"],
        "runs": rows,
    }


class GradientContractTests(unittest.TestCase):
    def test_draft_is_structural_but_frozen_is_required_for_evidence(self):
        draft = make_plan("draft")
        self.assertEqual(ge.validate_plan(draft)["status"], "draft")
        with self.assertRaisesRegex(ge.GradientToolError, "not ready"):
            ge.validate_plan(draft, require_frozen=True)
        self.assertEqual(ge.validate_plan(make_plan())["contractSha256"], HASH)

    def test_plan_rejects_missing_group_index_and_timeout_budget(self):
        plan = make_plan()
        plan["runs"] = plan["runs"][:-1]
        with self.assertRaisesRegex(ge.GradientToolError, "exactly 1"):
            ge.validate_plan(plan)
        plan = make_plan()
        plan["budget"]["totalWallClockSeconds"] = 1
        with self.assertRaisesRegex(ge.GradientToolError, "cover all run timeouts"):
            ge.validate_plan(plan)

    def test_strict_json_rejects_duplicates_and_nonfinite(self):
        with tempfile.TemporaryDirectory() as temp:
            duplicate = Path(temp) / "duplicate.json"
            duplicate.write_text('{"x": 1, "x": 2}', encoding="utf-8")
            with self.assertRaises(ge.GradientToolError):
                ge.read_json(duplicate)
            nonfinite = Path(temp) / "nonfinite.json"
            nonfinite.write_text('{"x": NaN}', encoding="utf-8")
            with self.assertRaises(ge.GradientToolError):
                ge.read_json(nonfinite)

    def test_quality_reports_rgba_metrics_and_quality_limit(self):
        plan = make_plan()
        self.assertEqual(ge.quality_metrics(make_quality(plan, delta=0.001), plan)["status"], "pass")
        limited = ge.quality_metrics(make_quality(plan, delta=0.1), plan)
        self.assertEqual(limited["status"], "quality_limited")
        self.assertAlmostEqual(limited["maxAbsError"], 0.1)

    def test_quality_does_not_pass_a_draft(self):
        plan = make_plan("draft")
        self.assertEqual(ge.quality_metrics(make_quality(plan), plan)["status"], "not_ready")

    def test_results_analysis_requires_all_gates_and_repeats(self):
        plan = make_plan()
        analysis = ge.analyze_results(plan, make_results(plan))
        self.assertEqual(analysis["status"], "pass")
        self.assertEqual(analysis["executionEvidence"], "not_assessed")
        self.assertEqual(analysis["comparisons"][0]["status"], "improved")
        blocked = ge.analyze_results(plan, make_results(plan, quality="quality_limited"))
        self.assertEqual(blocked["status"], "invalid")
        self.assertFalse(blocked["comparisons"])


    def test_missing_optional_cost_metrics_are_unavailable(self):
        plan = make_plan()
        results = make_results(plan)
        for item in results["runs"]:
            del item["metrics"]["costMetrics"]
        analysis = ge.analyze_results(plan, results)
        self.assertEqual(analysis["status"], "pass")
        for group in analysis["groups"]:
            self.assertEqual(group["metrics"]["availability"]["costMetrics"], "unavailable")
            self.assertIn("no optional cost metric supplied", group["metrics"]["availability"]["costMetricsReason"])

    def test_recovery_is_read_only_and_classifies_states(self):
        plan = make_plan()
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            plan_path = root / "plan.json"
            plan_path.write_text(json.dumps(plan), encoding="utf-8")
            # One complete run.
            run = plan["runs"][0]
            run_dir = root / run["runId"]
            run_dir.mkdir()
            summary = {"runId": run["runId"], "planId": plan["planId"],
                       "contractId": plan["contractId"], "contractSha256": plan["contractSha256"],
                       "evidenceKind": plan["evidenceKind"], "state": "completed",
                       "correctness": "pass", "measurementValidity": "valid",
                       "qualityStatus": "pass"}
            (run_dir / "summary.json").write_text(json.dumps(summary), encoding="utf-8")
            artifact_hash = ge.canonical_digest({"summary.json": ge.sha256_file(run_dir / "summary.json")})
            identity = {"runId": run["runId"], "planId": plan["planId"],
                        "contractId": plan["contractId"], "contractSha256": plan["contractSha256"],
                        "evidenceKind": plan["evidenceKind"], "candidateId": plan["candidateId"],
                        "buildId": plan["buildId"], "sourceRevision": plan["sourceRevision"],
                        "artifactSetSha256": artifact_hash}
            (run_dir / "identity.json").write_text(json.dumps(identity), encoding="utf-8")
            # One durable failure, one interrupted intent, one malformed remnant.
            failed = plan["runs"][1]["runId"]
            (root / (failed + "-failure.json")).write_text(
                json.dumps({"runId": failed, "reason": "child failed"}), encoding="utf-8")
            interrupted = plan["runs"][2]["runId"]
            (root / (interrupted + "-intent.json")).write_text("{}", encoding="utf-8")
            invalid = plan["runs"][3]["runId"]
            (root / invalid).mkdir()
            (root / invalid / "partial.txt").write_text("partial", encoding="utf-8")
            result = gr.inspect_plan(root, plan_path)
            self.assertEqual(result["counts"], {"completed": 1, "failed": 1, "pending": 0, "interrupted": 1, "invalid": 1})
            self.assertTrue(result["readOnly"])
            self.assertEqual(result["executionStatus"], "blocked")
            self.assertTrue((root / (interrupted + "-intent.json")).exists())
            self.assertFalse((root / "plan.json").read_bytes() == b"")

    def test_recovery_requires_complete_identity_hash(self):
        plan = make_plan()
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            run = plan["runs"][0]
            run_dir = root / run["runId"]
            run_dir.mkdir()
            identity = {"runId": run["runId"], "planId": plan["planId"],
                        "contractId": plan["contractId"], "contractSha256": plan["contractSha256"],
                        "evidenceKind": plan["evidenceKind"], "candidateId": plan["candidateId"],
                        "buildId": plan["buildId"], "sourceRevision": plan["sourceRevision"]}
            summary = dict(identity, state="completed", correctness="pass",
                           measurementValidity="valid", qualityStatus="pass")
            (run_dir / "identity.json").write_text(json.dumps(identity), encoding="utf-8")
            (run_dir / "summary.json").write_text(json.dumps(summary), encoding="utf-8")
            self.assertEqual(gr.inspect_plan(root, plan)["runs"][0]["status"], "invalid")

    def test_recovery_rejects_draft_and_unknown_remnant(self):
        plan = make_plan("draft")
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            with self.assertRaisesRegex(ge.GradientToolError, "draft"):
                gr.inspect_plan(root, plan)
            plan = make_plan()
            (root / "base-1-unknown.txt").write_text("keep", encoding="utf-8")
            result = gr.inspect_plan(root, plan)
            self.assertEqual(result["runs"][0]["status"], "invalid")
            self.assertEqual((root / "base-1-unknown.txt").read_text(encoding="utf-8"), "keep")

    def test_analysis_keeps_fixture_nonpublishable(self):
        plan = make_plan(evidence="fixture")
        analysis = ge.analyze_results(plan, make_results(plan))
        self.assertEqual(analysis["status"], "pass")
        self.assertEqual(analysis["executionEvidence"], "not_assessed")


if __name__ == "__main__":
    unittest.main()
