#!/usr/bin/env python3
"""Strict offline verifier for List Lab benchmark evidence.

The Unity runner owns the action timeline and the two CSV streams.  This
module deliberately treats the files as untrusted evidence: JSON types and
property names are checked before values are used, CSV statistics are
recomputed, and the List Lab counters are checked row by row.

The command line interface is intentionally small::

    python Tools/ListLab/verify_list_runs.py \
        --root Artifacts --manifest list-manifest.json --out list-report.json

The verifier only writes the requested report after every listed run has
passed.  A failed verification exits non-zero and leaves the output path
untouched.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import os
import stat
from pathlib import Path
import re
import sys
from datetime import datetime
from typing import Any, Dict, Iterable, List, Mapping, MutableMapping, Optional, Sequence, Tuple


PROTOCOL_VERSION = "xuilab.benchmark.protocol/v1"
CONFIG_SCHEMA = "xuilab.benchmark.config/v1"
ENVIRONMENT_SCHEMA = "xuilab.benchmark.environment/v1"
IDENTITY_SCHEMA = "xuilab.benchmark.identity/v1"
SUMMARY_SCHEMA = "xuilab.benchmark.summary/v1"
LIST_METRICS_SCHEMA = "xuilab.list.metrics/v1"

CONFIG_FIELDS = (
    "schemaVersion", "protocolVersion", "runId", "seriesId", "runIndex",
    "plannedRepeatCount", "tier", "caseId", "caseVersion", "seed",
    "warmupFrames", "measureFrames", "sampleCapacity", "readyTimeoutFrames",
    "frameBudgetMs", "targetFrameRate", "vSyncCount", "enableProfilerRecorders",
    "requiredMetrics", "optionalMetrics", "cpuIterationsPerFrame",
    "allocationBytesPerFrame", "outputDirectory", "candidateId", "buildId",
    "sourceRevision", "dirty", "quitWhenDone", "faultPlan",
)
FAULT_FIELDS = ("mode", "triggerMeasureFrame", "shortageSampleCount")
ENVIRONMENT_FIELDS = (
    "schemaVersion", "tier", "unityVersion", "operatingSystem", "processorType",
    "processorCount", "graphicsDeviceName", "graphicsDeviceType",
    "graphicsDeviceVersion", "screenWidth", "screenHeight", "qualityLevel",
    "vSyncCount", "targetFrameRate", "scriptingBackend", "buildType",
    "metricCapabilities",
)
CAPABILITY_FIELDS = ("name", "category", "unit", "required", "status", "reason")
IDENTITY_FIELDS = (
    "schemaVersion", "runId", "candidateId", "buildId", "sourceRevision",
    "dirty", "runnerVersion", "configSha256", "createdUtc",
)
SUMMARY_FIELDS = (
    "schemaVersion", "runId", "state", "failureCode", "failureReason",
    "correctness", "measurementValidity", "performanceComparison", "processSuccess",
    "exitCode", "enteredMeasure", "exportSucceeded", "cleanupSucceeded",
    "sampleCount", "p50FrameIntervalMs", "p95FrameIntervalMs", "p99FrameIntervalMs",
    "maxFrameIntervalMs", "overBudgetRatio", "meanMainThreadNanoseconds",
    "totalGcAllocatedBytes", "lastSystemUsedMemoryBytes",
)
LIST_METRICS_FIELDS = (
    "schemaVersion", "runId", "caseId", "actionProfile", "itemCount", "virtualized",
    "coldBuildMs", "firstInteractiveMs", "correctness", "reason",
    "maxPositionErrorPixels", "createdAtMeasureStart", "destroyedAtMeasureStart",
    "finalCreated", "finalDestroyed", "finalLeased", "finalCached", "finalUniqueTotal",
    "cleanupUniqueTotal", "rejectedReturns", "sampleCount", "uiRebuildMetric",
    "uiRebuildReason",
)

BASE_ARTIFACTS = (
    "config.json", "environment.json", "events.log", "identity.json", "report.md",
    "samples.csv", "summary.json",
)
LIST_ARTIFACTS = BASE_ARTIFACTS + ("list-metrics.json", "list-samples.csv")
BASE_SAMPLE_HEADER = (
    "sample_index", "unity_frame", "elapsed_ms", "frame_interval_ms",
    "main_thread_ns", "gc_allocated_bytes", "system_used_memory_bytes",
)
LIST_SAMPLE_HEADER = (
    "sample_index", "unity_frame", "offset", "visible", "active", "leased",
    "cached", "created", "destroyed", "bind_count", "unbind_count",
)

ROW_HEIGHT = 48.0
VIEWPORT_HEIGHT = 384.0
PREFETCH_ROWS = 2
POSITION_TOLERANCE = 0.05

CASE_RE = re.compile(r"^list-(normal|virtual)-(100|300|1000|10000)-(scroll|lifecycle)$")
SAFE_RUN_ID_RE = re.compile(r"^[^<>:\"/\\|?*\x00-\x1f]+$")
INTEGER_TEXT_RE = re.compile(r"^[0-9]+$")
HASH_RE = re.compile(r"^[0-9A-F]{64}$")
FLOAT_TEXT_RE = re.compile(
    r"^[+-]?(?:[0-9]+(?:\.[0-9]*)?|\.[0-9]+)(?:[eE][+-]?[0-9]+)?$"
)
WINDOWS_64BIT_RE = re.compile(r"^Windows\b.*\b64[- ]?bit\b", re.IGNORECASE)

PLAN_NAMES = ("matrix", "pilot", "stress")
FIXTURE_PLAN = "fixture"
REPARSE_POINT_ATTRIBUTE = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x0400)


def _plan_groups(plan: str) -> Tuple[Sequence[Tuple[int, str, int]], Sequence[str], int]:
    if plan == "matrix":
        return (
            (
                (100, "scroll", -1),
                (100, "lifecycle", -1),
                (1000, "scroll", -1),
                (1000, "lifecycle", -1),
                (1000, "scroll", 60),
            ),
            ("normal", "virtual", "virtual", "normal", "normal", "virtual", "virtual", "normal", "normal", "virtual"),
            5,
        )
    if plan == "pilot":
        return (( (100, "scroll", -1), (100, "lifecycle", -1) ), ("normal", "virtual"), 1)
    if plan == "stress":
        return (( (300, "scroll", -1), (10000, "scroll", -1) ), ("normal", "virtual"), 1)
    _fail("plan", "unsupported plan {!r}".format(plan))


def _expected_plan_specs(plan: str) -> List[Dict[str, Any]]:
    groups, order, repeats = _plan_groups(plan)
    specs: List[Dict[str, Any]] = []
    for item_count, profile, target in groups:
        indexes = {"normal": 0, "virtual": 0}
        for backend in order:
            indexes[backend] += 1
            specs.append(
                {
                    "caseId": "list-{}-{}-{}".format(backend, item_count, profile),
                    "targetFrameRate": target,
                    "runIndex": indexes[backend],
                    "plannedRepeatCount": repeats,
                    "warmupFrames": 300,
                    "measureFrames": 1800,
                }
            )
    return specs


def _validate_plan_manifest(manifest: Mapping[str, Any], plan: str) -> None:
    if plan == FIXTURE_PLAN:
        return
    if plan not in PLAN_NAMES:
        _fail("plan", "must be one of {}".format(", ".join(PLAN_NAMES)))
    expected = _expected_plan_specs(plan)
    actual = manifest["runs"]
    if len(actual) != len(expected):
        _fail("manifest.runs", "{} plan requires {} runs, found {}".format(plan, len(expected), len(actual)))
    for index, (found, wanted) in enumerate(zip(actual, expected)):
        context = "manifest.runs[{}]".format(index)
        for field in ("caseId", "targetFrameRate", "runIndex", "plannedRepeatCount", "warmupFrames", "measureFrames"):
            _assert_equal(found[field], wanted[field], context + "." + field)


def _infer_plan(manifest: Mapping[str, Any]) -> str:
    matches: List[str] = []
    for plan in PLAN_NAMES:
        try:
            _validate_plan_manifest(manifest, plan)
            matches.append(plan)
        except VerificationError:
            pass
    if len(matches) == 1:
        return matches[0]
    _fail("manifest", "does not match exactly one supported plan; pass an explicit plan")


def _assert_no_reparse_components(path: Path, context: str) -> None:
    """Reject symlinks, junctions and other Windows reparse points in a path."""
    absolute = Path(os.path.abspath(os.path.normpath(str(path))))
    chain = list(reversed(absolute.parents)) + [absolute]
    seen = set()
    for candidate in chain:
        candidate_text = os.path.normcase(str(candidate))
        if candidate_text in seen:
            continue
        seen.add(candidate_text)
        try:
            info = os.lstat(str(candidate))
        except FileNotFoundError:
            continue
        except OSError as exc:
            _fail(context, "cannot inspect path component {} ({})".format(candidate, exc))
        if stat.S_ISLNK(info.st_mode) or (getattr(info, "st_file_attributes", 0) & REPARSE_POINT_ATTRIBUTE):
            _fail(context, "path component {} is a symlink, junction or reparse point".format(candidate))


class VerificationError(Exception):
    """An evidence contract violation with a user-facing location."""


def _fail(context: str, message: str) -> None:
    raise VerificationError("{}: {}".format(context, message))


def _reject_json_constant(value: str) -> None:
    raise VerificationError("JSON contains non-finite numeric constant {!r}".format(value))


def _reject_duplicate_keys(pairs: List[Tuple[str, Any]]) -> Dict[str, Any]:
    result: Dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise VerificationError("JSON contains duplicate property {!r}".format(key))
        result[key] = value
    return result


def _read_json(path: Path) -> Any:
    try:
        text = path.read_bytes().decode("utf-8")
    except (OSError, UnicodeError) as exc:
        _fail(str(path), "cannot read UTF-8 JSON ({})".format(exc))
    try:
        return json.loads(
            text,
            parse_constant=_reject_json_constant,
            object_pairs_hook=_reject_duplicate_keys,
        )
    except VerificationError:
        raise
    except (TypeError, ValueError, json.JSONDecodeError) as exc:
        _fail(str(path), "invalid JSON ({})".format(exc))


def _write_json(path: Path, value: Mapping[str, Any]) -> None:
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        data = json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False)
        path.write_text(data + "\n", encoding="utf-8", newline="\n")
    except (OSError, TypeError, ValueError) as exc:
        _fail(str(path), "cannot write report ({})".format(exc))


def _require_dict(value: Any, context: str) -> Dict[str, Any]:
    if not isinstance(value, dict):
        _fail(context, "must be a JSON object")
    return value


def _require_list(value: Any, context: str) -> List[Any]:
    if not isinstance(value, list):
        _fail(context, "must be a JSON array")
    return value


def _assert_fields(value: Mapping[str, Any], expected: Sequence[str], context: str) -> None:
    actual = set(value.keys())
    wanted = set(expected)
    missing = [name for name in expected if name not in actual]
    extra = sorted(name for name in actual if name not in wanted)
    if missing or extra or len(actual) != len(expected):
        _fail(
            context,
            "property set mismatch; missing=[{}]; extra=[{}]".format(
                ", ".join(missing) if missing else "none",
                ", ".join(extra) if extra else "none",
            ),
        )


def _require_string(value: Any, context: str, nonempty: bool = False) -> str:
    if not isinstance(value, str):
        _fail(context, "must be a JSON string")
    if nonempty and not value.strip():
        _fail(context, "must be non-empty")
    return value


def _require_identity(value: Any, context: str) -> str:
    result = _require_string(value, context, nonempty=True)
    if result.strip().lower() == "unknown":
        _fail(context, "must be an explicit identity")
    return result


def _require_bool(value: Any, context: str) -> bool:
    if not isinstance(value, bool):
        _fail(context, "must be a JSON boolean")
    return value


def _require_int(value: Any, context: str, nonnegative: bool = False) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        _fail(context, "must be a JSON integer")
    if nonnegative and value < 0:
        _fail(context, "must be non-negative")
    return value


def _require_number(value: Any, context: str, nonnegative: bool = False) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        _fail(context, "must be a JSON number")
    result = float(value)
    if not math.isfinite(result):
        _fail(context, "must be finite")
    if nonnegative and result < 0.0:
        _fail(context, "must be non-negative")
    return result


def _require_nullable_number(value: Any, context: str) -> Optional[float]:
    if value is None:
        return None
    return _require_number(value, context)


def _require_nullable_int(value: Any, context: str) -> Optional[int]:
    if value is None:
        return None
    return _require_int(value, context, nonnegative=True)


def _assert_equal(actual: Any, expected: Any, context: str) -> None:
    # bool is an int subclass in Python, so equality alone is not a type check.
    if type(actual) is not type(expected) or actual != expected:
        _fail(context, "expected {!r}, found {!r}".format(expected, actual))


def _assert_near(actual: float, expected: float, tolerance: float, context: str) -> None:
    if not math.isfinite(actual) or not math.isfinite(expected) or abs(actual - expected) > tolerance:
        _fail(context, "expected {:.12g}, found {:.12g} (tolerance {})".format(actual, expected, tolerance))


def _parse_float_text(value: str, context: str, nonnegative: bool = False) -> float:
    if not isinstance(value, str) or not value or not FLOAT_TEXT_RE.fullmatch(value):
        _fail(context, "must be a finite decimal number")
    try:
        result = float(value)
    except ValueError:
        _fail(context, "must be a finite decimal number")
    if not math.isfinite(result):
        _fail(context, "must be finite")
    if nonnegative and result < 0.0:
        _fail(context, "must be non-negative")
    return result


def _parse_int_text(value: str, context: str) -> int:
    if not isinstance(value, str) or not INTEGER_TEXT_RE.fullmatch(value):
        _fail(context, "must be a non-negative decimal integer")
    try:
        return int(value, 10)
    except ValueError:
        _fail(context, "must be a non-negative decimal integer")


def _percentile(values: Sequence[float], percentile: float) -> float:
    if not values:
        raise VerificationError("percentile requires at least one value")
    ordered = sorted(float(value) for value in values)
    if len(ordered) == 1:
        return ordered[0]
    position = (len(ordered) - 1) * percentile
    lower = int(math.floor(position))
    upper = int(math.ceil(position))
    if lower == upper:
        return ordered[lower]
    weight = position - lower
    return ordered[lower] + ((ordered[upper] - ordered[lower]) * weight)


def _distribution(values: Sequence[float]) -> Dict[str, float]:
    if not values:
        raise VerificationError("distribution requires at least one value")
    median = _percentile(values, 0.5)
    deviations = [abs(value - median) for value in values]
    return {
        "median": median,
        "minimum": min(values),
        "maximum": max(values),
        "mad": _percentile(deviations, 0.5),
        "iqr": _percentile(values, 0.75) - _percentile(values, 0.25),
    }


def _safe_run_id(value: Any, context: str) -> str:
    run_id = _require_string(value, context, nonempty=True)
    if run_id in (".", "..") or not SAFE_RUN_ID_RE.fullmatch(run_id):
        _fail(context, "must be one safe path segment")
    if Path(run_id).name != run_id:
        _fail(context, "must be one safe path segment")
    return run_id


def _case_parts(case_id: str, context: str) -> Tuple[str, int, str, bool]:
    match = CASE_RE.fullmatch(case_id)
    if not match:
        _fail(context, "must match list-(normal|virtual)-(100|300|1000|10000)-(scroll|lifecycle)")
    mode, count_text, action, = match.group(1), match.group(2), match.group(3)
    return mode, int(count_text), action, mode == "virtual"


def _normal_path(path_value: str) -> str:
    return os.path.normcase(os.path.abspath(os.path.normpath(path_value)))


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    try:
        with path.open("rb") as handle:
            for block in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(block)
    except OSError as exc:
        _fail(str(path), "cannot hash file ({})".format(exc))
    return digest.hexdigest().upper()


def _artifact_set_hash(run_dir: Path) -> str:
    lines: List[str] = []
    # Keep the same stable name/hash line convention as the M0 verifier, with
    # the two List Lab files included in lexical order after the base set.
    for name in sorted(LIST_ARTIFACTS):
        lines.append(name + "|" + _sha256(run_dir / name))
    payload = ("\n".join(lines) + "\n").encode("utf-8")
    return hashlib.sha256(payload).hexdigest().upper()


def _read_text_file(path: Path, context: str, require_nonempty: bool = False) -> str:
    try:
        # Path.read_text(newline=...) requires Python 3.13; preserve line endings on 3.11+.
        with path.open(encoding="utf-8", newline="") as stream:
            text = stream.read()
    except (OSError, UnicodeError) as exc:
        _fail(context, "cannot read text file ({})".format(exc))
    if require_nonempty and not text:
        _fail(context, "must be non-empty")
    return text


def _load_manifest(path: Path) -> Dict[str, Any]:
    value = _require_dict(_read_json(path), "manifest")
    _assert_fields(value, ("candidateId", "buildId", "sourceRevision", "runs"), "manifest")
    candidate_id = _require_identity(value["candidateId"], "manifest.candidateId")
    build_id = _require_identity(value["buildId"], "manifest.buildId")
    source_revision = _require_identity(value["sourceRevision"], "manifest.sourceRevision")
    runs_value = _require_list(value["runs"], "manifest.runs")
    if not runs_value:
        _fail("manifest.runs", "must contain at least one run")

    specs: List[Dict[str, Any]] = []
    seen_run_ids = set()
    for index, raw in enumerate(runs_value):
        context = "manifest.runs[{}]".format(index)
        item = _require_dict(raw, context)
        fields = ("runId", "caseId", "targetFrameRate", "runIndex", "plannedRepeatCount", "warmupFrames", "measureFrames")
        _assert_fields(item, fields, context)
        run_id = _safe_run_id(item["runId"], context + ".runId")
        case_id = _require_string(item["caseId"], context + ".caseId", nonempty=True)
        _case_parts(case_id, context + ".caseId")
        target = _require_int(item["targetFrameRate"], context + ".targetFrameRate")
        if target not in (-1, 60):
            _fail(context + ".targetFrameRate", "must be -1 or 60")
        run_index = _require_int(item["runIndex"], context + ".runIndex", nonnegative=True)
        planned = _require_int(item["plannedRepeatCount"], context + ".plannedRepeatCount", nonnegative=True)
        warmup = _require_int(item["warmupFrames"], context + ".warmupFrames", nonnegative=True)
        measure = _require_int(item["measureFrames"], context + ".measureFrames", nonnegative=True)
        if run_index <= 0:
            _fail(context + ".runIndex", "must be positive")
        if planned <= 0:
            _fail(context + ".plannedRepeatCount", "must be positive")
        if measure <= 0:
            _fail(context + ".measureFrames", "must be positive")
        if run_id in seen_run_ids:
            _fail(context + ".runId", "duplicates another manifest run")
        seen_run_ids.add(run_id)
        specs.append({
            "runId": run_id,
            "caseId": case_id,
            "targetFrameRate": target,
            "runIndex": run_index,
            "plannedRepeatCount": planned,
            "warmupFrames": warmup,
            "measureFrames": measure,
        })

    return {
        "candidateId": candidate_id,
        "buildId": build_id,
        "sourceRevision": source_revision,
        "runs": specs,
    }


def _validate_config(config: Any, spec: Mapping[str, Any], manifest: Mapping[str, Any], root: Path, context: str) -> Dict[str, Any]:
    value = _require_dict(config, context)
    _assert_fields(value, CONFIG_FIELDS, context)
    string_fields = (
        "schemaVersion", "protocolVersion", "runId", "seriesId", "tier", "caseId",
        "caseVersion", "outputDirectory", "candidateId", "buildId", "sourceRevision",
    )
    for name in string_fields:
        _require_string(value[name], context + "." + name)
    int_fields = (
        "runIndex", "plannedRepeatCount", "seed", "warmupFrames", "measureFrames",
        "sampleCapacity", "readyTimeoutFrames", "targetFrameRate", "vSyncCount",
        "cpuIterationsPerFrame", "allocationBytesPerFrame",
    )
    for name in int_fields:
        _require_int(value[name], context + "." + name)
    for name in ("enableProfilerRecorders", "dirty", "quitWhenDone"):
        _require_bool(value[name], context + "." + name)
    _require_number(value["frameBudgetMs"], context + ".frameBudgetMs", nonnegative=True)
    if value["frameBudgetMs"] <= 0:
        _fail(context + ".frameBudgetMs", "must be positive")
    for name in ("requiredMetrics", "optionalMetrics"):
        array = _require_list(value[name], context + "." + name)
        for item_index, item in enumerate(array):
            _require_string(item, "{}.{}[{}]".format(context, name, item_index))
    fault = _require_dict(value["faultPlan"], context + ".faultPlan")
    _assert_fields(fault, FAULT_FIELDS, context + ".faultPlan")
    _require_string(fault["mode"], context + ".faultPlan.mode")
    _require_int(fault["triggerMeasureFrame"], context + ".faultPlan.triggerMeasureFrame", nonnegative=True)
    _require_int(fault["shortageSampleCount"], context + ".faultPlan.shortageSampleCount", nonnegative=True)

    expected_root = _normal_path(str(root))
    if _normal_path(value["outputDirectory"]) != expected_root:
        _fail(context + ".outputDirectory", "does not identify the artifact root")
    _assert_equal(value["schemaVersion"], CONFIG_SCHEMA, context + ".schemaVersion")
    _assert_equal(value["protocolVersion"], PROTOCOL_VERSION, context + ".protocolVersion")
    _assert_equal(value["runId"], spec["runId"], context + ".runId")
    _assert_equal(value["runIndex"], spec["runIndex"], context + ".runIndex")
    _assert_equal(value["plannedRepeatCount"], spec["plannedRepeatCount"], context + ".plannedRepeatCount")
    _assert_equal(value["tier"], "windows-development-player", context + ".tier")
    _assert_equal(value["caseId"], spec["caseId"], context + ".caseId")
    _assert_equal(value["caseVersion"], "1", context + ".caseVersion")
    _assert_equal(value["seed"], 1337, context + ".seed")
    _assert_equal(value["warmupFrames"], spec["warmupFrames"], context + ".warmupFrames")
    _assert_equal(value["measureFrames"], spec["measureFrames"], context + ".measureFrames")
    _assert_equal(value["sampleCapacity"], spec["measureFrames"], context + ".sampleCapacity")
    if value["readyTimeoutFrames"] <= 0:
        _fail(context + ".readyTimeoutFrames", "must be positive")
    _assert_near(float(value["frameBudgetMs"]), 16.6666667, 1e-8, context + ".frameBudgetMs")
    _assert_equal(value["targetFrameRate"], spec["targetFrameRate"], context + ".targetFrameRate")
    _assert_equal(value["vSyncCount"], 0, context + ".vSyncCount")
    _assert_equal(value["enableProfilerRecorders"], True, context + ".enableProfilerRecorders")
    if value["requiredMetrics"] != ["Frame Interval"]:
        _fail(context + ".requiredMetrics", "must be exactly ['Frame Interval']")
    if value["optionalMetrics"] != ["Main Thread", "GC Allocated In Frame", "System Used Memory"]:
        _fail(context + ".optionalMetrics", "does not match protocol v1")
    _assert_equal(value["cpuIterationsPerFrame"], 0, context + ".cpuIterationsPerFrame")
    _assert_equal(value["allocationBytesPerFrame"], 0, context + ".allocationBytesPerFrame")
    _assert_equal(value["candidateId"], manifest["candidateId"], context + ".candidateId")
    _assert_equal(value["buildId"], manifest["buildId"], context + ".buildId")
    _assert_equal(value["sourceRevision"], manifest["sourceRevision"], context + ".sourceRevision")
    _assert_equal(value["dirty"], True, context + ".dirty")
    _assert_equal(value["quitWhenDone"], True, context + ".quitWhenDone")
    _assert_equal(fault["mode"], "none", context + ".faultPlan.mode")
    _assert_equal(fault["triggerMeasureFrame"], 0, context + ".faultPlan.triggerMeasureFrame")
    _assert_equal(fault["shortageSampleCount"], 1, context + ".faultPlan.shortageSampleCount")
    return value


def _validate_capabilities(value: Any, context: str) -> Tuple[List[Dict[str, Any]], Dict[str, Dict[str, Any]]]:
    capabilities = _require_list(value, context)
    if len(capabilities) != 4:
        _fail(context, "must contain exactly four metric capabilities")
    result: List[Dict[str, Any]] = []
    by_name: Dict[str, Dict[str, Any]] = {}
    for index, raw in enumerate(capabilities):
        item_context = "{}[{}]".format(context, index)
        item = _require_dict(raw, item_context)
        _assert_fields(item, CAPABILITY_FIELDS, item_context)
        for name in ("name", "category", "unit", "status", "reason"):
            _require_string(item[name], item_context + "." + name)
        _require_bool(item["required"], item_context + ".required")
        if item["name"] in by_name:
            _fail(item_context + ".name", "duplicates another capability")
        by_name[item["name"]] = item
        result.append(item)
    expected_names = {"Frame Interval", "Main Thread", "GC Allocated In Frame", "System Used Memory"}
    if set(by_name) != expected_names:
        _fail(context, "capability names do not match protocol v1")
    frame = by_name["Frame Interval"]
    for field, expected in (("required", True), ("category", "BuiltIn"), ("unit", "Milliseconds"), ("status", "available"), ("reason", "")):
        _assert_equal(frame[field], expected, context + ".Frame Interval." + field)
    optional_specs = {
        "Main Thread": ("Internal", "TimeNanoseconds"),
        "GC Allocated In Frame": ("Memory", "Bytes"),
        "System Used Memory": ("Memory", "Bytes"),
    }
    for name, (category, unit) in optional_specs.items():
        item = by_name[name]
        _assert_equal(item["required"], False, context + ".{} .required".format(name))
        _assert_equal(item["category"], category, context + ".{}.category".format(name))
        if item["status"] not in ("available", "unavailable"):
            _fail(context + ".{}.status".format(name), "must be available or unavailable")
        if item["status"] == "available":
            _assert_equal(item["unit"], unit, context + ".{}.unit".format(name))
            _assert_equal(item["reason"], "", context + ".{}.reason".format(name))
        else:
            if item["unit"] not in (unit, "unknown"):
                _fail(context + ".{}.unit".format(name), "unsupported unit for unavailable metric")
            _require_string(item["reason"], context + ".{}.reason".format(name), nonempty=True)
    return result, by_name


def _environment_fingerprint(environment: Mapping[str, Any], capabilities: Sequence[Mapping[str, Any]]) -> str:
    stable = {
        name: environment[name]
        for name in ENVIRONMENT_FIELDS
        if name != "targetFrameRate"
    }
    stable["metricCapabilities"] = list(capabilities)
    return json.dumps(stable, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _validate_environment(value: Any, spec: Mapping[str, Any], context: str) -> Tuple[Dict[str, Any], str, Dict[str, Dict[str, Any]]]:
    environment = _require_dict(value, context)
    _assert_fields(environment, ENVIRONMENT_FIELDS, context)
    for name in ("schemaVersion", "tier", "unityVersion", "operatingSystem", "processorType", "graphicsDeviceName", "graphicsDeviceType", "graphicsDeviceVersion", "qualityLevel", "scriptingBackend", "buildType"):
        _require_string(environment[name], context + "." + name, nonempty=True)
    for name in ("processorCount", "screenWidth", "screenHeight", "vSyncCount", "targetFrameRate"):
        _require_int(environment[name], context + "." + name)
    capabilities, by_name = _validate_capabilities(environment["metricCapabilities"], context + ".metricCapabilities")
    _assert_equal(environment["schemaVersion"], ENVIRONMENT_SCHEMA, context + ".schemaVersion")
    _assert_equal(environment["tier"], "windows-development-player", context + ".tier")
    _assert_equal(environment["unityVersion"], "2022.3.45f1c1", context + ".unityVersion")
    if not WINDOWS_64BIT_RE.search(environment["operatingSystem"]):
        _fail(context + ".operatingSystem", "must identify a Windows 64-bit environment")
    if re.search(r"\b32[- ]?bit\b", environment["operatingSystem"], re.IGNORECASE):
        _fail(context + ".operatingSystem", "32-bit environments are not accepted")
    _assert_equal(environment["graphicsDeviceType"], "Direct3D11", context + ".graphicsDeviceType")
    _assert_equal(environment["screenWidth"], 960, context + ".screenWidth")
    _assert_equal(environment["screenHeight"], 540, context + ".screenHeight")
    _assert_equal(environment["qualityLevel"], "High Fidelity", context + ".qualityLevel")
    _assert_equal(environment["vSyncCount"], 0, context + ".vSyncCount")
    _assert_equal(environment["targetFrameRate"], spec["targetFrameRate"], context + ".targetFrameRate")
    _assert_equal(environment["scriptingBackend"], "mono", context + ".scriptingBackend")
    _assert_equal(environment["buildType"], "development", context + ".buildType")
    if environment["processorCount"] <= 0:
        _fail(context + ".processorCount", "must be positive")
    if environment["screenWidth"] <= 0 or environment["screenHeight"] <= 0:
        _fail(context, "screen dimensions must be positive")
    return environment, _environment_fingerprint(environment, capabilities), by_name


def _validate_identity(value: Any, spec: Mapping[str, Any], manifest: Mapping[str, Any], config_path: Path, context: str) -> Dict[str, Any]:
    identity = _require_dict(value, context)
    _assert_fields(identity, IDENTITY_FIELDS, context)
    for name in ("schemaVersion", "runId", "candidateId", "buildId", "sourceRevision", "runnerVersion", "configSha256", "createdUtc"):
        _require_string(identity[name], context + "." + name, nonempty=True)
    _require_bool(identity["dirty"], context + ".dirty")
    _assert_equal(identity["schemaVersion"], IDENTITY_SCHEMA, context + ".schemaVersion")
    _assert_equal(identity["runId"], spec["runId"], context + ".runId")
    _assert_equal(identity["candidateId"], manifest["candidateId"], context + ".candidateId")
    _assert_equal(identity["buildId"], manifest["buildId"], context + ".buildId")
    _assert_equal(identity["sourceRevision"], manifest["sourceRevision"], context + ".sourceRevision")
    _assert_equal(identity["dirty"], True, context + ".dirty")
    _assert_equal(identity["runnerVersion"], "1", context + ".runnerVersion")
    if not HASH_RE.fullmatch(identity["configSha256"]):
        _fail(context + ".configSha256", "must be an uppercase SHA-256 hex string")
    _assert_equal(identity["configSha256"], _sha256(config_path), context + ".configSha256")
    try:
        parsed = datetime.fromisoformat(identity["createdUtc"].replace("Z", "+00:00"))
    except ValueError as exc:
        _fail(context + ".createdUtc", "must be an ISO-8601 timestamp ({})".format(exc))
    if parsed.tzinfo is None:
        _fail(context + ".createdUtc", "must include a timezone")
    return identity


def _read_csv(path: Path, expected_header: Sequence[str], context: str) -> List[Dict[str, str]]:
    try:
        with path.open("r", encoding="utf-8", newline="") as handle:
            reader = csv.reader(handle)
            try:
                header = next(reader)
            except StopIteration:
                _fail(context, "is empty")
            if tuple(header) != tuple(expected_header):
                _fail(context, "header mismatch; expected {}".format(",".join(expected_header)))
            rows: List[Dict[str, str]] = []
            for row_index, row in enumerate(reader):
                if len(row) != len(expected_header):
                    _fail(context + " row {}".format(row_index), "column count mismatch")
                rows.append(dict(zip(expected_header, row)))
            return rows
    except (OSError, UnicodeError) as exc:
        _fail(context, "cannot read CSV ({})".format(exc))


def _validate_base_samples(path: Path, measure_frames: int, frame_budget: float, context: str) -> Dict[str, Any]:
    rows = _read_csv(path, BASE_SAMPLE_HEADER, context)
    if len(rows) != measure_frames:
        _fail(context, "expected {} data rows, found {}".format(measure_frames, len(rows)))
    intervals: List[float] = []
    optional_values: Dict[str, List[int]] = {"main_thread_ns": [], "gc_allocated_bytes": [], "system_used_memory_bytes": []}
    previous_frame: Optional[int] = None
    elapsed_sum = 0.0
    for index, row in enumerate(rows):
        row_context = "{} row {}".format(context, index)
        sample_index = _parse_int_text(row["sample_index"], row_context + ".sample_index")
        if sample_index != index:
            _fail(row_context + ".sample_index", "expected {}, found {}".format(index, sample_index))
        frame = _parse_int_text(row["unity_frame"], row_context + ".unity_frame")
        if previous_frame is not None and frame != previous_frame + 1:
            _fail(row_context + ".unity_frame", "frames are not consecutive")
        previous_frame = frame
        elapsed = _parse_float_text(row["elapsed_ms"], row_context + ".elapsed_ms", nonnegative=True)
        interval = _parse_float_text(row["frame_interval_ms"], row_context + ".frame_interval_ms", nonnegative=True)
        elapsed_sum += interval
        _assert_near(elapsed, elapsed_sum, 0.0001, row_context + ".elapsed_ms")
        intervals.append(interval)
        for name in optional_values:
            cell = row[name]
            if cell:
                optional_values[name].append(_parse_int_text(cell, row_context + "." + name))
    for name, values in optional_values.items():
        if values and len(values) != measure_frames:
            _fail(context + "." + name, "optional metric is only partially populated")
    computed = {
        "p50FrameIntervalMs": _percentile(intervals, 0.50),
        "p95FrameIntervalMs": _percentile(intervals, 0.95),
        "p99FrameIntervalMs": _percentile(intervals, 0.99),
        "maxFrameIntervalMs": max(intervals),
        "overBudgetRatio": sum(1 for value in intervals if value > frame_budget) / float(measure_frames),
        "optionalValues": optional_values,
        "frames": [
            _parse_int_text(row["unity_frame"], "{} row {}.unity_frame".format(context, index))
            for index, row in enumerate(rows)
        ],
    }
    return computed


def _validate_summary(value: Any, spec: Mapping[str, Any], base_stats: Mapping[str, Any], context: str) -> Dict[str, Any]:
    summary = _require_dict(value, context)
    _assert_fields(summary, SUMMARY_FIELDS, context)
    for name in ("schemaVersion", "runId", "state", "failureCode", "failureReason", "correctness", "measurementValidity", "performanceComparison"):
        _require_string(summary[name], context + "." + name)
    for name in ("processSuccess", "enteredMeasure", "exportSucceeded", "cleanupSucceeded"):
        _require_bool(summary[name], context + "." + name)
    _require_int(summary["exitCode"], context + ".exitCode")
    _require_int(summary["sampleCount"], context + ".sampleCount", nonnegative=True)
    for name in ("p50FrameIntervalMs", "p95FrameIntervalMs", "p99FrameIntervalMs", "maxFrameIntervalMs", "overBudgetRatio"):
        _require_number(summary[name], context + "." + name, nonnegative=True)
    _require_nullable_number(summary["meanMainThreadNanoseconds"], context + ".meanMainThreadNanoseconds")
    _require_nullable_int(summary["totalGcAllocatedBytes"], context + ".totalGcAllocatedBytes")
    _require_nullable_int(summary["lastSystemUsedMemoryBytes"], context + ".lastSystemUsedMemoryBytes")
    _assert_equal(summary["schemaVersion"], SUMMARY_SCHEMA, context + ".schemaVersion")
    _assert_equal(summary["runId"], spec["runId"], context + ".runId")
    _assert_equal(summary["state"], "completed", context + ".state")
    _assert_equal(summary["failureCode"], "none", context + ".failureCode")
    _assert_equal(summary["failureReason"], "", context + ".failureReason")
    _assert_equal(summary["correctness"], "pass", context + ".correctness")
    _assert_equal(summary["measurementValidity"], "valid", context + ".measurementValidity")
    _assert_equal(summary["performanceComparison"], "not_assessed", context + ".performanceComparison")
    _assert_equal(summary["processSuccess"], True, context + ".processSuccess")
    _assert_equal(summary["exitCode"], 0, context + ".exitCode")
    _assert_equal(summary["enteredMeasure"], True, context + ".enteredMeasure")
    _assert_equal(summary["exportSucceeded"], True, context + ".exportSucceeded")
    _assert_equal(summary["cleanupSucceeded"], True, context + ".cleanupSucceeded")
    _assert_equal(summary["sampleCount"], spec["measureFrames"], context + ".sampleCount")
    for name in ("p50FrameIntervalMs", "p95FrameIntervalMs", "p99FrameIntervalMs", "maxFrameIntervalMs", "overBudgetRatio"):
        _assert_near(float(summary[name]), float(base_stats[name]), 1e-6, context + "." + name)
    optional = base_stats["optionalValues"]
    if optional["main_thread_ns"]:
        expected = sum(optional["main_thread_ns"]) / float(len(optional["main_thread_ns"]))
        if summary["meanMainThreadNanoseconds"] is None:
            _fail(context + ".meanMainThreadNanoseconds", "must be present when CSV has samples")
        _assert_near(float(summary["meanMainThreadNanoseconds"]), expected, 1e-6, context + ".meanMainThreadNanoseconds")
    elif summary["meanMainThreadNanoseconds"] is not None:
        _fail(context + ".meanMainThreadNanoseconds", "must be null when CSV is empty")
    if optional["gc_allocated_bytes"]:
        if summary["totalGcAllocatedBytes"] is None:
            _fail(context + ".totalGcAllocatedBytes", "must be present when CSV has samples")
        _assert_equal(summary["totalGcAllocatedBytes"], sum(optional["gc_allocated_bytes"]), context + ".totalGcAllocatedBytes")
    elif summary["totalGcAllocatedBytes"] is not None:
        _fail(context + ".totalGcAllocatedBytes", "must be null when CSV is empty")
    if optional["system_used_memory_bytes"]:
        if summary["lastSystemUsedMemoryBytes"] is None:
            _fail(context + ".lastSystemUsedMemoryBytes", "must be present when CSV has samples")
        _assert_equal(summary["lastSystemUsedMemoryBytes"], optional["system_used_memory_bytes"][-1], context + ".lastSystemUsedMemoryBytes")
    elif summary["lastSystemUsedMemoryBytes"] is not None:
        _fail(context + ".lastSystemUsedMemoryBytes", "must be null when CSV is empty")
    return summary


def _validate_list_metrics(value: Any, spec: Mapping[str, Any], manifest: Mapping[str, Any], context: str) -> Dict[str, Any]:
    metrics = _require_dict(value, context)
    _assert_fields(metrics, LIST_METRICS_FIELDS, context)
    for name in ("schemaVersion", "runId", "caseId", "actionProfile", "correctness", "reason", "uiRebuildMetric", "uiRebuildReason"):
        _require_string(metrics[name], context + "." + name)
    _require_int(metrics["itemCount"], context + ".itemCount", nonnegative=True)
    _require_bool(metrics["virtualized"], context + ".virtualized")
    for name in ("coldBuildMs", "firstInteractiveMs", "maxPositionErrorPixels"):
        _require_number(metrics[name], context + "." + name, nonnegative=True)
    for name in (
        "createdAtMeasureStart", "destroyedAtMeasureStart", "finalCreated", "finalDestroyed",
        "finalLeased", "finalCached", "finalUniqueTotal", "cleanupUniqueTotal", "rejectedReturns", "sampleCount",
    ):
        _require_int(metrics[name], context + "." + name, nonnegative=True)
    mode, item_count, action, virtualized = _case_parts(spec["caseId"], context + ".caseId")
    _assert_equal(metrics["schemaVersion"], LIST_METRICS_SCHEMA, context + ".schemaVersion")
    _assert_equal(metrics["runId"], spec["runId"], context + ".runId")
    _assert_equal(metrics["caseId"], spec["caseId"], context + ".caseId")
    _assert_equal(metrics["actionProfile"], action, context + ".actionProfile")
    _assert_equal(metrics["itemCount"], item_count, context + ".itemCount")
    _assert_equal(metrics["virtualized"], virtualized, context + ".virtualized")
    _assert_equal(metrics["correctness"], "pass", context + ".correctness")
    _assert_equal(metrics["reason"], "", context + ".reason")
    if metrics["maxPositionErrorPixels"] > 0.05:
        _fail(context + ".maxPositionErrorPixels", "must be <= 0.05 pixels")
    _assert_equal(metrics["cleanupUniqueTotal"], 0, context + ".cleanupUniqueTotal")
    _assert_equal(metrics["rejectedReturns"], 0, context + ".rejectedReturns")
    _assert_equal(metrics["sampleCount"], spec["measureFrames"], context + ".sampleCount")
    _assert_equal(metrics["uiRebuildMetric"], "unavailable", context + ".uiRebuildMetric")
    _require_string(metrics["uiRebuildReason"], context + ".uiRebuildReason", nonempty=True)
    if metrics["finalLeased"] + metrics["finalCached"] != metrics["finalUniqueTotal"]:
        _fail(context, "final unique total must equal final leased + final cached")
    if metrics["finalCreated"] - metrics["finalDestroyed"] != metrics["finalUniqueTotal"]:
        _fail(context, "final unique total must equal final created - final destroyed")
    if metrics["finalDestroyed"] > metrics["finalCreated"]:
        _fail(context, "final destroyed cannot exceed final created")
    if virtualized and metrics["finalLeased"] > 13:
        _fail(context + ".finalLeased", "virtual leased count must be <= 13")
    if virtualized and metrics["finalUniqueTotal"] > 29:
        _fail(context + ".finalUniqueTotal", "single-template virtual unique count must be <= 29")
    if metrics["finalCached"] > 16:
        _fail(context + ".finalCached", "single-template cache count must be <= 16")
    if not virtualized and action == "scroll" and metrics["finalLeased"] != item_count:
        _fail(context + ".finalLeased", "normal scroll must retain N leased cells")
    return metrics


def _validate_list_samples(
    path: Path,
    spec: Mapping[str, Any],
    metrics: Mapping[str, Any],
    base_stats: Mapping[str, Any],
    context: str,
) -> Dict[str, Any]:
    rows = _read_csv(path, LIST_SAMPLE_HEADER, context)
    measure_frames = spec["measureFrames"]
    if len(rows) != measure_frames:
        _fail(context, "expected {} data rows, found {}".format(measure_frames, len(rows)))
    _, item_count, action, virtualized = _case_parts(spec["caseId"], context + ".caseId")
    max_offset = max(0.0, item_count * ROW_HEIGHT - VIEWPORT_HEIGHT)
    parsed: List[Dict[str, Any]] = []
    previous_frame: Optional[int] = None
    previous_counters: Optional[Dict[str, int]] = None
    for index, row in enumerate(rows):
        row_context = "{} row {}".format(context, index)
        sample_index = _parse_int_text(row["sample_index"], row_context + ".sample_index")
        if sample_index != index:
            _fail(row_context + ".sample_index", "expected {}, found {}".format(index, sample_index))
        frame = _parse_int_text(row["unity_frame"], row_context + ".unity_frame")
        if previous_frame is not None and frame != previous_frame + 1:
            _fail(row_context + ".unity_frame", "frames are not consecutive")
        previous_frame = frame
        offset = _parse_float_text(row["offset"], row_context + ".offset", nonnegative=True)
        if offset > max_offset + 0.05:
            _fail(row_context + ".offset", "exceeds content maximum")
        expected_offset = _expected_action_offset(action, index, max_offset)
        _assert_near(offset, expected_offset, POSITION_TOLERANCE, row_context + ".offset")
        counters: Dict[str, int] = {}
        for name in ("visible", "active", "leased", "cached", "created", "destroyed", "bind_count", "unbind_count"):
            counters[name] = _parse_int_text(row[name], row_context + "." + name)
        expected_live = _expected_live_state(action, index)
        expected_leased = _expected_leased_count(
            item_count, offset, virtualized, expected_live
        )
        expected_active = expected_leased
        expected_visible = _expected_visible_count(
            item_count, offset, expected_live
        )
        _assert_equal(counters["leased"], expected_leased, row_context + ".leased")
        _assert_equal(counters["active"], expected_active, row_context + ".active")
        _assert_equal(counters["visible"], expected_visible, row_context + ".visible")
        if counters["destroyed"] > counters["created"]:
            _fail(row_context, "destroyed cannot exceed created")
        if counters["leased"] + counters["cached"] != counters["created"] - counters["destroyed"]:
            _fail(row_context, "leased + cached must equal created - destroyed")
        if counters["bind_count"] < counters["unbind_count"]:
            _fail(row_context, "unbind_count cannot exceed bind_count")
        if counters["bind_count"] - counters["unbind_count"] != counters["leased"]:
            _fail(row_context, "bound count must equal leased count")
        if virtualized and counters["leased"] > 13:
            _fail(row_context + ".leased", "virtual leased count must be <= 13")
        if virtualized and counters["leased"] + counters["cached"] > 29:
            _fail(row_context, "single-template virtual unique count must be <= 29")
        if counters["cached"] > 16:
            _fail(row_context + ".cached", "single-template cache count must be <= 16")
        if previous_counters is not None:
            for name in ("created", "destroyed", "bind_count", "unbind_count"):
                if counters[name] < previous_counters[name]:
                    _fail(row_context + "." + name, "cumulative counter decreased")
        previous_counters = counters
        parsed.append({"sample_index": sample_index, "unity_frame": frame, "offset": offset, **counters})

    if parsed[0]["created"] != metrics["createdAtMeasureStart"] or parsed[0]["destroyed"] != metrics["destroyedAtMeasureStart"]:
        _fail(context, "first row counters do not match measure-start counters")
    last = parsed[-1]
    for name, row_name in (
        ("finalCreated", "created"), ("finalDestroyed", "destroyed"),
        ("finalLeased", "leased"), ("finalCached", "cached"),
    ):
        _assert_equal(metrics[name], last[row_name], "{}.{}".format(context, name))
    _assert_equal(metrics["finalUniqueTotal"], last["leased"] + last["cached"], context + ".finalUniqueTotal")

    if action == "scroll":
        expected_created = metrics["createdAtMeasureStart"]
        expected_destroyed = metrics["destroyedAtMeasureStart"]
        for index, row in enumerate(parsed):
            _assert_equal(row["created"], expected_created, "{} row {} created".format(context, index))
            _assert_equal(row["destroyed"], expected_destroyed, "{} row {} destroyed".format(context, index))
        if not virtualized:
            for index, row in enumerate(parsed):
                _assert_equal(row["leased"], item_count, "{} row {} leased".format(context, index))
    else:
        _validate_lifecycle_timeline(parsed, item_count, max_offset, virtualized, context)

    list_frames = [row["unity_frame"] for row in parsed]
    base_frames = base_stats["frames"]
    for index, (list_frame, base_frame) in enumerate(zip(list_frames, base_frames)):
        if base_frame != list_frame + 1:
            _fail("{} row {}".format(context, index), "base sample unity_frame must equal list frame + 1")
    return {"rows": parsed, "frames": list_frames, "maxOffset": max_offset}


def _near(actual: float, expected: float, tolerance: float = POSITION_TOLERANCE) -> bool:
    return math.isfinite(actual) and abs(actual - expected) <= tolerance


def _triangle(frame: int, period: int) -> float:
    """Match ListBenchmarkCase.Triangle exactly for non-negative frames."""
    phase = frame % period
    half = period // 2
    if phase <= half:
        return phase / float(half)
    return (period - 1 - phase) / float(period - 1 - half)


def _expected_action_offset(action: str, frame: int, max_offset: float) -> float:
    """Return the frozen action offset for one measured frame."""
    if action == "scroll":
        return _triangle(frame, 600) * max_offset
    if action != "lifecycle":
        _fail("actionProfile", "unsupported action profile {!r}".format(action))

    saved = max_offset * 0.4525
    if frame < 300:
        return 0.0
    if frame < 1200:
        return _triangle(frame - 300, 900) * max_offset
    if frame < 1260:
        return 0.0
    if frame < 1320:
        return max_offset
    if frame < 1440:
        return saved
    if frame < 1500:
        return 0.0
    return saved


def _expected_live_state(action: str, frame: int) -> bool:
    """Whether the ListLab view has active, non-empty content at this action."""
    return not (action == "lifecycle" and (1440 <= frame < 1500 or 1560 <= frame < 1620))


def _window_bounds(item_count: int, offset: float) -> Tuple[int, int]:
    offset = _snap_layout_boundary(offset)
    first = max(0, int(math.floor(offset / ROW_HEIGHT)) - PREFETCH_ROWS)
    end = min(item_count, int(math.ceil((offset + VIEWPORT_HEIGHT) / ROW_HEIGHT)) + PREFETCH_ROWS)
    return first, end


def _visible_bounds(item_count: int, offset: float) -> Tuple[int, int]:
    offset = _snap_layout_boundary(offset)
    first = min(item_count, int(math.floor(offset / ROW_HEIGHT)))
    end = min(item_count, int(math.ceil((offset + VIEWPORT_HEIGHT) / ROW_HEIGHT)))
    return first, end


def _snap_layout_boundary(offset: float) -> float:
    """Avoid double-rounding artifacts at exact row boundaries."""
    nearest = round(offset)
    return float(nearest) if abs(offset - nearest) <= 1e-5 else offset


def _expected_leased_count(item_count: int, offset: float, virtualized: bool, live: bool) -> int:
    if not live or item_count == 0:
        return 0
    if not virtualized:
        return item_count
    first, end = _window_bounds(item_count, offset)
    return end - first


def _expected_visible_count(item_count: int, offset: float, live: bool) -> int:
    if not live or item_count == 0:
        return 0
    first, end = _visible_bounds(item_count, offset)
    return end - first


def _validate_lifecycle_timeline(rows: Sequence[Mapping[str, Any]], item_count: int, max_offset: float, virtualized: bool, context: str) -> None:
    # Keep this second pass explicit: it documents the complete lifecycle
    # phases and makes direct regression tests fail on a single changed row.
    for index, row in enumerate(rows):
        expected = _expected_action_offset("lifecycle", index, max_offset)
        _assert_near(float(row["offset"]), expected, POSITION_TOLERANCE, "{} row {} offset".format(context, index))
        live = _expected_live_state("lifecycle", index)
        actual_offset = float(row["offset"])
        expected_leased = _expected_leased_count(item_count, actual_offset, virtualized, live)
        expected_visible = _expected_visible_count(item_count, actual_offset, live)
        _assert_equal(row["leased"], expected_leased, "{} row {} leased".format(context, index))
        _assert_equal(row["active"], expected_leased, "{} row {} active".format(context, index))
        _assert_equal(row["visible"], expected_visible, "{} row {} visible".format(context, index))


def _validate_run(
    root: Path,
    spec: Mapping[str, Any],
    manifest: Mapping[str, Any],
    recorded_root: Optional[str] = None,
) -> Dict[str, Any]:
    run_dir = root / spec["runId"]
    context = spec["runId"]
    _assert_no_reparse_components(run_dir, context + "/run")
    if not run_dir.is_dir():
        _fail(context, "run directory is missing")
    try:
        children = list(os.scandir(run_dir))
    except OSError as exc:
        _fail(context, "cannot enumerate run directory ({})".format(exc))
    actual_names = sorted(entry.name for entry in children)
    expected_names = sorted(LIST_ARTIFACTS)
    if actual_names != expected_names:
        _fail(context, "run directory must contain exactly nine files; found {}".format(", ".join(actual_names)))
    if any(entry.is_dir(follow_symlinks=False) for entry in children):
        _fail(context, "run directory cannot contain child directories")
    for entry in children:
        if not entry.is_file(follow_symlinks=False):
            _fail(context, "artifact {} is not a regular file".format(entry.name))

    config_path = run_dir / "config.json"
    environment_path = run_dir / "environment.json"
    identity_path = run_dir / "identity.json"
    summary_path = run_dir / "summary.json"
    list_metrics_path = run_dir / "list-metrics.json"
    base_samples_path = run_dir / "samples.csv"
    list_samples_path = run_dir / "list-samples.csv"
    _read_text_file(run_dir / "events.log", context + "/events.log")
    _read_text_file(run_dir / "report.md", context + "/report.md")

    # An explicit relocation mapping changes only path comparison, never bytes,
    # identities, hashes, statistical checks or the rest of the config contract.
    config = _validate_config(_read_json(config_path), spec, manifest,
                              root if recorded_root is None else recorded_root, context + "/config")
    environment, environment_fingerprint, capability_by_name = _validate_environment(
        _read_json(environment_path), spec, context + "/environment"
    )
    identity = _validate_identity(_read_json(identity_path), spec, manifest, config_path, context + "/identity")
    base_stats = _validate_base_samples(
        base_samples_path,
        spec["measureFrames"],
        float(config["frameBudgetMs"]),
        context + "/samples.csv",
    )
    optional_columns = {
        "Main Thread": "main_thread_ns",
        "GC Allocated In Frame": "gc_allocated_bytes",
        "System Used Memory": "system_used_memory_bytes",
    }
    for name, column in optional_columns.items():
        values = base_stats["optionalValues"][column]
        capability = capability_by_name[name]
        expected_status = "available" if values else "unavailable"
        _assert_equal(capability["status"], expected_status, context + "/environment.metricCapabilities." + name + ".status")
        if expected_status == "available":
            _assert_equal(capability["reason"], "", context + "/environment.metricCapabilities." + name + ".reason")
        elif not capability["reason"].strip():
            _fail(context + "/environment.metricCapabilities." + name + ".reason", "must explain unavailable metric")
    summary = _validate_summary(_read_json(summary_path), spec, base_stats, context + "/summary")
    list_metrics = _validate_list_metrics(_read_json(list_metrics_path), spec, manifest, context + "/list-metrics")
    list_samples = _validate_list_samples(
        list_samples_path,
        spec,
        list_metrics,
        base_stats,
        context + "/list-samples.csv",
    )

    # The List CSV is an action-side companion stream.  The C# writer emits
    # one action row for every base sample; checking both directions catches
    # dropped, duplicated, and shifted rows.
    if len(base_stats["frames"]) != len(list_samples["frames"]):
        _fail(context, "base and List sample streams have different lengths")
    for index, (base_frame, list_frame) in enumerate(zip(base_stats["frames"], list_samples["frames"])):
        if base_frame != list_frame + 1:
            _fail(context + " sample {}".format(index), "base frame is not List action frame + 1")

    record = {
        "runId": spec["runId"],
        "caseId": spec["caseId"],
        "targetFrameRate": spec["targetFrameRate"],
        "runIndex": spec["runIndex"],
        "plannedRepeatCount": spec["plannedRepeatCount"],
        "warmupFrames": spec["warmupFrames"],
        "measureFrames": spec["measureFrames"],
        "candidateId": identity["candidateId"],
        "buildId": identity["buildId"],
        "sourceRevision": identity["sourceRevision"],
        "configSha256": identity["configSha256"],
        "artifactSetSha256": _artifact_set_hash(run_dir),
        "environmentFingerprint": hashlib.sha256(environment_fingerprint.encode("utf-8")).hexdigest().upper(),
        "p50FrameIntervalMs": float(summary["p50FrameIntervalMs"]),
        "p95FrameIntervalMs": float(summary["p95FrameIntervalMs"]),
        "p99FrameIntervalMs": float(summary["p99FrameIntervalMs"]),
        "maxFrameIntervalMs": float(summary["maxFrameIntervalMs"]),
        "overBudgetRatio": float(summary["overBudgetRatio"]),
        "listMetrics": dict(list_metrics),
    }
    return {"record": record, "environmentFingerprint": environment_fingerprint, "environment": environment, "capabilities": capability_by_name}


def _aggregate_records(records: Sequence[Mapping[str, Any]]) -> Dict[str, Any]:
    first = records[0]
    result: Dict[str, Any] = {
        "caseId": first["caseId"],
        "targetFrameRate": first["targetFrameRate"],
        "repeatCount": len(records),
        "runIndexes": [record["runIndex"] for record in records],
    }
    for name in ("p50FrameIntervalMs", "p95FrameIntervalMs", "p99FrameIntervalMs", "maxFrameIntervalMs", "overBudgetRatio"):
        result[name] = _distribution([float(record[name]) for record in records])
    for name in ("coldBuildMs", "firstInteractiveMs", "maxPositionErrorPixels"):
        result[name] = _distribution([float(record["listMetrics"][name]) for record in records])
    for name in (
        "createdAtMeasureStart", "destroyedAtMeasureStart", "finalCreated", "finalDestroyed",
        "finalLeased", "finalCached", "finalUniqueTotal", "cleanupUniqueTotal", "rejectedReturns",
    ):
        result[name] = _distribution([float(record["listMetrics"][name]) for record in records])
    return result


def verify(root: Path, manifest: Mapping[str, Any], plan: Optional[str] = None,
           recorded_root: Optional[str] = None) -> Dict[str, Any]:
    """Verify all manifest runs and return the report object.

    ``manifest`` may be an already parsed object, which keeps the function
    useful for callers and the regression tests.  CLI callers should use
    :func:`_load_manifest` to retain the strict JSON parser.
    """
    root = Path(os.path.abspath(os.path.normpath(str(root))))
    _assert_no_reparse_components(root, "root")
    if not root.is_dir():
        _fail("root", "artifact root is not a directory")
    # Re-validate an in-memory manifest with the same shape rules used by the
    # CLI.  This also prevents tests/callers from bypassing type checks.
    manifest_value = _load_manifest_from_value(manifest)
    selected_plan = _infer_plan(manifest_value) if plan is None else plan
    _validate_plan_manifest(manifest_value, selected_plan)
    results: List[Dict[str, Any]] = []
    env_by_target: Dict[int, str] = {}
    for spec in manifest_value["runs"]:
        result = _validate_run(root, spec, manifest_value, recorded_root=recorded_root)
        fingerprint = result["environmentFingerprint"]
        target = spec["targetFrameRate"]
        if target in env_by_target and env_by_target[target] != fingerprint:
            _fail(spec["runId"], "environment fingerprint differs within target-frame-rate group")
        env_by_target[target] = fingerprint
        results.append(result["record"])

    groups: Dict[Tuple[str, int], List[Dict[str, Any]]] = {}
    for record in results:
        groups.setdefault((record["caseId"], record["targetFrameRate"]), []).append(record)
    aggregates: List[Dict[str, Any]] = []
    for key in sorted(groups):
        group_records = sorted(groups[key], key=lambda item: item["runIndex"])
        planned = group_records[0]["plannedRepeatCount"]
        if len(group_records) != planned:
            _fail("{}@{}".format(key[0], key[1]), "expected {} runs, found {}".format(planned, len(group_records)))
        indexes = [record["runIndex"] for record in group_records]
        if indexes != list(range(1, planned + 1)):
            _fail("{}@{}".format(key[0], key[1]), "run indexes must be 1..{}".format(planned))
        for record in group_records[1:]:
            for field in ("plannedRepeatCount", "warmupFrames", "measureFrames"):
                if record[field] != group_records[0][field]:
                    _fail("{}@{}".format(key[0], key[1]), "{} differs between repeats".format(field))
        aggregates.append(_aggregate_records(group_records))

    # Keep the public report compact while retaining every run's independent
    # statistics and artifact identity.  No frame values are concatenated.
    return {
        "schemaVersion": "xuilab.list.verification/v1",
        "protocolVersion": PROTOCOL_VERSION,
        "plan": selected_plan,
        "percentileMethod": "linear interpolation at (n - 1) * p",
        "aggregateMethod": "per-run statistics; median, min, max, MAD, IQR; no frame concatenation",
        "candidateId": manifest_value["candidateId"],
        "buildId": manifest_value["buildId"],
        "sourceRevision": manifest_value["sourceRevision"],
        "runCount": len(results),
        "environmentFingerprintsByTargetFrameRate": {
            str(target): hashlib.sha256(value.encode("utf-8")).hexdigest().upper()
            for target, value in sorted(env_by_target.items())
        },
        "runs": sorted(results, key=lambda item: (item["caseId"], item["targetFrameRate"], item["runIndex"])),
        "aggregates": aggregates,
    }


def _load_manifest_from_value(value: Mapping[str, Any]) -> Dict[str, Any]:
    # Use the same implementation as the JSON path loader without serializing
    # through JSON (which could silently turn tuples or custom objects into a
    # different contract).
    item = _require_dict(value, "manifest")
    _assert_fields(item, ("candidateId", "buildId", "sourceRevision", "runs"), "manifest")
    candidate = _require_identity(item["candidateId"], "manifest.candidateId")
    build = _require_identity(item["buildId"], "manifest.buildId")
    source = _require_identity(item["sourceRevision"], "manifest.sourceRevision")
    raw_runs = _require_list(item["runs"], "manifest.runs")
    if not raw_runs:
        _fail("manifest.runs", "must contain at least one run")
    specs: List[Dict[str, Any]] = []
    seen = set()
    fields = ("runId", "caseId", "targetFrameRate", "runIndex", "plannedRepeatCount", "warmupFrames", "measureFrames")
    for index, raw in enumerate(raw_runs):
        context = "manifest.runs[{}]".format(index)
        obj = _require_dict(raw, context)
        _assert_fields(obj, fields, context)
        run_id = _safe_run_id(obj["runId"], context + ".runId")
        case_id = _require_string(obj["caseId"], context + ".caseId", nonempty=True)
        _case_parts(case_id, context + ".caseId")
        target = _require_int(obj["targetFrameRate"], context + ".targetFrameRate")
        if target not in (-1, 60):
            _fail(context + ".targetFrameRate", "must be -1 or 60")
        run_index = _require_int(obj["runIndex"], context + ".runIndex", nonnegative=True)
        planned = _require_int(obj["plannedRepeatCount"], context + ".plannedRepeatCount", nonnegative=True)
        warmup = _require_int(obj["warmupFrames"], context + ".warmupFrames", nonnegative=True)
        measure = _require_int(obj["measureFrames"], context + ".measureFrames", nonnegative=True)
        if run_index <= 0 or planned <= 0 or measure <= 0:
            _fail(context, "runIndex, plannedRepeatCount and measureFrames must be positive")
        if run_id in seen:
            _fail(context + ".runId", "duplicates another manifest run")
        seen.add(run_id)
        specs.append({
            "runId": run_id, "caseId": case_id, "targetFrameRate": target,
            "runIndex": run_index, "plannedRepeatCount": planned,
            "warmupFrames": warmup, "measureFrames": measure,
        })
    return {"candidateId": candidate, "buildId": build, "sourceRevision": source, "runs": specs}


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Verify List Lab benchmark evidence.")
    parser.add_argument("--root", default="Artifacts", help="artifact root containing run directories")
    parser.add_argument("--manifest", required=True, help="strict JSON manifest")
    parser.add_argument("--recorded-root", help="explicit original outputDirectory when checking a relocated copy")
    parser.add_argument("--out", required=True, help="JSON report path")
    parser.add_argument(
        "--plan",
        choices=PLAN_NAMES,
        default="matrix",
        help="expected run plan; matrix is the default production contract",
    )
    args = parser.parse_args(argv)
    try:
        root = Path(args.root)
        manifest = _load_manifest(Path(args.manifest))
        report = verify(root, manifest, plan=args.plan, recorded_root=args.recorded_root)
        _write_json(Path(args.out), report)
        print("PASS runs={} aggregates={} out={}".format(report["runCount"], len(report["aggregates"]), args.out))
        return 0
    except VerificationError as exc:
        print("VERIFY FAILED: {}".format(exc), file=sys.stderr)
        return 1
    except (OSError, ValueError, TypeError) as exc:
        print("VERIFY FAILED: {}".format(exc), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
