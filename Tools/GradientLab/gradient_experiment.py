"""Offline Gradient Lab contracts and evidence analysis.

No Unity, GradientEffect, mesh generation, or colour function is implemented here.
M2-01 owns the opaque mathematical contract referenced by frozen plans.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import pathlib
import re
import stat
import sys

PLAN_SCHEMA = "xuilab.gradient.plan/v1"
QUALITY_SCHEMA = "xuilab.gradient.quality/v1"
RESULTS_SCHEMA = "xuilab.gradient.results/v1"
ANALYSIS_SCHEMA = "xuilab.gradient.analysis/v1"
PROTOCOL_VERSION = "xuilab.benchmark.protocol/v1"
REPARSE_POINT_ATTRIBUTE = 0x400
HASH_RE = re.compile(r"^[0-9A-Fa-f]{64}$")
IDENTIFIER_RE = re.compile(r'^[^<>:"/\\|?*\x00-\x1f]+$')


class GradientToolError(ValueError):
    """A contract or evidence violation."""


def _fail(context, message):
    raise GradientToolError(f"{context}: {message}")


def _reject_constant(value):
    raise ValueError(f"non-finite JSON constant {value}")


def _reject_duplicates(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"duplicate JSON key {key!r}")
        result[key] = value
    return result


def _finite(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(float(value))


def _string(value, context, empty=False):
    if not isinstance(value, str) or (not empty and not value):
        _fail(context, "must be a string")
    return value


def _identifier(value, context, empty=False):
    value = _string(value, context, empty)
    if value and (value in (".", "..") or not IDENTIFIER_RE.fullmatch(value) or value[-1] in (".", " ")):
        _fail(context, "must be a safe identifier")
    return value


def _integer(value, context, positive=False, nonnegative=False):
    if not isinstance(value, int) or isinstance(value, bool):
        _fail(context, "must be an integer")
    if positive and value <= 0:
        _fail(context, "must be positive")
    if nonnegative and value < 0:
        _fail(context, "must be non-negative")
    return value


def _number(value, context, positive=False, nonnegative=False):
    if not _finite(value):
        _fail(context, "must be a finite number")
    value = float(value)
    if positive and value <= 0:
        _fail(context, "must be positive")
    if nonnegative and value < 0:
        _fail(context, "must be non-negative")
    return value


def _dict(value, context):
    if not isinstance(value, dict):
        _fail(context, "must be an object")
    return value


def _list(value, context):
    if not isinstance(value, list):
        _fail(context, "must be an array")
    return value


def _exact(value, fields, context):
    missing = sorted(set(fields) - set(value))
    extra = sorted(set(value) - set(fields))
    if missing or extra:
        pieces = []
        if missing:
            pieces.append("missing " + ", ".join(missing))
        if extra:
            pieces.append("extra " + ", ".join(extra))
        _fail(context, "; ".join(pieces))


def _hash(value):
    return isinstance(value, str) and HASH_RE.fullmatch(value) is not None


def _assert_no_reparse_components(path, context):
    raw = os.path.abspath(os.path.normpath(str(path)))
    current = pathlib.Path(raw)
    while True:
        try:
            if os.path.lexists(str(current)):
                info = os.lstat(str(current))
                if stat.S_ISLNK(info.st_mode) or int(getattr(info, "st_file_attributes", 0)) & REPARSE_POINT_ATTRIBUTE:
                    _fail(context, f"{current} is a symlink, junction, or reparse point")
        except FileNotFoundError:
            pass
        parent = current.parent
        if parent == current:
            break
        current = parent


def _assert_regular_file(path, context):
    path = pathlib.Path(path)
    _assert_no_reparse_components(path, context)
    try:
        info = os.lstat(str(path))
    except FileNotFoundError:
        _fail(context, "file is missing")
    if stat.S_ISLNK(info.st_mode) or int(getattr(info, "st_file_attributes", 0)) & REPARSE_POINT_ATTRIBUTE:
        _fail(context, "file is a symlink, junction, or reparse point")
    if not stat.S_ISREG(info.st_mode):
        _fail(context, "file is not regular")


def _assert_directory(path, context):
    path = pathlib.Path(path)
    _assert_no_reparse_components(path, context)
    if not path.is_dir():
        _fail(context, "directory is missing")


def read_json(path):
    path = pathlib.Path(path)
    _assert_regular_file(path, "JSON input")
    try:
        with path.open("r", encoding="utf-8") as stream:
            return json.load(stream, object_pairs_hook=_reject_duplicates, parse_constant=_reject_constant)
    except GradientToolError:
        raise
    except (OSError, UnicodeError, ValueError, TypeError) as exc:
        _fail(str(path), f"invalid JSON ({exc})")


def write_json_new(path, value):
    path = pathlib.Path(path)
    _assert_no_reparse_components(path, "JSON output")
    if os.path.lexists(str(path)):
        _fail(str(path), "refusing to overwrite existing file")
    payload = json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True, allow_nan=False) + "\n"
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        fd = os.open(str(path), os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(fd, "w", encoding="utf-8", newline="") as stream:
            stream.write(payload)
            stream.flush()
            os.fsync(stream.fileno())
    except FileExistsError:
        _fail(str(path), "refusing to overwrite existing file")
    except (OSError, ValueError, TypeError) as exc:
        _fail(str(path), f"cannot create JSON ({exc})")


def canonical_digest(value):
    try:
        payload = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)
    except (TypeError, ValueError) as exc:
        _fail("JSON value", f"cannot compute digest ({exc})")
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def sha256_file(path):
    path = pathlib.Path(path)
    _assert_regular_file(path, "hash input")
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


_PLAN_FIELDS = ("schemaVersion", "status", "planId", "experimentId", "protocolVersion", "contractId",
                "contractSha256", "candidateId", "buildId", "sourceRevision", "dirty", "evidenceKind",
                "budget", "quality", "comparison", "artifacts", "runs")
_RUN_FIELDS = ("runId", "groupId", "caseId", "variant", "runIndex", "plannedRepeatCount", "warmupFrames",
               "measureFrames", "sampleCapacity", "frameBudgetMs", "timeoutSeconds", "parameters")


def _comparison(value):
    if value is None:
        return None
    value = _dict(value, "plan.comparison")
    fields = ("leftGroupId", "rightGroupId", "metricId", "lowerIsBetter", "rule")
    _exact(value, fields, "plan.comparison")
    for field in fields[:3]:
        _identifier(value[field], f"plan.comparison.{field}")
    if not isinstance(value["lowerIsBetter"], bool):
        _fail("plan.comparison.lowerIsBetter", "must be boolean")
    if value["rule"] != "disjoint_range_and_mad":
        _fail("plan.comparison.rule", "unsupported comparison rule")
    if value["leftGroupId"] == value["rightGroupId"]:
        _fail("plan.comparison", "comparison groups must differ")
    return dict(value)


def validate_plan(value, require_frozen=False):
    plan = _dict(value, "plan")
    _exact(plan, _PLAN_FIELDS, "plan")
    if plan["schemaVersion"] != PLAN_SCHEMA:
        _fail("plan.schemaVersion", f"expected {PLAN_SCHEMA}")
    if plan["protocolVersion"] != PROTOCOL_VERSION:
        _fail("plan.protocolVersion", f"expected {PROTOCOL_VERSION}")
    status = _string(plan["status"], "plan.status")
    if status not in ("draft", "frozen"):
        _fail("plan.status", "must be draft or frozen")
    if require_frozen and status != "frozen":
        _fail("plan.status", "draft plan is not ready for evidence")
    for field in ("planId", "experimentId", "candidateId", "buildId", "sourceRevision"):
        _identifier(plan[field], f"plan.{field}")
    if not isinstance(plan["dirty"], bool):
        _fail("plan.dirty", "must be boolean")
    evidence = _string(plan["evidenceKind"], "plan.evidenceKind")
    if evidence not in ("fixture", "windows-development-player"):
        _fail("plan.evidenceKind", "must be fixture or windows-development-player")
    contract_id = _identifier(plan["contractId"], "plan.contractId", empty=True)
    contract_hash = plan["contractSha256"]
    if contract_hash is not None and not _hash(contract_hash):
        _fail("plan.contractSha256", "must be null or SHA-256")
    if status == "frozen" and (not contract_id or contract_hash is None):
        _fail("plan", "frozen plans require contractId and contractSha256")
    if status == "draft" and contract_hash is not None and not contract_id:
        _fail("plan.contractId", "hash requires contract id")

    budget = _dict(plan["budget"], "plan.budget")
    _exact(budget, ("perRunWallClockSeconds", "totalWallClockSeconds"), "plan.budget")
    per_run = _number(budget["perRunWallClockSeconds"], "plan.budget.perRunWallClockSeconds", positive=True)
    total = _number(budget["totalWallClockSeconds"], "plan.budget.totalWallClockSeconds", positive=True)

    quality = _dict(plan["quality"], "plan.quality")
    _exact(quality, ("metricId", "threshold", "referenceId", "aggregation"), "plan.quality")
    metric = _identifier(quality["metricId"], "plan.quality.metricId")
    threshold = _number(quality["threshold"], "plan.quality.threshold", nonnegative=True)
    reference = _identifier(quality["referenceId"], "plan.quality.referenceId")
    aggregation = _identifier(quality["aggregation"], "plan.quality.aggregation")

    artifacts = _list(plan["artifacts"], "plan.artifacts")
    names = []
    for index, name in enumerate(artifacts):
        name = _identifier(name, f"plan.artifacts[{index}]")
        if name in names:
            _fail(f"plan.artifacts[{index}]", "duplicate artifact")
        names.append(name)
    if not names or not {"identity.json", "summary.json"}.issubset(names):
        _fail("plan.artifacts", "identity.json and summary.json are required")

    runs = _list(plan["runs"], "plan.runs")
    if not runs:
        _fail("plan.runs", "must not be empty")
    run_ids, groups, normalized_runs = set(), {}, []
    for index, raw in enumerate(runs):
        context = f"plan.runs[{index}]"
        run = _dict(raw, context)
        _exact(run, _RUN_FIELDS, context)
        run_id = _identifier(run["runId"], context + ".runId")
        if run_id in run_ids:
            _fail(context + ".runId", "duplicates another run")
        run_ids.add(run_id)
        group_id = _identifier(run["groupId"], context + ".groupId")
        case_id = _identifier(run["caseId"], context + ".caseId")
        variant = _identifier(run["variant"], context + ".variant")
        run_index = _integer(run["runIndex"], context + ".runIndex", positive=True)
        repeats = _integer(run["plannedRepeatCount"], context + ".plannedRepeatCount", positive=True)
        warmup = _integer(run["warmupFrames"], context + ".warmupFrames", nonnegative=True)
        measure = _integer(run["measureFrames"], context + ".measureFrames", positive=True)
        capacity = _integer(run["sampleCapacity"], context + ".sampleCapacity", positive=True)
        if capacity < measure:
            _fail(context + ".sampleCapacity", "must cover measureFrames")
        if run_index > repeats:
            _fail(context + ".runIndex", "cannot exceed plannedRepeatCount")
        frame_budget = _number(run["frameBudgetMs"], context + ".frameBudgetMs", positive=True)
        timeout = _number(run["timeoutSeconds"], context + ".timeoutSeconds", positive=True)
        parameters = _dict(run["parameters"], context + ".parameters")
        digest = canonical_digest(parameters)
        group = groups.setdefault(group_id, {"caseId": case_id, "variant": variant, "repeats": repeats, "digest": digest, "indexes": []})
        if (group["caseId"], group["variant"], group["repeats"], group["digest"]) != (case_id, variant, repeats, digest):
            _fail(context + ".groupId", "group mixes run settings")
        if run_index in group["indexes"]:
            _fail(context + ".runIndex", "duplicates another index in group")
        group["indexes"].append(run_index)
        normalized_runs.append({"runId": run_id, "groupId": group_id, "caseId": case_id, "variant": variant,
                                "runIndex": run_index, "plannedRepeatCount": repeats, "warmupFrames": warmup,
                                "measureFrames": measure, "sampleCapacity": capacity, "frameBudgetMs": frame_budget,
                                "timeoutSeconds": timeout, "parameters": parameters})
    for group_id, group in groups.items():
        if sorted(group["indexes"]) != list(range(1, group["repeats"] + 1)):
            _fail("plan group " + group_id, "run indexes must be exactly 1..plannedRepeatCount")
    if total < sum(run["timeoutSeconds"] for run in normalized_runs):
        _fail("plan.budget.totalWallClockSeconds", "must cover all run timeouts")
    comparison = _comparison(plan["comparison"])
    if comparison and not {comparison["leftGroupId"], comparison["rightGroupId"]}.issubset(groups):
        _fail("plan.comparison", "comparison groups must exist")
    return {"schemaVersion": PLAN_SCHEMA, "status": status, "planId": plan["planId"], "experimentId": plan["experimentId"],
            "protocolVersion": PROTOCOL_VERSION, "contractId": contract_id, "contractSha256": contract_hash,
            "candidateId": plan["candidateId"], "buildId": plan["buildId"], "sourceRevision": plan["sourceRevision"],
            "dirty": plan["dirty"], "evidenceKind": evidence, "budget": {"perRunWallClockSeconds": per_run,
            "totalWallClockSeconds": total}, "quality": {"metricId": metric, "threshold": threshold,
            "referenceId": reference, "aggregation": aggregation}, "comparison": comparison, "artifacts": names,
            "runs": normalized_runs}


def plan_budget(plan):
    normalized = validate_plan(plan)
    minimum = sum(run["timeoutSeconds"] for run in normalized["runs"])
    declared = normalized["budget"]["totalWallClockSeconds"]
    return {"schemaVersion": PLAN_SCHEMA, "planId": normalized["planId"], "runCount": len(normalized["runs"]),
            "groupCount": len({run["groupId"] for run in normalized["runs"]}),
            "perRunWallClockSeconds": normalized["budget"]["perRunWallClockSeconds"],
            "declaredTotalWallClockSeconds": declared, "minimumTotalWallClockSeconds": minimum,
            "headroomSeconds": declared - minimum, "withinBudget": declared >= minimum}


_QUALITY_FIELDS = ("schemaVersion", "runId", "contractId", "contractSha256", "evidenceKind", "referenceId",
                   "metricId", "threshold", "aggregation", "colorSpace", "alphaMode", "samples")


def _rgba(value, context):
    values = _list(value, context)
    if len(values) != 4:
        _fail(context, "must contain four channels")
    output = []
    for index, item in enumerate(values):
        item = _number(item, f"{context}[{index}]")
        if not 0 <= item <= 1:
            _fail(f"{context}[{index}]", "must be within [0, 1]")
        output.append(item)
    return output


def validate_quality_document(value, plan=None):
    document = _dict(value, "quality")
    _exact(document, _QUALITY_FIELDS, "quality")
    if document["schemaVersion"] != QUALITY_SCHEMA:
        _fail("quality.schemaVersion", f"expected {QUALITY_SCHEMA}")
    run_id = _identifier(document["runId"], "quality.runId")
    contract_id = _identifier(document["contractId"], "quality.contractId", empty=True)
    contract_hash = document["contractSha256"]
    if contract_hash is not None and not _hash(contract_hash):
        _fail("quality.contractSha256", "must be null or SHA-256")
    evidence = _string(document["evidenceKind"], "quality.evidenceKind")
    if evidence not in ("fixture", "windows-development-player"):
        _fail("quality.evidenceKind", "unsupported evidence kind")
    reference = _identifier(document["referenceId"], "quality.referenceId")
    metric = _identifier(document["metricId"], "quality.metricId")
    threshold = _number(document["threshold"], "quality.threshold", nonnegative=True)
    aggregation = _identifier(document["aggregation"], "quality.aggregation")
    color_space = _string(document["colorSpace"], "quality.colorSpace")
    alpha_mode = _string(document["alphaMode"], "quality.alphaMode")
    samples = _list(document["samples"], "quality.samples")
    if not samples:
        _fail("quality.samples", "must not be empty")
    normalized_samples, previous_t = [], None
    for index, raw in enumerate(samples):
        context = f"quality.samples[{index}]"
        sample = _dict(raw, context)
        _exact(sample, ("t", "expectedRgba", "actualRgba"), context)
        t = _number(sample["t"], context + ".t", nonnegative=True)
        if t > 1 or (previous_t is not None and t <= previous_t):
            _fail(context + ".t", "must be strictly increasing in [0, 1]")
        previous_t = t
        normalized_samples.append({"t": t, "expectedRgba": _rgba(sample["expectedRgba"], context + ".expectedRgba"),
                                   "actualRgba": _rgba(sample["actualRgba"], context + ".actualRgba")})
    normalized = {"schemaVersion": QUALITY_SCHEMA, "runId": run_id, "contractId": contract_id,
                  "contractSha256": contract_hash, "evidenceKind": evidence, "referenceId": reference,
                  "metricId": metric, "threshold": threshold, "aggregation": aggregation, "colorSpace": color_space,
                  "alphaMode": alpha_mode, "samples": normalized_samples}
    if plan is not None:
        expected = validate_plan(plan)
        if run_id not in {run["runId"] for run in expected["runs"]}:
            _fail("quality.runId", "does not belong to plan")
        for field, actual, planned in (("evidenceKind", evidence, expected["evidenceKind"]),
                                       ("referenceId", reference, expected["quality"]["referenceId"]),
                                       ("metricId", metric, expected["quality"]["metricId"]),
                                       ("threshold", threshold, expected["quality"]["threshold"]),
                                       ("contractId", contract_id, expected["contractId"]),
                                       ("contractSha256", contract_hash, expected["contractSha256"])):
            if actual != planned:
                _fail("quality." + field, "does not match plan")
    return normalized

def quality_metrics(value, plan=None):
    document = validate_quality_document(value, plan)
    deltas = [abs(actual - expected) for sample in document["samples"]
              for expected, actual in zip(sample["expectedRgba"], sample["actualRgba"])]
    max_abs, mean_abs = max(deltas), sum(deltas) / len(deltas)
    rmse = math.sqrt(sum(delta * delta for delta in deltas) / len(deltas))
    available = {"rgba.max_abs": max_abs, "rgba.mean_abs": mean_abs, "rgba.rmse": rmse}
    selected = available.get(document["metricId"])
    ready = (plan is None or validate_plan(plan)["status"] == "frozen") and bool(document["contractId"]) and document["contractSha256"] is not None
    if not ready:
        status, reason = "not_ready", "frozen contract identity is required before quality can pass"
    elif selected is None:
        status, reason = "not_assessed", "quality metric is not implemented by this offline tool"
    elif selected <= document["threshold"]:
        status, reason = "pass", ""
    else:
        status, reason = "quality_limited", "selected quality metric exceeds threshold"
    return {"schemaVersion": QUALITY_SCHEMA, "runId": document["runId"], "contractId": document["contractId"],
            "contractSha256": document["contractSha256"], "evidenceKind": document["evidenceKind"],
            "referenceId": document["referenceId"], "metricId": document["metricId"], "threshold": document["threshold"],
            "colorSpace": document["colorSpace"], "alphaMode": document["alphaMode"], "sampleCount": len(document["samples"]),
            "maxAbsError": max_abs, "meanAbsError": mean_abs, "rmse": rmse, "selectedError": selected,
            "status": status, "reason": reason}


def _percentile(values, p):
    if not values:
        _fail("statistics", "cannot calculate an empty percentile")
    values = sorted(float(value) for value in values)
    position = (len(values) - 1) * p
    low, high = math.floor(position), math.ceil(position)
    return values[low] if low == high else values[low] + (values[high] - values[low]) * (position - low)


def _distribution(values):
    values = sorted(float(value) for value in values)
    median = _percentile(values, .5)
    return {"median": median, "minimum": values[0], "maximum": values[-1],
            "mad": _percentile([abs(value - median) for value in values], .5),
            "iqr": _percentile(values, .75) - _percentile(values, .25)}


_RESULT_FIELDS = ("schemaVersion", "planId", "contractId", "contractSha256", "evidenceKind", "runs")
_RESULT_RUN_FIELDS = ("runId", "groupId", "caseId", "variant", "runIndex", "plannedRepeatCount", "state",
                      "correctness", "measurementValidity", "qualityStatus", "failureCode", "failureReason", "metrics")

def _validate_result_document(value, plan):
    result = _dict(value, "results")
    _exact(result, _RESULT_FIELDS, "results")
    if result["schemaVersion"] != RESULTS_SCHEMA:
        _fail("results.schemaVersion", f"expected {RESULTS_SCHEMA}")
    for field in ("planId", "contractId", "contractSha256", "evidenceKind"):
        if result[field] != plan[field]:
            _fail("results." + field, "does not match plan")
    runs = _list(result["runs"], "results.runs")
    expected = {run["runId"]: run for run in plan["runs"]}
    if len(runs) != len(expected):
        _fail("results.runs", "must contain exactly every planned run")
    seen, normalized = set(), []
    for index, raw in enumerate(runs):
        context = f"results.runs[{index}]"
        item = _dict(raw, context)
        _exact(item, _RESULT_RUN_FIELDS, context)
        run_id = _identifier(item["runId"], context + ".runId")
        if run_id in seen:
            _fail(context + ".runId", "duplicate result")
        seen.add(run_id)
        planned = expected.get(run_id)
        if planned is None:
            _fail(context + ".runId", "not in plan")
        for field in ("groupId", "caseId", "variant", "runIndex", "plannedRepeatCount"):
            if item[field] != planned[field]:
                _fail(context + "." + field, "does not match plan")
        state = _string(item["state"], context + ".state")
        correctness = _string(item["correctness"], context + ".correctness")
        validity = _string(item["measurementValidity"], context + ".measurementValidity")
        quality = _string(item["qualityStatus"], context + ".qualityStatus")
        if state not in ("completed", "failed", "cancelled"):
            _fail(context + ".state", "unsupported state")
        if correctness not in ("pass", "fail", "not_run"):
            _fail(context + ".correctness", "unsupported value")
        if validity not in ("valid", "invalid", "not_assessed"):
            _fail(context + ".measurementValidity", "unsupported value")
        if quality not in ("pass", "quality_limited", "not_ready", "not_assessed", "fail"):
            _fail(context + ".qualityStatus", "unsupported value")
        _string(item["failureCode"], context + ".failureCode", empty=True)
        _string(item["failureReason"], context + ".failureReason", empty=True)
        metrics = _dict(item["metrics"], context + ".metrics")
        extra_metrics = set(metrics) - {"frameIntervalMs", "costMetrics"}
        if extra_metrics:
            _fail(context + ".metrics", "extra fields: " + ", ".join(sorted(extra_metrics)))
        if "frameIntervalMs" not in metrics:
            _fail(context + ".metrics", "frameIntervalMs is required")
        frame = _list(metrics["frameIntervalMs"], context + ".metrics.frameIntervalMs")
        if not frame:
            _fail(context + ".metrics.frameIntervalMs", "must not be empty")
        frame = [_number(value, context + ".metrics.frameIntervalMs") for value in frame]
        costs = _dict(metrics.get("costMetrics", {}), context + ".metrics.costMetrics")
        normalized_cost = {}
        for name, values in costs.items():
            _identifier(name, context + ".metrics.costMetrics key")
            values = values if isinstance(values, list) else [values]
            if not values:
                _fail(context + ".metrics.costMetrics." + name, "must not be empty")
            normalized_cost[name] = [_number(value, context + ".metrics.costMetrics." + name) for value in values]
        normalized.append({"runId": run_id, "groupId": item["groupId"], "caseId": item["caseId"], "variant": item["variant"],
                           "runIndex": item["runIndex"], "plannedRepeatCount": item["plannedRepeatCount"], "state": state,
                           "correctness": correctness, "measurementValidity": validity, "qualityStatus": quality,
                           "failureCode": item["failureCode"], "failureReason": item["failureReason"],
                           "metrics": {"frameIntervalMs": frame, "costMetrics": normalized_cost},
                           "frameBudgetMs": planned["frameBudgetMs"]})
    if seen != set(expected):
        _fail("results.runs", "missing planned run")
    return {"schemaVersion": RESULTS_SCHEMA, "planId": plan["planId"], "contractId": plan["contractId"],
            "contractSha256": plan["contractSha256"], "evidenceKind": plan["evidenceKind"], "runs": normalized}


def validate_results_document(value, plan):
    return _validate_result_document(value, validate_plan(plan))


def _run_stats(run):
    values = run["metrics"]["frameIntervalMs"]
    budget = run["frameBudgetMs"]
    costs = {}
    for name, data in run["metrics"]["costMetrics"].items():
        costs[name] = {"median": _percentile(data, .5), "mean": sum(data) / len(data), "maximum": max(data)}
    return {"sampleCount": len(values), "p50": _percentile(values, .5), "p95": _percentile(values, .95),
            "p99": _percentile(values, .99), "maximum": max(values),
            "overBudgetRatio": sum(value > budget for value in values) / len(values),
            "costMetrics": costs,
            "costMetricsAvailability": "available" if costs else "unavailable",
            "costMetricsReason": "" if costs else "no optional cost metric supplied"}


def run_statistics(run):
    return _run_stats(run)

def _metric(group, metric):
    frame = group["metrics"]["frameIntervalMs"]
    if metric.startswith("frameIntervalMs."):
        return frame.get(metric.split(".", 1)[1])
    if metric.startswith("cost.") and metric.endswith(".median"):
        return group["metrics"]["costMetrics"].get(metric[5:-7])
    return None


def _compare(plan, groups):
    rule = plan["comparison"]
    if rule is None:
        return {"status": "not_assessed", "reason": "plan has no comparison rule"}
    left, right = groups.get(rule["leftGroupId"]), groups.get(rule["rightGroupId"])
    if left is None or right is None:
        return {"status": "not_assessed", "reason": "comparison group failed the gate"}
    left_stat, right_stat = _metric(left, rule["metricId"]), _metric(right, rule["metricId"])
    if left_stat is None or right_stat is None:
        return {"status": "not_assessed", "reason": "comparison metric is absent"}
    disjoint = left_stat["minimum"] > right_stat["maximum"] or right_stat["minimum"] > left_stat["maximum"]
    robust = abs(left_stat["median"] - right_stat["median"]) > left_stat["mad"] + right_stat["mad"]
    if not disjoint or not robust:
        status = "inconclusive"
    else:
        right_better = right_stat["median"] < left_stat["median"] if rule["lowerIsBetter"] else right_stat["median"] > left_stat["median"]
        status = "improved" if right_better else "regressed"
    return {"status": status, "rule": rule["rule"], "metricId": rule["metricId"],
            "leftGroupId": rule["leftGroupId"], "rightGroupId": rule["rightGroupId"],
            "left": left_stat, "right": right_stat}


def analyze_results(plan_value, results_value):
    plan = validate_plan(plan_value)
    ready = plan["status"] == "frozen" and plan["contractSha256"] is not None
    try:
        results = _validate_result_document(results_value, plan)
    except GradientToolError as exc:
        return {"schemaVersion": ANALYSIS_SCHEMA, "planId": plan["planId"], "contractId": plan["contractId"],
                "contractSha256": plan["contractSha256"], "evidenceKind": plan["evidenceKind"],
                "status": "not_ready" if not ready else "invalid", "reason": str(exc),
                "groups": [], "comparisons": [], "runs": [], "executionEvidence": "not_assessed"}
    expected_groups = {}
    for run in plan["runs"]:
        expected_groups.setdefault(run["groupId"], []).append(run)
    observed, diagnostics = {}, []
    for run in results["runs"]:
        stats = _run_stats(run)
        runtime_ok = run["state"] == "completed" and run["correctness"] == "pass" and run["measurementValidity"] == "valid"
        quality_ok = run["qualityStatus"] == "pass"
        accepted = ready and runtime_ok and quality_ok
        reason = "" if accepted else ("frozen contract identity is required" if not ready else "state, correctness, validity, and quality must pass")
        diagnostics.append({"runId": run["runId"], "groupId": run["groupId"], "runIndex": run["runIndex"],
                            "accepted": accepted, "reason": reason, "state": run["state"],
                            "correctness": run["correctness"], "measurementValidity": run["measurementValidity"],
                            "qualityStatus": run["qualityStatus"], "failureCode": run["failureCode"],
                            "failureReason": run["failureReason"], "statistics": stats})
        observed.setdefault(run["groupId"], []).append((run, stats, accepted))

    groups, valid = [], {}
    for group_id in sorted(expected_groups):
        expected_runs, actual = expected_groups[group_id], observed.get(group_id, [])
        if not actual:
            groups.append({"groupId": group_id, "caseId": expected_runs[0]["caseId"], "variant": expected_runs[0]["variant"],
                           "runCount": 0, "plannedRepeatCount": expected_runs[0]["plannedRepeatCount"],
                           "runIndexes": [], "gate": "invalid",
                           "metrics": {"frameIntervalMs": {}, "costMetrics": {},
                                       "availability": {"costMetrics": "unavailable",
                                                        "costMetricsReason": "group has no accepted runs"}}})
            continue
        complete = len(actual) == len(expected_runs) and sorted(item[0]["runIndex"] for item in actual) == list(range(1, len(expected_runs) + 1))
        group_ok = complete and all(item[2] for item in actual)
        frame = {key: _distribution([item[1][key] for item in actual]) for key in ("p50", "p95", "p99", "maximum", "overBudgetRatio")}
        costs = {}
        for name in sorted({name for item in actual for name in item[1]["costMetrics"]}):
            if all(name in item[1]["costMetrics"] for item in actual):
                costs[name] = _distribution([item[1]["costMetrics"][name]["median"] for item in actual])
        cost_available = bool(actual) and all(item[1]["costMetrics"] for item in actual)
        cost_reason = "" if cost_available else ("missing from one or more runs" if any(item[1]["costMetrics"] for item in actual) else "no optional cost metric supplied")
        output = {"groupId": group_id, "caseId": expected_runs[0]["caseId"], "variant": expected_runs[0]["variant"],
                  "runCount": len(actual), "plannedRepeatCount": expected_runs[0]["plannedRepeatCount"],
                  "runIndexes": sorted(item[0]["runIndex"] for item in actual),
                  "gate": "pass" if group_ok else ("not_ready" if not ready else "invalid"),
                  "metrics": {"frameIntervalMs": frame, "costMetrics": costs,
                              "availability": {"costMetrics": "available" if cost_available else "unavailable",
                                               "costMetricsReason": cost_reason}}}
        groups.append(output)
        if group_ok:
            valid[group_id] = output
    all_complete = bool(groups) and all(group["runCount"] == group["plannedRepeatCount"] for group in groups)
    all_valid = all_complete and len(valid) == len(groups)
    status = "pass" if ready and all_valid else ("not_ready" if not ready else "invalid")
    return {"schemaVersion": ANALYSIS_SCHEMA, "planId": plan["planId"], "contractId": plan["contractId"],
            "contractSha256": plan["contractSha256"], "evidenceKind": plan["evidenceKind"], "status": status,
            "reason": "" if status == "pass" else "identity, quality, or complete-repeat gate did not pass",
            "groups": groups, "comparisons": [_compare(plan, valid)] if status == "pass" else [], "runs": diagnostics,
            "executionEvidence": "not_assessed"}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--plan", type=pathlib.Path, required=True)
    parser.add_argument("--quality", type=pathlib.Path)
    parser.add_argument("--results", type=pathlib.Path)
    parser.add_argument("--require-frozen", action="store_true")
    args = parser.parse_args(argv)
    try:
        plan = validate_plan(read_json(args.plan), args.require_frozen)
        output = {"plan": plan, "budget": plan_budget(plan)}
        if args.quality:
            output["quality"] = quality_metrics(read_json(args.quality), plan)
        if args.results:
            output["analysis"] = analyze_results(plan, read_json(args.results))
        print(json.dumps(output, ensure_ascii=False, indent=2, allow_nan=False))
        return 0
    except (GradientToolError, OSError, ValueError, TypeError) as exc:
        print("GRADIENT TOOL FAILED: " + str(exc), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
