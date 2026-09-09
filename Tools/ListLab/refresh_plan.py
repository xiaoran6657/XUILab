"""Frozen List refresh plans; standard-library-only.

The default selection is the original 110-run matrix.  A plan may explicitly
select a subset of backends and profiles, but the selected groups still use
the complete five-round A/B protocol and canonical run order.  Historical
plans predate the selection metadata and remain accepted through the legacy
full-matrix/pilot compatibility path.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path
from typing import Sequence


ARTIFACTS = [
    "config.json",
    "environment.json",
    "identity.json",
    "samples.csv",
    "summary.json",
    "report.md",
    "events.log",
    "refresh-metrics.json",
    "refresh-samples.csv",
    "refresh-binding.json",
]

BACKENDS = ("normal", "virtual")
PROFILES = ("idle", "sparse", "burst", "high", "batch")
DEFAULT_GROUPS = tuple(
    [(backend, profile, -1) for backend in BACKENDS for profile in PROFILES]
    + [("virtual", "high", 60)]
)
PILOT_GROUPS = (("virtual", "high", -1), ("normal", "batch", -1))
CASE = re.compile(
    r"listrefresh-(normal|virtual)-1000-(window|target)-(idle|sparse|burst|high|batch)\Z"
)
IDENTIFIER = re.compile(r"[A-Za-z0-9_-]+\Z")
SHA256 = re.compile(r"[0-9a-fA-F]{64}\Z")


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _selection_values(value, allowed: Sequence[str], label: str, *, strict=False):
    """Return a canonical ordered subset for CLI values or plan metadata."""

    if strict:
        if not isinstance(value, list):
            raise ValueError(f"Selection {label} must be a list")
        # Plan metadata is already serialized.  Every element must be one
        # canonical token; comma splitting and whitespace trimming are CLI
        # conveniences only.
        if any(not isinstance(item, str) or item not in allowed for item in value):
            raise ValueError(f"Selection {label} contains a non-canonical value")
        values = list(value)
    else:
        if value is None:
            return list(allowed)
        if isinstance(value, str):
            value = [value]
        if not isinstance(value, (list, tuple)):
            raise ValueError(f"Selection {label} must be a list")

        items = []
        for item in value:
            if isinstance(item, (list, tuple)):
                items.extend(item)
            else:
                items.append(item)
        values = []
        for item in items:
            if not isinstance(item, str):
                raise ValueError(f"Selection {label} contains a non-string")
            # Supporting comma-separated values keeps the CLI convenient
            # while repeated --backend/--profile remains equally valid.
            values.extend(part.strip() for part in item.split(",") if part.strip())
    if not values:
        raise ValueError(f"Selection {label} must not be empty")
    if len(values) != len(set(values)):
        raise ValueError(f"Selection {label} contains duplicates")
    unknown = [item for item in values if item not in allowed]
    if unknown:
        raise ValueError(f"Unknown {label}: {unknown[0]}")
    canonical = [item for item in allowed if item in values]
    if strict and values != canonical:
        raise ValueError(f"Selection {label} order is not canonical")
    return canonical


def _groups(backends=None, profiles=None, pilot=False):
    selected_backends = _selection_values(backends, BACKENDS, "backends")
    selected_profiles = _selection_values(profiles, PROFILES, "profiles")
    source = PILOT_GROUPS if pilot else DEFAULT_GROUPS
    groups = [
        group
        for group in source
        if group[0] in selected_backends and group[1] in selected_profiles
    ]
    if not groups:
        raise ValueError("Selection produces no protocol groups")
    return groups, selected_backends, selected_profiles


def planned_runs(plan_id, gate_hash, build_hash, backends=None, profiles=None, pilot=False):
    """Build the exact canonical run sequence for a selection."""

    if not isinstance(plan_id, str) or not IDENTIFIER.fullmatch(plan_id):
        raise ValueError("Plan/run identity")
    groups, _, _ = _groups(backends, profiles, pilot)
    repeats = 1 if pilot else 5
    runs = []
    for backend, profile, fps in groups:
        for repeat in range(1, repeats + 1):
            policies = ("window", "target") if repeat % 2 else ("target", "window")
            for policy in policies:
                case = f"listrefresh-{backend}-1000-{policy}-{profile}"
                runs.append(
                    dict(
                        runId=f"{plan_id}-{case}-fps{fps}-r{repeat}",
                        groupId=f"{backend}-{profile}-fps{fps}",
                        caseId=case,
                        variant=policy,
                        runIndex=repeat,
                        plannedRepeatCount=repeats,
                        warmupFrames=300,
                        measureFrames=1800,
                        sampleCapacity=1800,
                        frameBudgetMs=16.6666667,
                        timeoutSeconds=180,
                        parameters=dict(
                            targetFrameRate=fps,
                            vSyncCount=0,
                            screenWidth=960,
                            screenHeight=540,
                            graphicsApi="Direct3D11",
                            qualityLevel="High Fidelity",
                            preflightSha256=gate_hash,
                            buildManifestSha256=build_hash,
                        ),
                    )
                )
    return runs


def _plan_selection(p):
    """Read new selection metadata, or infer the retained legacy mode."""

    selection = p.get("selection")
    if selection is None:
        # The two archived plans predate selection metadata.  Keep their
        # exact identities and ordering verifiable without rewriting them.
        runs = p.get("runs")
        pilot = isinstance(runs, list) and len(runs) == 4
        return list(BACKENDS), list(PROFILES), pilot, False
    if not isinstance(selection, dict) or set(selection) != {
        "backends",
        "profiles",
        "pilot",
    }:
        raise ValueError("Selection metadata contract")
    backends = _selection_values(selection["backends"], BACKENDS, "backends", strict=True)
    profiles = _selection_values(selection["profiles"], PROFILES, "profiles", strict=True)
    if type(selection["pilot"]) is not bool:
        raise ValueError("Selection pilot must be boolean")
    return backends, profiles, selection["pilot"], True


def validate_plan(p, require_frozen=True):
    if (
        p.get("schemaVersion") != "xuilab.list-refresh.plan/v1"
        or p.get("status") != "frozen"
        or p.get("contractId") != "list-refresh/v1"
    ):
        raise ValueError("Plan schema/status/contract")
    if p.get("artifacts") != ARTIFACTS or p.get("evidenceKind") != "windows-development-player":
        raise ValueError("Artifact/tier contract")
    if p.get("protocolVersion") != "xuilab.benchmark.protocol/v1":
        raise ValueError("Protocol version")
    if type(p.get("dirty")) is not bool:
        raise ValueError("Protocol/evidence mode")
    plan_id = p.get("planId")
    if not isinstance(plan_id, str) or not IDENTIFIER.fullmatch(plan_id):
        raise ValueError("Plan/run identity")
    runs = p.get("runs")
    if not isinstance(runs, list) or not runs:
        raise ValueError("Empty plan")
    seen = set()
    for run in runs:
        if not isinstance(run, dict):
            raise ValueError("Plan/run identity")
        run_id = run.get("runId")
        case_id = run.get("caseId")
        if (
            not isinstance(run_id, str)
            or not IDENTIFIER.fullmatch(run_id)
            or run_id in seen
            or not isinstance(case_id, str)
            or CASE.fullmatch(case_id) is None
        ):
            raise ValueError("Plan/run identity")
        seen.add(run_id)

    backends, profiles, pilot, has_selection = _plan_selection(p)
    try:
        first_parameters = runs[0]["parameters"]
        gate_hash = first_parameters["preflightSha256"]
        build_hash = first_parameters["buildManifestSha256"]
    except (KeyError, IndexError, TypeError):
        raise ValueError("Missing plan control hashes") from None
    if not isinstance(gate_hash, str) or not SHA256.fullmatch(gate_hash):
        raise ValueError("Invalid preflight hash")
    if not isinstance(build_hash, str) or not SHA256.fullmatch(build_hash):
        raise ValueError("Invalid build manifest hash")

    # Constructing the full expected sequence makes omission, addition,
    # parameter edits, and reordering equally invalid.  It also keeps the
    # five-round protocol from being silently reduced when a run is too slow.
    expected = planned_runs(
        plan_id,
        gate_hash,
        build_hash,
        backends,
        profiles,
        pilot,
    )
    if runs != expected:
        raise ValueError("Incomplete/reordered protocol matrix")
    if not has_selection:
        # Legacy pilot/full plans are intentionally validated by the exact
        # inferred sequence above.  No metadata is added to historical input.
        return p
    return p


def make_plan(
    plan_id,
    candidate,
    build,
    source,
    gate,
    manifest,
    pilot=False,
    dirty=True,
    backends=None,
    profiles=None,
):
    if type(dirty) is not bool:
        raise ValueError("dirty must be boolean")
    groups, selected_backends, selected_profiles = _groups(backends, profiles, pilot)
    mh = sha(manifest)
    gh = sha(gate)
    m = json.loads(Path(manifest).read_text(encoding="utf-8"))
    expected_identity = dict(
        candidateId=candidate,
        buildId=build,
        sourceRevision=source,
        dirty=dirty,
    )
    if any(m.get(key) != value for key, value in expected_identity.items()):
        raise ValueError("Build identity")
    runs = planned_runs(
        plan_id,
        gh,
        mh,
        selected_backends,
        selected_profiles,
        pilot,
    )
    result = dict(
        schemaVersion="xuilab.list-refresh.plan/v1",
        status="frozen",
        planId=plan_id,
        contractId="list-refresh/v1",
        contractSha256=sha("Docs/Experiments/LIST_REFRESH_PROTOCOL-r1.md"),
        candidateId=candidate,
        buildId=build,
        sourceRevision=source,
        dirty=dirty,
        evidenceKind="windows-development-player",
        protocolVersion="xuilab.benchmark.protocol/v1",
        artifacts=ARTIFACTS,
        selection=dict(
            backends=selected_backends,
            profiles=selected_profiles,
            pilot=pilot,
        ),
        runs=runs,
    )
    return validate_plan(result)


def _cli_selection(values):
    # argparse uses nargs='+' and action='append' so both
    # --backend normal virtual and repeated --backend normal --backend virtual
    # are accepted; _selection_values also accepts comma-separated values.
    return values


def main():
    p = argparse.ArgumentParser(description=__doc__)
    for name in ("output", "plan-id", "candidate", "build", "source", "gate", "build-manifest"):
        p.add_argument("--" + name, required=True)
    p.add_argument("--pilot", action="store_true")
    p.add_argument("--dirty", choices=("true", "false"), default="true")
    p.add_argument("--backend", "--backends", dest="backends", action="append", nargs="+")
    p.add_argument("--profile", "--profiles", dest="profiles", action="append", nargs="+")
    a = p.parse_args()
    doc = make_plan(
        a.plan_id,
        a.candidate,
        a.build,
        a.source,
        a.gate,
        a.build_manifest,
        a.pilot,
        a.dirty == "true",
        _cli_selection(a.backends),
        _cli_selection(a.profiles),
    )
    with Path(a.output).open("x", encoding="utf-8") as f:
        json.dump(doc, f, indent=2)
        f.write("\n")
    print(json.dumps(dict(runs=len(doc["runs"]), sha256=sha(a.output))))


if __name__ == "__main__":
    main()
