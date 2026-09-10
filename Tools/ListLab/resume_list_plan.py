"""Inspect and conservatively resume a frozen List Lab run plan.

The original ``run_list_matrix.py`` launcher creates a manifest and then runs
each listed Player serially.  This module is deliberately a separate tool so
that an interrupted launcher can be inspected and continued without changing
the frozen manifest or silently replacing evidence.  Inspection is read-only;
execution requires ``--execute`` and an explicitly supplied Player.

The module uses the strict List Lab verifier as the source of truth for a raw
run.  A run is complete only when its nine raw artifacts validate and its
outside receipt names the same artifact-set hash.  A valid orchestration
failure sidecar is a durable failed state.  Everything else that has remnants
is blocked as interrupted/invalid.
"""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import math
import os
import pathlib
import re
import stat
import subprocess
import sys
import time
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence, Tuple

import verify_list_runs as verifier


PLAN_NAMES = tuple(verifier.PLAN_NAMES)
LOCK_SUFFIX = ".resume.lock"
INTENT_SUFFIX = "-resume-intent.json"
RECEIPT_SUFFIX = "-receipt.json"
FAILURE_SUFFIX = "-orchestration-failure.json"
PLAYER_LOG_SUFFIX = "-player.log"
HASH_RE = re.compile(r"^[0-9A-Fa-f]{64}$")
IDENTIFIER_RE = re.compile(r"^[^<>:\"/\\|?*\x00-\x1f]+$")
MANIFEST_NAME_RE = re.compile(
    r"^(?P<series>.+)-(?P<plan>matrix|pilot|stress)-manifest\.json$"
)


class ResumeError(Exception):
    """A conservative resume refusal or a durable child-run failure."""


def _fail(message: str) -> None:
    raise ResumeError(message)


