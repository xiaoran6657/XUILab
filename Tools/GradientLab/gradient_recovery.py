"""Read-only inspection and recovery classification for Gradient Lab plans.

The tool never starts Unity or changes a run. It classifies each planned run
as completed, failed, pending, interrupted, or invalid. A malformed remnant is
kept visible and cannot silently become a new pending run.
"""

from __future__ import annotations

import argparse
import json
import os
import pathlib
import stat
import sys
from typing import Any, Mapping, Optional

import gradient_experiment as contracts

RECOVERY_SCHEMA = "xuilab.gradient.recovery/v1"
FAILURE_SUFFIXES = ("-failure.json", "-orchestration-failure.json")
INTENT_SUFFIXES = ("-intent.json", "-resume-intent.json")


def _fail(context: str, message: str) -> None:
    raise contracts.GradientToolError(f"{context}: {message}")


def _child(root: pathlib.Path, name: str, context: str) -> pathlib.Path:
    if not isinstance(name, str) or not name or pathlib.PurePath(name).name != name:
        _fail(context, "must be a direct child name")
    path = root / name
    contracts._assert_no_reparse_components(path, context)
    return path


def _exists(path: pathlib.Path) -> bool:
    return os.path.lexists(str(path))


def _regular(path: pathlib.Path, context: str) -> None:
    contracts._assert_regular_file(path, context)


def _read(path: pathlib.Path, context: str) -> Any:
    _regular(path, context)
    try:
        return contracts.read_json(path)
    except contracts.GradientToolError:
        raise
    except (OSError, ValueError, TypeError, UnicodeError) as exc:
        _fail(context, f"cannot read JSON ({exc})")


def _artifact_set_digest(run_dir: pathlib.Path, names: list[str]) -> str:
    file_hashes = {}
    for name in sorted(name for name in names if name != "identity.json"):
        path = _child(run_dir, name, "run artifact")
        _regular(path, "run artifact")
        file_hashes[name] = contracts.sha256_file(path)
    return contracts.canonical_digest(file_hashes)


def _check_identity(identity: Any, plan: Mapping[str, Any], run: Mapping[str, Any], run_dir: pathlib.Path) -> Optional[str]:
    if not isinstance(identity, dict):
        return "identity.json is not an object"
    for field, expected in (("runId", run["runId"]), ("planId", plan["planId"]),
                            ("contractId", plan["contractId"]), ("contractSha256", plan["contractSha256"]),
                            ("evidenceKind", plan["evidenceKind"])):
        if identity.get(field) != expected:
            return f"identity.{field} does not match the frozen plan"
    for field in ("candidateId", "buildId", "sourceRevision"):
        if identity.get(field) != plan[field]:
            return f"identity.{field} does not match the frozen plan"
    digest = identity.get("artifactSetSha256")
    if digest is not None:
        if not isinstance(digest, str) or len(digest) != 64:
            return "identity.artifactSetSha256 is not SHA-256"
        try:
            actual = _artifact_set_digest(run_dir, plan["artifacts"])
        except contracts.GradientToolError as exc:
            return str(exc)
        if digest.lower() != actual.lower():
            return "identity.artifactSetSha256 does not match artifacts"
    hashes = identity.get("artifactSha256")
    if digest is None and hashes is None:
        return "identity requires artifactSetSha256 or artifactSha256"
    if hashes is not None:
        expected_names = set(plan["artifacts"]) - {"identity.json"}
        if not isinstance(hashes, dict) or set(hashes) != expected_names:
            return "identity.artifactSha256 must cover every non-identity artifact"
        for name in sorted(expected_names):
            if not isinstance(hashes[name], str) or len(hashes[name]) != 64:
                return f"identity.artifactSha256.{name} is not SHA-256"
            try:
                actual = contracts.sha256_file(_child(run_dir, name, "run artifact"))
            except contracts.GradientToolError as exc:
                return str(exc)
            if hashes[name].lower() != actual.lower():
                return f"identity.artifactSha256.{name} does not match artifact"
    return None


def _check_summary(summary: Any, plan: Mapping[str, Any], run: Mapping[str, Any]) -> tuple[str, str]:
    if not isinstance(summary, dict):
        return "invalid", "summary.json is not an object"
    for field, expected in (("runId", run["runId"]), ("planId", plan["planId"]),
                            ("contractId", plan["contractId"]), ("contractSha256", plan["contractSha256"]),
                            ("evidenceKind", plan["evidenceKind"])):
        if summary.get(field) != expected:
            return "invalid", f"summary.{field} does not match the frozen plan"
    state = summary.get("state")
    correctness = summary.get("correctness")
    validity = summary.get("measurementValidity")
    quality = summary.get("qualityStatus")
    if state == "completed" and correctness == "pass" and validity == "valid" and quality == "pass":
        return "completed", ""
    if state in ("failed", "cancelled"):
        reason = summary.get("failureReason") or summary.get("reason") or "runner reported failure"
        return "failed", str(reason)
    return "invalid", "summary gates are not a completed successful run"


