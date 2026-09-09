"""Offline contract tests for List refresh selection metadata and subsets."""
from __future__ import annotations

import copy
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import refresh_plan as plan


REPO = Path(__file__).resolve().parents[2]
LEGACY_FIXTURE = Path(__file__).resolve().parent / "testdata" / "legacy_pilot_plan.json"


class RefreshPlanSubsetTests(unittest.TestCase):
    def setUp(self):
        self.old_cwd = Path.cwd()
        os.chdir(REPO)

    def tearDown(self):
        os.chdir(self.old_cwd)

    def write_inputs(self, directory: Path, dirty: bool):
        gate = directory / "gate.json"
        manifest = directory / "build.json"
        gate.write_text("{}", encoding="utf-8")
        manifest.write_text(
            json.dumps(
                {
                    "candidateId": "candidate",
                    "buildId": "build",
                    "sourceRevision": "source",
                    "dirty": dirty,
                }
            ),
            encoding="utf-8",
        )
        return gate, manifest

    def test_default_is_original_complete_matrix(self):
        with tempfile.TemporaryDirectory() as temp:
            gate, manifest = self.write_inputs(Path(temp), True)
            value = plan.make_plan("default", "candidate", "build", "source", gate, manifest)
        self.assertTrue(value["dirty"])
        self.assertEqual(
            value["selection"],
            {
                "backends": ["normal", "virtual"],
                "profiles": ["idle", "sparse", "burst", "high", "batch"],
                "pilot": False,
            },
        )
        self.assertEqual(len(value["runs"]), 110)
        self.assertEqual(value["runs"][0]["caseId"], "listrefresh-normal-1000-window-idle")
        self.assertEqual(value["runs"][-1]["caseId"], "listrefresh-virtual-1000-target-high")
        self.assertEqual({run["plannedRepeatCount"] for run in value["runs"]}, {5})
        expected_groups = [
            (f"{backend}-{profile}-fps{fps}", fps)
            for backend in ("normal", "virtual")
            for profile in ("idle", "sparse", "burst", "high", "batch")
            for fps in (-1,)
        ] + [("virtual-high-fps60", 60)]
        observed_groups = []
        for run in value["runs"]:
            group = (run["groupId"], run["parameters"]["targetFrameRate"])
            if not observed_groups or observed_groups[-1] != group:
                observed_groups.append(group)
        self.assertEqual(observed_groups, expected_groups)
        for group, fps in expected_groups:
            members = [run for run in value["runs"] if run["groupId"] == group]
            self.assertEqual(len(members), 10)
            self.assertEqual(
                [run["variant"] for run in members],
                ["window", "target", "target", "window", "window", "target", "target", "window", "window", "target"],
            )
            self.assertTrue(all(run["parameters"]["targetFrameRate"] == fps for run in members))
            self.assertTrue(all(run["warmupFrames"] == 300 for run in members))
            self.assertTrue(all(run["measureFrames"] == 1800 for run in members))
            self.assertTrue(all(run["sampleCapacity"] == 1800 for run in members))
            self.assertTrue(all(run["parameters"]["vSyncCount"] == 0 for run in members))
            self.assertTrue(all(run["parameters"]["screenWidth"] == 960 for run in members))
            self.assertTrue(all(run["parameters"]["screenHeight"] == 540 for run in members))
            self.assertTrue(all(run["parameters"]["graphicsApi"] == "Direct3D11" for run in members))
            self.assertTrue(all(run["parameters"]["qualityLevel"] == "High Fidelity" for run in members))

    def test_clean_candidate_and_explicit_subset_keep_full_group_protocol(self):
        with tempfile.TemporaryDirectory() as temp:
            gate, manifest = self.write_inputs(Path(temp), False)
            value = plan.make_plan(
                "subset",
                "candidate",
                "build",
                "source",
                gate,
                manifest,
                dirty=False,
                backends=["virtual"],
                profiles=["high"],
            )
        self.assertFalse(value["dirty"])
        self.assertEqual(
            value["selection"],
            {"backends": ["virtual"], "profiles": ["high"], "pilot": False},
        )
        self.assertEqual(len(value["runs"]), 20)
        self.assertEqual(
            {(run["groupId"], run["parameters"]["targetFrameRate"]) for run in value["runs"]},
            {("virtual-high-fps-1", -1), ("virtual-high-fps60", 60)},
        )
        for group in ("virtual-high-fps-1", "virtual-high-fps60"):
            members = [run for run in value["runs"] if run["groupId"] == group]
            self.assertEqual(len(members), 10)
            self.assertEqual([run["runIndex"] for run in members], [1, 1, 2, 2, 3, 3, 4, 4, 5, 5])
            self.assertEqual(
                [run["variant"] for run in members],
                ["window", "target", "target", "window", "window", "target", "target", "window", "window", "target"],
            )
            self.assertTrue(all(run["warmupFrames"] == 300 for run in members))
            self.assertTrue(all(run["measureFrames"] == 1800 for run in members))

    def test_validator_rejects_missing_extra_reordered_and_changed_selection(self):
        with tempfile.TemporaryDirectory() as temp:
            gate, manifest = self.write_inputs(Path(temp), False)
            value = plan.make_plan(
                "subset",
                "candidate",
                "build",
                "source",
                gate,
                manifest,
                dirty=False,
                backends=["normal"],
                profiles=["idle"],
            )

        for mutation in (
            lambda p: p["runs"].pop(),
            lambda p: p["runs"].append(copy.deepcopy(p["runs"][-1])),
            lambda p: p["runs"].__setitem__(0, p["runs"][1]),
            lambda p: p["selection"]["profiles"].__setitem__(0, "high"),
        ):
            changed = copy.deepcopy(value)
            mutation(changed)
            with self.assertRaises(ValueError):
                plan.validate_plan(changed)

    def test_legacy_plans_remain_verifiable_without_metadata(self):
        # This is a sanitized, test-only copy of the retained four-run
        # historical shape; it is not runtime evidence or a release artifact.
        value = json.loads(LEGACY_FIXTURE.read_text(encoding="utf-8"))
        self.assertNotIn("selection", value)
        self.assertEqual(len(plan.validate_plan(value)["runs"]), 4)

    def test_validator_rejects_unsafe_ids_and_noncanonical_metadata(self):
        with tempfile.TemporaryDirectory() as temp:
            gate, manifest = self.write_inputs(Path(temp), False)
            value = plan.make_plan(
                "safe",
                "candidate",
                "build",
                "source",
                gate,
                manifest,
                dirty=False,
                backends=["normal"],
                profiles=["idle"],
            )
            with self.assertRaisesRegex(ValueError, "Plan/run identity"):
                plan.make_plan(
                    "../escape",
                    "candidate",
                    "build",
                    "source",
                    gate,
                    manifest,
                    dirty=False,
                    backends=["normal"],
                    profiles=["idle"],
                )

        for bad_plan_id in ("../escape", "safe/name", ""):
            changed = copy.deepcopy(value)
            changed["planId"] = bad_plan_id
            with self.assertRaisesRegex(ValueError, "Plan/run identity"):
                plan.validate_plan(changed)

        changed = copy.deepcopy(value)
        changed["runs"][0]["runId"] = "../escape"
        with self.assertRaisesRegex(ValueError, "Plan/run identity"):
            plan.validate_plan(changed)

        for bad_backends in (["normal,virtual"], [" normal"], ["normal", "virtual "]):
            changed = copy.deepcopy(value)
            changed["selection"]["backends"] = bad_backends
            with self.assertRaises(ValueError):
                plan.validate_plan(changed)

    def test_cli_dirty_false_and_accepts_subset_flags(self):
        with tempfile.TemporaryDirectory() as temp:
            directory = Path(temp)
            gate, manifest = self.write_inputs(directory, False)
            output = directory / "plan.json"
            command = [
                sys.executable,
                "-B",
                str(REPO / "Tools/ListLab/refresh_plan.py"),
                "--output",
                str(output),
                "--plan-id",
                "cli",
                "--candidate",
                "candidate",
                "--build",
                "build",
                "--source",
                "source",
                "--gate",
                str(gate),
                "--build-manifest",
                str(manifest),
                "--dirty",
                "false",
                "--backend",
                "virtual",
                "--profile",
                "high",
            ]
            completed = subprocess.run(
                command,
                cwd=REPO,
                check=True,
                capture_output=True,
                text=True,
            )
            self.assertIn('"runs": 20', completed.stdout)
            value = json.loads(output.read_text(encoding="utf-8"))
            self.assertFalse(value["dirty"])
            self.assertEqual(value["selection"]["backends"], ["virtual"])
            self.assertEqual(value["selection"]["profiles"], ["high"])

    def test_cli_dirty_defaults_true(self):
        with tempfile.TemporaryDirectory() as temp:
            directory = Path(temp)
            gate, manifest = self.write_inputs(directory, True)
            output = directory / "plan.json"
            subprocess.run(
                [
                    sys.executable,
                    "-B",
                    str(REPO / "Tools/ListLab/refresh_plan.py"),
                    "--output",
                    str(output),
                    "--plan-id",
                    "cli-default",
                    "--candidate",
                    "candidate",
                    "--build",
                    "build",
                    "--source",
                    "source",
                    "--gate",
                    str(gate),
                    "--build-manifest",
                    str(manifest),
                ],
                cwd=REPO,
                check=True,
                capture_output=True,
                text=True,
            )
            self.assertTrue(json.loads(output.read_text(encoding="utf-8"))["dirty"])


if __name__ == "__main__":
    unittest.main()