def _is_number(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(float(value))


def _normal_path(value: pathlib.Path | str) -> str:
    return os.path.normcase(os.path.abspath(os.path.normpath(str(value))))


def _same_path(left: pathlib.Path | str, right: pathlib.Path | str) -> bool:
    return _normal_path(left) == _normal_path(right)


def _assert_path(path: pathlib.Path, context: str) -> None:
    """Use the verifier's symlink/junction/reparse-point guard."""
    try:
        verifier._assert_no_reparse_components(path, context)
    except verifier.VerificationError as exc:
        _fail(str(exc))


def _lexists(path: pathlib.Path) -> bool:
    return os.path.lexists(str(path))


def _assert_regular_file(path: pathlib.Path, context: str) -> None:
    _assert_path(path, context)
    try:
        info = os.lstat(str(path))
    except FileNotFoundError:
        _fail("{}: file is missing".format(context))
    except OSError as exc:
        _fail("{}: cannot inspect file ({})".format(context, exc))
    if stat.S_ISLNK(info.st_mode) or (getattr(info, "st_file_attributes", 0) & verifier.REPARSE_POINT_ATTRIBUTE):
        _fail("{}: file is a symlink, junction or reparse point".format(context))
    if not stat.S_ISREG(info.st_mode):
        _fail("{}: file is not regular".format(context))


def _read_json(path: pathlib.Path, context: str) -> Any:
    _assert_regular_file(path, context)
    try:
        return verifier._read_json(path)
    except verifier.VerificationError as exc:
        _fail(str(exc))
    except (OSError, UnicodeError, ValueError, TypeError) as exc:
        _fail("{}: cannot read JSON ({})".format(context, exc))


def _write_json_new(path: pathlib.Path, value: Mapping[str, Any], context: str) -> None:
    """Create one durable JSON sidecar and never replace an existing file."""
    _assert_path(path, context)
    payload = json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + "\n"
    try:
        descriptor = os.open(
            str(path),
            os.O_WRONLY | os.O_CREAT | os.O_EXCL,
            0o600,
        )
    except FileExistsError:
        _fail("{}: refusing to overwrite existing file".format(context))
    except OSError as exc:
        _fail("{}: cannot create file ({})".format(context, exc))
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8", newline="") as stream:
            stream.write(payload)
            stream.flush()
            os.fsync(stream.fileno())
    except Exception:
        try:
            path.unlink()
        except OSError:
            pass
        raise


def _remove_owned(path: pathlib.Path, context: str) -> None:
    """Remove only our intent marker after its successor is durable."""
    try:
        _assert_regular_file(path, context)
        path.unlink()
    except ResumeError:
        raise
    except OSError as exc:
        _fail("{}: cannot remove marker ({})".format(context, exc))


def _manifest_and_plan(
    manifest_path: pathlib.Path,
    requested_plan: Optional[str],
) -> Tuple[Dict[str, Any], str]:
    _assert_regular_file(manifest_path, "manifest")
    try:
        manifest = verifier._load_manifest(manifest_path)
    except verifier.VerificationError as exc:
        _fail(str(exc))
    plan_from_name: Optional[str] = None
    match = MANIFEST_NAME_RE.fullmatch(manifest_path.name)
    if match:
        plan_from_name = match.group("plan")
    plan = requested_plan or plan_from_name
    if plan is None:
        try:
            plan = verifier._infer_plan(manifest)
        except verifier.VerificationError:
            _fail("cannot derive plan from manifest; pass --plan explicitly")
    if plan not in PLAN_NAMES:
        _fail("unsupported plan {!r}".format(plan))
    if plan_from_name is not None and requested_plan is not None and requested_plan != plan_from_name:
        _fail("requested plan does not match manifest filename")
    try:
        verifier._validate_plan_manifest(manifest, plan)
    except verifier.VerificationError as exc:
        _fail(str(exc))
    return manifest, plan


def _valid_identifier(value: Any, context: str) -> str:
    if not isinstance(value, str) or not value or not IDENTIFIER_RE.fullmatch(value):
        _fail("{}: must be a non-empty safe identifier".format(context))
    return value


def _derive_series_id(
    manifest_path: pathlib.Path,
    root: pathlib.Path,
    manifest: Mapping[str, Any],
    explicit: Optional[str],
) -> str:
    match = MANIFEST_NAME_RE.fullmatch(manifest_path.name)
    if match:
        # The launcher passes ``stamp + '-' + plan`` as seriesId.  Keep the
        # complete frozen filename stem so a stamp that itself contains a
        # plan-looking suffix is not shortened or duplicated.
        derived = _valid_identifier(manifest_path.name[: -len("-manifest.json")], "manifest series id")
        if explicit is not None and explicit != derived:
            _fail("explicit series id conflicts with manifest filename")
        return derived

    # A generic manifest filename is accepted only when an existing config
    # supplies one unambiguous identity.  We never invent a historic value.
    values = set()
    for spec in manifest["runs"]:
        config_path = root / spec["runId"] / "config.json"
        if not _lexists(config_path):
            continue
        raw = _read_json(config_path, spec["runId"] + "/config.json")
        if not isinstance(raw, dict) or not isinstance(raw.get("seriesId"), str) or not raw["seriesId"]:
            _fail("{}: seriesId is missing or invalid".format(config_path))
        values.add(raw["seriesId"])
    if len(values) == 1:
        derived = _valid_identifier(next(iter(values)), "config series id")
        if explicit is not None and explicit != derived:
            _fail("explicit series id conflicts with existing config")
        return derived
    if values:
        _fail("existing configs have conflicting series identities")
    if explicit is not None:
        return _valid_identifier(explicit, "series id")
    _fail("cannot derive series id from manifest filename or existing config; pass --series-id explicitly")


def _validate_series_id(root: pathlib.Path, spec: Mapping[str, Any], series_id: str) -> None:
    config_path = root / spec["runId"] / "config.json"
    if not _lexists(config_path):
        return
    raw = _read_json(config_path, spec["runId"] + "/config.json")
    if not isinstance(raw, dict) or not isinstance(raw.get("seriesId"), str) or not raw["seriesId"]:
        _fail("{}: seriesId is missing or invalid".format(spec["runId"]))
    if raw["seriesId"] != series_id:
        _fail("{}: config seriesId {!r} differs from frozen {!r}".format(spec["runId"], raw["seriesId"], series_id))


def _effective_recorded_root(
    root: pathlib.Path,
    spec: Mapping[str, Any],
    recorded_root: Optional[str],
) -> Optional[str]:
    """Select an explicit mapping for one run in a relocated mixed-root plan."""
    config_path = root / spec["runId"] / "config.json"
    if not _lexists(config_path):
        return recorded_root
    raw = _read_json(config_path, spec["runId"] + "/config.json")
    if not isinstance(raw, dict) or not isinstance(raw.get("outputDirectory"), str) or not raw["outputDirectory"]:
        _fail("{}: config outputDirectory is missing or invalid".format(spec["runId"]))
    output = raw["outputDirectory"]
    if _same_path(output, root):
        return None
    if recorded_root is not None and _same_path(output, recorded_root):
        return recorded_root
    _fail(
        "{}: outputDirectory {!r} is neither physical root nor explicit recorded root".format(
            spec["runId"], output
        )
    )


def _run_side_paths(root: pathlib.Path, run_id: str) -> Dict[str, pathlib.Path]:
    return {
        "run": root / run_id,
        "receipt": root / (run_id + RECEIPT_SUFFIX),
        "failure": root / (run_id + FAILURE_SUFFIX),
        "intent": root / (run_id + INTENT_SUFFIX),
        "log": root / (run_id + PLAYER_LOG_SUFFIX),
    }


def _all_failure_paths(root: pathlib.Path, run_id: str) -> List[pathlib.Path]:
    paths: List[pathlib.Path] = []
    prefix = run_id + "-"
    try:
        entries = list(os.scandir(str(root)))
    except OSError as exc:
        _fail("root: cannot enumerate plan files ({})".format(exc))
    for entry in entries:
        if not entry.name.startswith(prefix) or not entry.name.endswith(FAILURE_SUFFIX):
            continue
        path = root / entry.name
        _assert_path(path, "failure sidecar")
        paths.append(path)
    return sorted(paths, key=lambda item: item.name)


def _parse_receipt(path: pathlib.Path, run_id: str, artifact_hash: str) -> Tuple[bool, str]:
    if not _lexists(path):
        return False, "receipt is missing"
    try:
        value = _read_json(path, run_id + "/receipt")
    except ResumeError as exc:
        return False, str(exc)
    if not isinstance(value, dict):
        return False, "receipt is not an object"
    expected = {"runId", "pid", "exitCode", "durationSeconds", "completedUtc", "artifactSetSha256"}
    if not expected.issubset(value):
        return False, "receipt is missing launcher contract fields"
    if value.get("runId") != run_id:
        return False, "receipt runId does not match"
    if isinstance(value.get("pid"), bool) or not isinstance(value.get("pid"), int) or value["pid"] <= 0:
        return False, "receipt pid is invalid"
    if isinstance(value.get("exitCode"), bool) or value.get("exitCode") != 0:
        return False, "receipt exitCode is not zero"
    if not _is_number(value.get("durationSeconds")) or float(value["durationSeconds"]) < 0:
        return False, "receipt durationSeconds is invalid"
    if not isinstance(value.get("completedUtc"), str) or not value["completedUtc"]:
        return False, "receipt completedUtc is invalid"
    if not isinstance(value.get("artifactSetSha256"), str) or not HASH_RE.fullmatch(value["artifactSetSha256"]):
        return False, "receipt artifactSetSha256 is invalid"
    if value["artifactSetSha256"].upper() != artifact_hash.upper():
        return False, "receipt artifactSetSha256 does not match raw artifacts"
    return True, "receipt matches raw artifacts"


def _parse_failure(path: pathlib.Path, run_id: str) -> Tuple[bool, str]:
    try:
        value = _read_json(path, run_id + "/failure sidecar")
    except ResumeError as exc:
        return False, str(exc)
    if not isinstance(value, dict):
        return False, "failure sidecar is not an object"
    expected = {"runId", "pid", "timeout", "exitCode", "reason", "durationSeconds"}
    if not expected.issubset(value):
        return False, "failure sidecar is missing launcher contract fields"
    if value.get("runId") != run_id:
        return False, "failure sidecar runId does not match"
    pid = value.get("pid")
    if pid is not None and (isinstance(pid, bool) or not isinstance(pid, int) or pid <= 0):
        return False, "failure sidecar pid is invalid"
    if not isinstance(value.get("timeout"), bool):
        return False, "failure sidecar timeout is invalid"
    exit_code = value.get("exitCode")
    if exit_code is not None and (isinstance(exit_code, bool) or not isinstance(exit_code, int)):
        return False, "failure sidecar exitCode is invalid"
    if not isinstance(value.get("reason"), str) or not value["reason"].strip():
        return False, "failure sidecar reason is empty"
    if not _is_number(value.get("durationSeconds")) or float(value["durationSeconds"]) < 0:
        return False, "failure sidecar durationSeconds is invalid"
    return True, "valid failure sidecar"


def classify_run(
    root: pathlib.Path,
    spec: Mapping[str, Any],
    manifest: Mapping[str, Any],
    series_id: str,
    recorded_root: Optional[str] = None,
) -> Dict[str, Any]:
    """Return one of completed, failed, pending, interrupted, or invalid."""
    run_id = spec["runId"]
    paths = _run_side_paths(root, run_id)
    for name, path in paths.items():
        if _lexists(path):
            _assert_path(path, run_id + "/" + name)

    failure_paths = _all_failure_paths(root, run_id)
    known_names = {p.name for p in paths.values()} | {p.name for p in failure_paths}
    unknown = sorted(entry.name for entry in root.iterdir()
                     if entry.name.startswith(run_id + "-") and entry.name not in known_names)
    if unknown:
        return {"runId": run_id, "status": "invalid",
                "reason": "unknown run-prefixed remnants require operator inspection: " + ", ".join(unknown)}
    intent_exists = _lexists(paths["intent"])
    run_exists = _lexists(paths["run"])
    receipt_exists = _lexists(paths["receipt"])
    log_exists = _lexists(paths["log"])
    any_remnant = run_exists or receipt_exists or bool(failure_paths) or intent_exists or log_exists

    if intent_exists:
        return {
            "runId": run_id,
            "status": "interrupted",
            "reason": "durable resume intent remains; operator evidence is required",
        }

    raw_record: Optional[Dict[str, Any]] = None
    raw_error: Optional[str] = None
    if run_exists:
        try:
            _validate_series_id(root, spec, series_id)
            result = verifier._validate_run(
                root, spec, manifest,
                recorded_root=_effective_recorded_root(root, spec, recorded_root),
            )
            raw_record = result["record"]
        except Exception as exc:
            raw_error = str(exc)

    if raw_record is not None:
        receipt_ok, receipt_reason = _parse_receipt(paths["receipt"], run_id, raw_record["artifactSetSha256"])
        if receipt_ok:
            if failure_paths:
                return {
                    "runId": run_id,
                    "status": "invalid",
                    "reason": "receipt and failure sidecar conflict; operator evidence is required",
                }
            return {
                "runId": run_id,
                "status": "completed",
                "reason": receipt_reason,
                "record": raw_record,
            }
        return {
            "runId": run_id,
            "status": "invalid",
            "reason": "raw artifacts validate but {}".format(receipt_reason),
        }

    failure_reasons: List[str] = []
    invalid_failure = False
    for failure_path in failure_paths:
        valid, reason = _parse_failure(failure_path, run_id)
        if not valid:
            invalid_failure = True
            failure_reasons.append("{}: {}".format(failure_path.name, reason))
    if invalid_failure:
        return {
            "runId": run_id,
            "status": "invalid",
            "reason": "; ".join(failure_reasons),
        }
    if failure_paths:
        if receipt_exists:
            return {
                "runId": run_id,
                "status": "invalid",
                "reason": "receipt and failure sidecar conflict; operator evidence is required",
            }
        return {
            "runId": run_id,
            "status": "failed",
            "reason": "valid failure sidecar(s): {}".format(", ".join(path.name for path in failure_paths)),
        }

    if any_remnant:
        return {
            "runId": run_id,
            "status": "invalid",
            "reason": raw_error or "artifacts are incomplete and no valid completion/failure evidence exists",
        }
    return {"runId": run_id, "status": "pending", "reason": "no run artifacts or sidecars exist"}


def _find_hash_file(root: pathlib.Path, manifest_path: pathlib.Path, explicit: Optional[pathlib.Path]) -> pathlib.Path:
    if explicit is not None:
        return explicit
    name = manifest_path.name
    if name.endswith("-manifest.json"):
        candidate = root / (name[: -len("-manifest.json")] + "-build-hashes.json")
        if _lexists(candidate):
            return candidate
    _fail("build-hashes JSON is missing; pass --build-hashes explicitly")


def _sha256_file(path: pathlib.Path, context: str) -> str:
    _assert_regular_file(path, context)
    digest = hashlib.sha256()
    try:
        with path.open("rb") as stream:
            for block in iter(lambda: stream.read(1024 * 1024), b""):
                digest.update(block)
    except OSError as exc:
        _fail("{}: cannot hash file ({})".format(context, exc))
    return digest.hexdigest().upper()


def _assert_frozen_inputs(
    manifest_path: pathlib.Path,
    hashes_path: pathlib.Path,
    manifest_hash: str,
    hashes_file_hash: str,
) -> None:
    """Refuse to launch when either frozen input changed after inspection."""
    if _sha256_file(manifest_path, "manifest") != manifest_hash:
        _fail("manifest changed after plan freeze")
    if _sha256_file(hashes_path, "build hashes") != hashes_file_hash:
        _fail("build-hashes JSON changed after plan freeze")


def _load_hashes(path: pathlib.Path) -> Dict[str, str]:
    value = _read_json(path, "build hashes")
    if not isinstance(value, dict) or not value:
        _fail("build hashes: expected a non-empty object")
    result: Dict[str, str] = {}
    for raw_path, raw_hash in value.items():
        if not isinstance(raw_path, str) or not raw_path:
            _fail("build hashes: every path key must be a non-empty string")
        if not isinstance(raw_hash, str) or not HASH_RE.fullmatch(raw_hash):
            _fail("build hashes: invalid SHA-256 for {!r}".format(raw_path))
        result[raw_path] = raw_hash.upper()
    return result


def _absolute_existing(path: pathlib.Path, context: str) -> pathlib.Path:
    _assert_path(path, context)
    try:
        resolved = path.resolve(strict=True)
    except OSError as exc:
        _fail("{}: path is missing ({})".format(context, exc))
    _assert_path(resolved, context)
    return resolved


def _relative_under(path: pathlib.Path, root: pathlib.Path) -> Optional[pathlib.Path]:
    try:
        path_text = _normal_path(path)
        root_text = _normal_path(root)
        common = os.path.commonpath([path_text, root_text])
    except ValueError:
        return None
    if common != root_text:
        return None
    return pathlib.Path(path_text).relative_to(pathlib.Path(root_text))


def _mapped_hash_paths(
    hashes: Mapping[str, str],
    player: pathlib.Path,
    build_root: Optional[pathlib.Path],
    recorded_build_root: Optional[pathlib.Path],
) -> Dict[pathlib.Path, str]:
    player = _absolute_existing(player, "player")
    if recorded_build_root is not None and build_root is None:
        _fail("--recorded-build-root requires --build-root")
    if build_root is not None:
        _assert_path(build_root, "build root")
        build_root = pathlib.Path(os.path.abspath(os.path.normpath(str(build_root))))
    if recorded_build_root is not None:
        recorded_build_root = pathlib.Path(os.path.abspath(os.path.normpath(str(recorded_build_root))))
        _assert_path(recorded_build_root, "recorded build root")

    mapped: Dict[pathlib.Path, str] = {}
    for raw_name, expected in hashes.items():
        raw_path = pathlib.Path(raw_name)
        if raw_path.is_absolute():
            if recorded_build_root is not None:
                relative = _relative_under(raw_path, recorded_build_root)
                if relative is None:
                    _fail("build hash path {} is outside --recorded-build-root".format(raw_name))
                current = build_root / relative  # type: ignore[operator]
            else:
                current = raw_path
        else:
            base = build_root or player.parent
            current = base / raw_path
            if _relative_under(current, base) is None:
                _fail("relative build hash path {} escapes its build root".format(raw_name))
        # Match the Player's canonical identity, including Windows 8.3 aliases.
        # Guard both spellings against reparse points before/after resolution.
        current = _absolute_existing(current, "pinned build file")
        if current in mapped and mapped[current] != expected:
            _fail("build hashes map two different hashes to {}".format(current))
        mapped[current] = expected
    if player not in mapped:
        _fail("--player is not one of the pinned build files")
    return mapped


def verify_build_hashes(
    hashes_path: pathlib.Path,
    player: pathlib.Path,
    build_root: Optional[pathlib.Path] = None,
    recorded_build_root: Optional[pathlib.Path] = None,
    expected_hashes_file_sha256: Optional[str] = None,
) -> Dict[str, str]:
    """Verify every pinned file and return the current path/hash map."""
    if expected_hashes_file_sha256 is not None:
        current_hashes_file_sha256 = _sha256_file(hashes_path, "build hashes")
        if current_hashes_file_sha256 != expected_hashes_file_sha256.upper():
            _fail("build-hashes JSON changed after plan freeze")
    hashes = _load_hashes(hashes_path)
    mapped = _mapped_hash_paths(hashes, player, build_root, recorded_build_root)
    actual: Dict[str, str] = {}
    for path, expected in sorted(mapped.items(), key=lambda item: _normal_path(item[0])):
        try:
            digest = hashlib.sha256(path.read_bytes()).hexdigest().upper()
        except OSError as exc:
            _fail("cannot hash pinned build file {} ({})".format(path, exc))
        if digest != expected:
            _fail("build changed after plan freeze: {}".format(path))
        actual[str(path)] = digest
    if expected_hashes_file_sha256 is not None and _sha256_file(hashes_path, "build hashes") != expected_hashes_file_sha256.upper():
        _fail("build-hashes JSON changed while verifying pinned files")
    return actual


def _lock_path(root: pathlib.Path, manifest_path: pathlib.Path) -> pathlib.Path:
    return root / (manifest_path.name + LOCK_SUFFIX)


class PlanLock:
    def __init__(self, path: pathlib.Path):
        self.path = path
        self.token = "{}-{}".format(os.getpid(), time.time_ns())
        self.held = False

    def acquire(self) -> None:
        _assert_path(self.path, "plan lock")
        payload = json.dumps(
            {"schemaVersion": "xuilab.list.resume-lock/v1", "pid": os.getpid(), "token": self.token,
             "createdUtc": dt.datetime.now(dt.timezone.utc).isoformat()},
            ensure_ascii=False,
            sort_keys=True,
        ).encode("utf-8") + b"\n"
        try:
            descriptor = os.open(str(self.path), os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        except FileExistsError:
            _fail("plan lock already exists; operator evidence is required before removing it: {}".format(self.path))
        except OSError as exc:
            _fail("cannot create plan lock {} ({})".format(self.path, exc))
        try:
            with os.fdopen(descriptor, "wb") as stream:
                stream.write(payload)
                stream.flush()
                os.fsync(stream.fileno())
            self.held = True
        except Exception:
            try:
                self.path.unlink()
            except OSError:
                pass
            raise

    def release(self) -> None:
        if not self.held:
            return
        try:
            _assert_regular_file(self.path, "plan lock")
            current = json.loads(self.path.read_text(encoding="utf-8"))
            if not isinstance(current, dict) or current.get("token") != self.token:
                _fail("plan lock changed while held; refusing to remove it")
            self.path.unlink()
            self.held = False
        except ResumeError:
            raise
        except OSError as exc:
            _fail("cannot release plan lock ({})".format(exc))


def _plan_summary(
    manifest_path: pathlib.Path,
    root: pathlib.Path,
    requested_plan: Optional[str] = None,
    recorded_root: Optional[str] = None,
    series_id: Optional[str] = None,
    build_hashes_path: Optional[pathlib.Path] = None,
) -> Dict[str, Any]:
    _assert_path(root, "artifact root")
    if not root.is_dir():
        _fail("artifact root is not a directory: {}".format(root))
    manifest, plan = _manifest_and_plan(manifest_path, requested_plan)
    frozen_series = _derive_series_id(manifest_path, root, manifest, series_id)
    runs = [classify_run(root, spec, manifest, frozen_series, recorded_root=recorded_root) for spec in manifest["runs"]]
    counts: Dict[str, int] = {}
    for item in runs:
        counts[item["status"]] = counts.get(item["status"], 0) + 1
    hashes_status: Dict[str, Any]
    try:
        hash_path = _find_hash_file(root, manifest_path, build_hashes_path)
        _assert_regular_file(hash_path, "build hashes")
        _load_hashes(hash_path)
        hashes_status = {
            "status": "schema_valid_binaries_not_checked",
            "path": str(hash_path),
        }
    except ResumeError as exc:
        hashes_status = {"status": "invalid_or_missing", "reason": str(exc)}
    return {
        "manifest": str(manifest_path),
        "root": str(root),
        "plan": plan,
        "seriesId": frozen_series,
        "candidateId": manifest["candidateId"],
        "buildId": manifest["buildId"],
        "sourceRevision": manifest["sourceRevision"],
        "runs": runs,
        "counts": counts,
        "buildHashes": hashes_status,
        "relocation": {
            "recordedRoot": recorded_root,
            "physicalRoot": str(root),
            "mixedRoots": recorded_root is not None and not _same_path(root, recorded_root),
            "aggregateStatus": (
                "not_aggregated_mixed_roots"
                if recorded_root is not None and not _same_path(root, recorded_root)
                else "not_run"
            ),
        },
        "lock": {"path": str(_lock_path(root, manifest_path)), "exists": _lexists(_lock_path(root, manifest_path))},
    }


def inspect_plan(
    root: pathlib.Path,
    manifest_path: pathlib.Path,
    plan: Optional[str] = None,
    recorded_root: Optional[str] = None,
    series_id: Optional[str] = None,
    build_hashes_path: Optional[pathlib.Path] = None,
) -> Dict[str, Any]:
    """Inspect without creating a lock or changing any plan file."""
    return _plan_summary(
        pathlib.Path(manifest_path), pathlib.Path(root), plan,
        recorded_root=recorded_root, series_id=series_id,
        build_hashes_path=build_hashes_path,
    )


def _failure_sidecar_path(root: pathlib.Path, run_id: str, attempt: str) -> pathlib.Path:
    canonical = root / (run_id + FAILURE_SUFFIX)
    if not _lexists(canonical):
        return canonical
    return root / (run_id + "-resume-" + attempt + FAILURE_SUFFIX)


def _player_command(
    player: pathlib.Path,
    root: pathlib.Path,
    spec: Mapping[str, Any],
    manifest: Mapping[str, Any],
    series_id: str,
    log_path: pathlib.Path,
) -> List[str]:
    return [
        str(player), "-screen-fullscreen", "0", "-screen-width", "960", "-screen-height", "540", "-force-d3d11",
        "-logFile", str(log_path), "--xuilab-run", "--xuilab-quit", "--xuilab-output-root", str(root),
        "--xuilab-run-id", spec["runId"], "--xuilab-case", spec["caseId"], "--xuilab-series-id", series_id,
        "--xuilab-run-index", str(spec["runIndex"]), "--xuilab-repeat-count", str(spec["plannedRepeatCount"]),
        "--xuilab-warmup-frames", str(spec["warmupFrames"]), "--xuilab-measure-frames", str(spec["measureFrames"]),
        "--xuilab-sample-capacity", str(spec["measureFrames"]), "--xuilab-target-frame-rate", str(spec["targetFrameRate"]),
        "--xuilab-vsync-count", "0", "--xuilab-candidate-id", manifest["candidateId"],
        "--xuilab-build-id", manifest["buildId"], "--xuilab-source-revision", manifest["sourceRevision"],
    ]


def _new_log_path(root: pathlib.Path, run_id: str) -> pathlib.Path:
    canonical = root / (run_id + PLAYER_LOG_SUFFIX)
    if not _lexists(canonical):
        return canonical
    _fail("{}: player log already exists; refusing to overwrite".format(run_id))


def _write_failure(
    root: pathlib.Path,
    run_id: str,
    attempt: str,
    process: Optional[subprocess.Popen[Any]],
    timeout: bool,
    reason: str,
    started: float,
) -> pathlib.Path:
    process_pid = getattr(process, "pid", None) if process is not None else None
    process_code = getattr(process, "returncode", None) if process is not None else None
    path = _failure_sidecar_path(root, run_id, attempt)
    value = {
        "runId": run_id,
        "pid": process_pid,
        "timeout": bool(timeout),
        "exitCode": process_code,
        "reason": reason,
        "durationSeconds": max(0.0, time.monotonic() - started),
    }
    _write_json_new(path, value, "failure sidecar")
    return path


def _start_player(command: Sequence[str]) -> subprocess.Popen[Any]:
    startup = None
    if hasattr(subprocess, "STARTUPINFO"):
        startup = subprocess.STARTUPINFO()
        startup.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        startup.wShowWindow = 1
    kwargs: Dict[str, Any] = {
        "stdout": subprocess.DEVNULL,
        "stderr": subprocess.DEVNULL,
    }
    if startup is not None:
        kwargs["startupinfo"] = startup
    return subprocess.Popen(list(command), **kwargs)


def _execute_one(
    root: pathlib.Path,
    spec: Mapping[str, Any],
    manifest: Mapping[str, Any],
    series_id: str,
    player: pathlib.Path,
    timeout_seconds: int,
    recorded_root: Optional[str],
    build_hashes_path: pathlib.Path,
    build_root: Optional[pathlib.Path],
    recorded_build_root: Optional[pathlib.Path],
    manifest_hash: str,
    hashes_file_hash: str,
    manifest_path: pathlib.Path,
    hashes_path: pathlib.Path,
) -> None:
    run_id = spec["runId"]
    attempt = "{}-{}".format(os.getpid(), time.time_ns())
    log_path = _new_log_path(root, run_id)
    intent_path = root / (run_id + INTENT_SUFFIX)
    if _lexists(intent_path):
        _fail("{}: resume intent already exists; operator evidence is required".format(run_id))

    # Verify every pinned file immediately before creating the intent.  A
    # changed build therefore cannot leave an apparent child attempt behind.
    _assert_frozen_inputs(manifest_path, hashes_path, manifest_hash, hashes_file_hash)
    verify_build_hashes(
        build_hashes_path, player, build_root, recorded_build_root,
        expected_hashes_file_sha256=hashes_file_hash,
    )
    intent = {
        "schemaVersion": "xuilab.list.resume-intent/v1",
        "runId": run_id,
        "seriesId": series_id,
        "candidateId": manifest["candidateId"],
        "buildId": manifest["buildId"],
        "sourceRevision": manifest["sourceRevision"],
        "pid": os.getpid(),
        "attempt": attempt,
        "player": str(player),
        "logPath": str(log_path),
        "createdUtc": dt.datetime.now(dt.timezone.utc).isoformat(),
    }
    _write_json_new(intent_path, intent, "resume intent")
    process: Optional[subprocess.Popen[Any]] = None
    started = time.monotonic()
    try:
        command = _player_command(player, root, spec, manifest, series_id, log_path)
        try:
            process = _start_player(command)
        except Exception as exc:
            failure_path = _write_failure(root, run_id, attempt, None, False, str(exc), started)
            _remove_owned(intent_path, "resume intent")
            raise ResumeError("{}: Player could not start; failure sidecar {}".format(run_id, failure_path.name))
        try:
            exit_code = process.wait(timeout=timeout_seconds)
        except subprocess.TimeoutExpired as exc:
            # Only terminate the exact object created by this invocation.
            if process.poll() is None:
                process.kill()
                process.wait(timeout=15)
            failure_path = _write_failure(root, run_id, attempt, process, True, str(exc), started)
            _remove_owned(intent_path, "resume intent")
            raise ResumeError("{}: Player timed out; failure sidecar {}".format(run_id, failure_path.name))
        except Exception as exc:
            failure_path = _write_failure(root, run_id, attempt, process, False, str(exc), started)
            _remove_owned(intent_path, "resume intent")
            raise ResumeError("{}: Player wait failed; failure sidecar {}".format(run_id, failure_path.name))
        if exit_code != 0:
            failure_path = _write_failure(
                root, run_id, attempt, process, False,
                "Player exit {}".format(exit_code), started,
            )
            _remove_owned(intent_path, "resume intent")
            raise ResumeError("{}: Player exit {}; failure sidecar {}".format(run_id, exit_code, failure_path.name))

        try:
            result = verifier._validate_run(
                root, spec, manifest,
                recorded_root=_effective_recorded_root(root, spec, recorded_root),
            )
            _validate_series_id(root, spec, series_id)
        except Exception as exc:
            failure_path = _write_failure(root, run_id, attempt, process, False, str(exc), started)
            _remove_owned(intent_path, "resume intent")
            raise ResumeError("{}: raw run validation failed; failure sidecar {}".format(run_id, failure_path.name))

        record = result["record"]
        receipt = {
            "runId": run_id,
            "pid": process.pid,
            "exitCode": int(exit_code),
            "durationSeconds": max(0.0, time.monotonic() - started),
            "completedUtc": dt.datetime.now(dt.timezone.utc).isoformat(),
            "artifactSetSha256": record["artifactSetSha256"],
        }
        _write_json_new(root / (run_id + RECEIPT_SUFFIX), receipt, "receipt")
        _remove_owned(intent_path, "resume intent")
    except ResumeError:
        raise
    except Exception:
        # An unexpected exception intentionally leaves the intent marker.  The
        # next inspect must block until an operator examines the exact state.
        raise


def execute_plan(
    root: pathlib.Path,
    manifest_path: pathlib.Path,
    player: pathlib.Path,
    plan: Optional[str] = None,
    timeout_seconds: int = 180,
    continue_after_failure: bool = False,
    recorded_root: Optional[str] = None,
    series_id: Optional[str] = None,
    build_hashes_path: Optional[pathlib.Path] = None,
    build_root: Optional[pathlib.Path] = None,
    recorded_build_root: Optional[pathlib.Path] = None,
) -> Dict[str, Any]:
    """Resume pending runs, returning a final read-only inspection summary."""
    root = pathlib.Path(os.path.abspath(os.path.normpath(str(root))))
    manifest_path = pathlib.Path(os.path.abspath(os.path.normpath(str(manifest_path))))
    player = pathlib.Path(player)
    if timeout_seconds <= 0:
        _fail("timeout must be positive")
    # Capture the manifest bytes before parsing them.  A concurrent writer
    # between parse and launch is then detected by the post-parse check.
    manifest_hash = _sha256_file(manifest_path, "manifest")
    manifest, selected_plan = _manifest_and_plan(manifest_path, plan)
    frozen_series = _derive_series_id(manifest_path, root, manifest, series_id)
    _assert_path(root, "artifact root")
    if not root.is_dir():
        _fail("artifact root is not a directory: {}".format(root))
    player = _absolute_existing(player, "player")
    hash_path = _find_hash_file(root, manifest_path, build_hashes_path)
    _assert_regular_file(hash_path, "build hashes")
    hashes_file_hash = _sha256_file(hash_path, "build hashes")
    _assert_frozen_inputs(manifest_path, hash_path, manifest_hash, hashes_file_hash)
    lock = PlanLock(_lock_path(root, manifest_path))
    lock.acquire()
    release_lock = False
    try:
        statuses = [classify_run(root, spec, manifest, frozen_series, recorded_root=recorded_root) for spec in manifest["runs"]]
        blocked = [item for item in statuses if item["status"] in ("interrupted", "invalid")]
        if blocked:
            _fail("plan contains blocked runs: {}".format(", ".join(item["runId"] for item in blocked)))
        failed = [item for item in statuses if item["status"] == "failed"]
        if failed and not continue_after_failure:
            _fail("plan contains failed runs; pass --continue-after-failure to continue pending runs explicitly: {}".format(
                ", ".join(item["runId"] for item in failed)
            ))
        # A failure is historical evidence.  The explicit flag permits the
        # remaining pending runs to continue; it never retries that old runId.
        selected = [item for item in statuses if item["status"] == "pending"]
        by_id = {spec["runId"]: spec for spec in manifest["runs"]}
        for item in selected:
            spec = by_id[item["runId"]]
            _assert_frozen_inputs(manifest_path, hash_path, manifest_hash, hashes_file_hash)
            _execute_one(
                root, spec, manifest, frozen_series, player, timeout_seconds,
                recorded_root, hash_path, build_root, recorded_build_root,
                manifest_hash=manifest_hash,
                hashes_file_hash=hashes_file_hash,
                manifest_path=manifest_path,
                hashes_path=hash_path,
            )
        # Also close the race after the final child.  There is no next loop
        # iteration in which to notice a changed frozen input or build.
        _assert_frozen_inputs(manifest_path, hash_path, manifest_hash, hashes_file_hash)
        verify_build_hashes(
            hash_path, player, build_root, recorded_build_root,
            expected_hashes_file_sha256=hashes_file_hash,
        )
        release_lock = True
        return inspect_plan(
            root, manifest_path, selected_plan, recorded_root=recorded_root,
            series_id=frozen_series, build_hashes_path=hash_path,
        )
    except Exception:
        # Ordinary, observable errors are safe to retry.  OS termination or a
        # keyboard interrupt skips this handler and leaves the lock + intent.
        release_lock = True
        raise
    finally:
        if release_lock:
            lock.release()


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Inspect or safely resume a frozen List Lab plan.")
    parser.add_argument("--root", type=pathlib.Path, default=pathlib.Path("Artifacts"))
    parser.add_argument("--manifest", type=pathlib.Path, required=True)
    parser.add_argument("--plan", choices=PLAN_NAMES)
    parser.add_argument("--series-id", help="explicit series identity only when it cannot be derived")
    parser.add_argument("--recorded-root", help="original outputDirectory for offline inspection of a relocated copy")
    parser.add_argument("--build-hashes", type=pathlib.Path)
    parser.add_argument("--player", type=pathlib.Path, help="exact Player executable; required with --execute")
    parser.add_argument("--build-root", type=pathlib.Path, help="current root for relative or mapped build hash paths")
    parser.add_argument("--recorded-build-root", type=pathlib.Path, help="original root prefix in absolute build hash paths")
    parser.add_argument("--timeout", type=int, default=180)
    parser.add_argument("--execute", action="store_true", help="launch pending/explicitly continued runs")
    parser.add_argument("--continue-after-failure", action="store_true", help="continue pending runs while preserving valid failures")
    return parser


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = _parser()
    args = parser.parse_args(argv)
    try:
        if args.execute:
            if args.player is None:
                parser.error("--player is required with --execute")
            result = execute_plan(
                args.root, args.manifest, args.player, plan=args.plan,
                timeout_seconds=args.timeout, continue_after_failure=args.continue_after_failure,
                recorded_root=args.recorded_root, series_id=args.series_id,
                build_hashes_path=args.build_hashes, build_root=args.build_root,
                recorded_build_root=args.recorded_build_root,
            )
            print(json.dumps(result, ensure_ascii=False, sort_keys=True))
            return 0
        result = inspect_plan(
            args.root, args.manifest, plan=args.plan,
            recorded_root=args.recorded_root, series_id=args.series_id,
            build_hashes_path=args.build_hashes,
        )
        print(json.dumps(result, ensure_ascii=False, sort_keys=True))
        return 0
    except (ResumeError, verifier.VerificationError, OSError, ValueError, TypeError) as exc:
        print("RESUME FAILED: {}".format(exc), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