def classify_run(root: pathlib.Path, plan: Mapping[str, Any], run: Mapping[str, Any]) -> dict[str, Any]:
    """Classify one run without creating or deleting anything."""
    run_id = run["runId"]
    run_dir = _child(root, run_id, f"{run_id} run directory")
    known = set()
    failure_paths = []
    intent_paths = []
    try:
        entries = list(os.scandir(str(root)))
    except OSError as exc:
        _fail("recovery root", f"cannot enumerate ({exc})")
    prefix = run_id + "-"
    for entry in entries:
        if not entry.name.startswith(prefix):
            continue
        path = _child(root, entry.name, "run sidecar")
        known_name = False
        if any(entry.name.endswith(suffix) for suffix in FAILURE_SUFFIXES):
            failure_paths.append(path)
            known_name = True
        if any(entry.name.endswith(suffix) for suffix in INTENT_SUFFIXES):
            intent_paths.append(path)
            known_name = True
        if not known_name:
            return {"runId": run_id, "groupId": run["groupId"], "runIndex": run["runIndex"],
                    "status": "invalid", "reason": f"unknown run remnant {entry.name}", "path": str(path)}
    if len(failure_paths) > 1 or len(intent_paths) > 1:
        return {"runId": run_id, "groupId": run["groupId"], "runIndex": run["runIndex"],
                "status": "invalid", "reason": "duplicate failure or intent sidecars", "path": str(root)}
    if intent_paths:
        return {"runId": run_id, "groupId": run["groupId"], "runIndex": run["runIndex"],
                "status": "interrupted", "reason": "durable intent marker requires operator review", "path": str(intent_paths[0])}
    if failure_paths:
        try:
            failure = _read(failure_paths[0], "failure sidecar")
        except contracts.GradientToolError as exc:
            return {"runId": run_id, "groupId": run["groupId"], "runIndex": run["runIndex"],
                    "status": "invalid", "reason": str(exc), "path": str(failure_paths[0])}
        if not isinstance(failure, dict) or failure.get("runId") != run_id or not isinstance(failure.get("reason"), str) or not failure["reason"].strip():
            return {"runId": run_id, "groupId": run["groupId"], "runIndex": run["runIndex"],
                    "status": "invalid", "reason": "failure sidecar contract is invalid", "path": str(failure_paths[0])}
        if _exists(run_dir):
            return {"runId": run_id, "groupId": run["groupId"], "runIndex": run["runIndex"],
                    "status": "invalid", "reason": "failure sidecar conflicts with run directory", "path": str(run_dir)}
        return {"runId": run_id, "groupId": run["groupId"], "runIndex": run["runIndex"],
                "status": "failed", "reason": failure["reason"], "path": str(failure_paths[0])}
    if not _exists(run_dir):
        return {"runId": run_id, "groupId": run["groupId"], "runIndex": run["runIndex"],
                "status": "pending", "reason": "no run artifacts exist", "path": str(run_dir)}
    contracts._assert_no_reparse_components(run_dir, "run directory")
    if not run_dir.is_dir():
        return {"runId": run_id, "groupId": run["groupId"], "runIndex": run["runIndex"],
                "status": "invalid", "reason": "run path is not a directory", "path": str(run_dir)}
    try:
        children = list(os.scandir(str(run_dir)))
    except OSError as exc:
        return {"runId": run_id, "groupId": run["groupId"], "runIndex": run["runIndex"],
                "status": "invalid", "reason": f"cannot enumerate run directory ({exc})", "path": str(run_dir)}
    expected_names = set(plan["artifacts"])
    for entry in children:
        if entry.name not in expected_names:
            return {"runId": run_id, "groupId": run["groupId"], "runIndex": run["runIndex"],
                    "status": "invalid", "reason": f"unknown run artifact {entry.name}", "path": str(run_dir)}
    missing = sorted(expected_names - {entry.name for entry in children})
    if missing:
        return {"runId": run_id, "groupId": run["groupId"], "runIndex": run["runIndex"],
                "status": "invalid", "reason": "missing artifacts: " + ", ".join(missing), "path": str(run_dir)}
    try:
        identity = _read(run_dir / "identity.json", "identity.json")
        reason = _check_identity(identity, plan, run, run_dir)
        if reason:
            status, message = "invalid", reason
        else:
            summary = _read(run_dir / "summary.json", "summary.json")
            status, message = _check_summary(summary, plan, run)
    except contracts.GradientToolError as exc:
        status, message = "invalid", str(exc)
    return {"runId": run_id, "groupId": run["groupId"], "runIndex": run["runIndex"],
            "status": status, "reason": message, "path": str(run_dir)}


def inspect_plan(root: pathlib.Path | str, plan_value: Mapping[str, Any] | pathlib.Path | str) -> dict[str, Any]:
    """Inspect a frozen plan and classify all planned runs read-only."""
    root = pathlib.Path(root)
    contracts._assert_directory(root, "recovery root")
    plan_value = contracts.read_json(plan_value) if isinstance(plan_value, (pathlib.Path, str)) else plan_value
    plan = contracts.validate_plan(plan_value, require_frozen=True)
    runs = [classify_run(root, plan, run) for run in plan["runs"]]
    counts = {status: sum(item["status"] == status for item in runs)
              for status in ("completed", "failed", "pending", "interrupted", "invalid")}
    return {"schemaVersion": RECOVERY_SCHEMA, "planId": plan["planId"], "contractId": plan["contractId"],
            "contractSha256": plan["contractSha256"], "evidenceKind": plan["evidenceKind"], "root": str(root),
            "counts": counts, "runs": runs, "readOnly": True,
            "safeToReview": counts["invalid"] == 0 and counts["interrupted"] == 0,
            "executionStatus": "blocked" if counts["invalid"] or counts["interrupted"] else ("pending" if counts["pending"] else "complete")}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=pathlib.Path, required=True)
    parser.add_argument("--plan", type=pathlib.Path, required=True)
    args = parser.parse_args(argv)
    try:
        print(json.dumps(inspect_plan(args.root, args.plan), ensure_ascii=False, indent=2, allow_nan=False))
        return 0
    except (contracts.GradientToolError, OSError, ValueError, TypeError) as exc:
        print("GRADIENT RECOVERY FAILED: " + str(exc), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
