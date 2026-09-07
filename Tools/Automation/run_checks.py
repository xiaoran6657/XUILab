"""Run XUILab's fixed, explicit, one-shot offline checks.

The scheduler builds a deterministic plan, executes only an explicit command
allowlist, and persists enough state to distinguish completion from an
interrupted run. It never invokes a shell, Unity, a Player, a network client,
or an unattended loop.
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import subprocess
import sys
import tempfile
from typing import Any, Callable, Sequence


PLAN_SCHEMA = "xuilab.offline-check-plan/v1"
STATE_SCHEMA = "xuilab.offline-check-state/v1"
RESULT_SCHEMA = "xuilab.offline-check-result/v1"
ALLOWED_CHECKS: tuple[str, ...] = (
    "check_offline",
    "ProjectManagement",
    "ListLab",
    "UnityOperations",
    "GradientLab",
    "Archiving",
    "Automation",
)
DEFAULT_TIMEOUT_SECONDS = 300
MAX_TIMEOUT_SECONDS = 3600
MAX_CAPTURE_CHARS = 2 * 1024 * 1024
RUN_ID_PATTERN = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,63}\Z")
RESERVED_WINDOWS_NAME = re.compile(
    r"(?i)(?:con|prn|aux|nul|com[1-9]|lpt[1-9])(?:\..*)?\Z"
)


class AutomationError(ValueError):
    """An offline automation request or persisted record is invalid."""


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AutomationError(message)


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds")


def _reject_json_constant(value: str) -> None:
    raise ValueError(f"non-finite JSON value: {value}")


def _reject_duplicate_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    value: dict[str, Any] = {}
    for key, item in pairs:
        require(key not in value, f"duplicate JSON key: {key}")
        value[key] = item
    return value


def _read_json(path: Path) -> dict[str, Any]:
    _safe_path(path)
    try:
        value = json.loads(
            path.read_text(encoding="utf-8"),
            object_pairs_hook=_reject_duplicate_keys,
            parse_constant=_reject_json_constant,
        )
    except AutomationError:
        raise
    except (OSError, UnicodeError, ValueError) as exc:
        raise AutomationError(f"unreadable JSON {path}: {exc}") from exc
    require(isinstance(value, dict), f"JSON object required: {path}")
    return value


def _write_json(path: Path, value: dict[str, Any]) -> None:
    """Write one JSON record atomically."""
    _safe_path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(
        value, ensure_ascii=False, indent=2, sort_keys=True, allow_nan=False
    ) + "\n"
    fd, temporary_name = tempfile.mkstemp(
        prefix=f".{path.name}.", suffix=".tmp", dir=str(path.parent)
    )
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary_name, path)
    except BaseException:
        try:
            os.unlink(temporary_name)
        except OSError:
            pass
        raise


def _safe_path(path: Path) -> Path:
    """Reject symlinks and Windows reparse points in an existing path chain."""
    absolute = Path(os.path.abspath(path))
    for part in (absolute, *absolute.parents):
        try:
            present = part.exists() or part.is_symlink()
        except OSError as exc:
            raise AutomationError(f"cannot inspect path {part}: {exc}") from exc
        if not present:
            continue
        try:
            info = part.lstat()
        except OSError as exc:
            raise AutomationError(f"cannot inspect path {part}: {exc}") from exc
        attributes = getattr(info, "st_file_attributes", 0)
        if stat.S_ISLNK(info.st_mode) or attributes & getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400):
            raise AutomationError(f"link/reparse point forbidden: {part}")
    return absolute


def repository_root(value: str | Path | None = None) -> Path:
    raw = Path(value) if value is not None else Path(__file__).resolve().parents[2]
    _safe_path(raw)
    try:
        root = raw.resolve()
    except OSError as exc:
        raise AutomationError(f"cannot resolve repository root {raw}: {exc}") from exc
    require(root.is_dir(), f"repository root is not a directory: {root}")
    _safe_path(root)
    return root


def validate_repository(root: Path) -> None:
    require((root / "Tools" / "check_offline.py").is_file(), "missing Tools/check_offline.py")
    for name in ALLOWED_CHECKS[1:]:
        require((root / "Tools" / name).is_dir(), f"missing Tools/{name} directory")


def validate_run_id(value: str) -> str:
    require(isinstance(value, str) and RUN_ID_PATTERN.fullmatch(value) is not None, "invalid run-id")
    require(value not in {".", ".."}, "invalid run-id")
    require(RESERVED_WINDOWS_NAME.fullmatch(value) is None, "reserved run-id")
    return value


def validate_timeout(value: Any) -> int:
    require(
        type(value) is int and 0 < value <= MAX_TIMEOUT_SECONDS,
        f"timeout-seconds must be an integer from 1 to {MAX_TIMEOUT_SECONDS}",
    )
    return value


def normalize_checks(value: Any) -> list[str]:
    require(isinstance(value, (list, tuple)) and value, "checks must be non-empty")
    values: list[str] = []
    for item in value:
        require(type(item) is str, "check names must be strings")
        values.extend(part.strip() for part in item.split(",") if part.strip())
    require(values, "checks must be non-empty")
    require(len(values) == len(set(values)), "duplicate check")
    unknown = sorted(set(values) - set(ALLOWED_CHECKS))
    require(not unknown, f"unsupported check: {', '.join(unknown)}")
    return [name for name in ALLOWED_CHECKS if name in values]

def validate_test_directories(root: Path, selected: Sequence[str]) -> None:
    for name in selected:
        if name == "check_offline":
            continue
        directory = root / "Tools" / name
        matches = sorted(directory.glob("test_*.py"))
        valid = []
        for path in matches:
            _safe_path(path)
            if path.is_file():
                valid.append(path)
        require(valid, f"no test_*.py files in Tools/{name}")



def _command_for(name: str, root: Path, timeout_seconds: int) -> dict[str, Any]:
    python = str(Path(sys.executable).resolve())
    if name == "check_offline":
        argv = [python, "-B", str(root / "Tools" / "check_offline.py"), "--root", str(root)]
        kind = "script"
    else:
        argv = [
            python,
            "-B",
            "-m",
            "unittest",
            "discover",
            "-s",
            str(root / "Tools" / name),
            "-p",
            "test_*.py",
        ]
        kind = "unittest"
    return {
        "name": name,
        "kind": kind,
        "argv": argv,
        "cwd": str(root),
        "timeout_seconds": timeout_seconds,
    }


def build_plan(
    root: str | Path | None = None,
    checks: Sequence[str] | None = None,
    timeout_seconds: int = DEFAULT_TIMEOUT_SECONDS,
) -> dict[str, Any]:
    repo = repository_root(root)
    require(sys.version_info >= (3, 11), "Python >=3.11 required")
    validate_repository(repo)
    timeout = validate_timeout(timeout_seconds)
    selected = normalize_checks(list(checks) if checks is not None else list(ALLOWED_CHECKS))
    validate_test_directories(repo, selected)
    commands = [_command_for(name, repo, timeout) for name in selected]
    plan: dict[str, Any] = {
        "schema": PLAN_SCHEMA,
        "root": str(repo),
        "python": sys.version.split()[0],
        "checks": selected,
        "timeout_seconds": timeout,
        "commands": commands,
    }
    plan["plan_sha256"] = _plan_digest(plan)
    return plan


def _run_directory(root: Path, run_id: str) -> Path:
    validate_run_id(run_id)
    base = _safe_path(root / "Artifacts" / "offline-checks")
    base.mkdir(parents=True, exist_ok=True)
    _safe_path(base)
    run_dir = base / run_id
    try:
        run_dir.mkdir()
    except FileExistsError as exc:
        raise AutomationError(f"run-id already exists: {run_id}") from exc
    _safe_path(run_dir)
    return run_dir


def _capture(value: str) -> str:
    if len(value) <= MAX_CAPTURE_CHARS:
        return value
    return value[:MAX_CAPTURE_CHARS] + "\n[output truncated]\n"


Runner = Callable[..., subprocess.CompletedProcess[str]]


def run_checks(
    run_id: str,
    root: str | Path | None = None,
    checks: Sequence[str] | None = None,
    timeout_seconds: int = DEFAULT_TIMEOUT_SECONDS,
    executor: Runner | None = None,
) -> dict[str, Any]:
    """Execute one new plan and return its terminal result.

    executor is only for isolated tests. Production uses subprocess.run with a
    list and shell=False.
    """
    repo = repository_root(root)
    plan = build_plan(repo, checks, timeout_seconds)
    run_dir = _run_directory(repo, run_id)
    started = utc_now()
    state: dict[str, Any] = {
        "schema": STATE_SCHEMA,
        "run_id": run_id,
        "status": "running",
        "started_at": started,
        "finished_at": None,
        "plan_sha256": plan["plan_sha256"],
        "completed_commands": 0,
    }
    _write_json(run_dir / "plan.json", plan)
    _write_json(run_dir / "state.json", state)
    results: list[dict[str, Any]] = []
    runner = executor or subprocess.run

    try:
        for command in plan["commands"]:
            command_started = utc_now()
            try:
                completed = runner(
                    command["argv"],
                    cwd=command["cwd"],
                    shell=False,
                    capture_output=True,
                    text=True,
                    encoding="utf-8",
                    errors="replace",
                    timeout=command["timeout_seconds"],
                    check=False,
                )
                exit_code = int(completed.returncode)
                status = "passed" if exit_code == 0 else "failed"
                stdout = _capture(completed.stdout or "")
                stderr = _capture(completed.stderr or "")
            except subprocess.TimeoutExpired as exc:
                exit_code = None
                status = "timeout"
                stdout = _capture((exc.stdout or "") if isinstance(exc.stdout, str) else "")
                stderr = _capture((exc.stderr or "") if isinstance(exc.stderr, str) else "")
            except KeyboardInterrupt:
                state.update(status="interrupted", finished_at=None, completed_commands=len(results))
                _write_json(run_dir / "state.json", state)
                _write_json(
                    run_dir / "result.json",
                    {
                        "schema": RESULT_SCHEMA,
                        "run_id": run_id,
                        "status": "needs_review",
                        "started_at": started,
                        "finished_at": None,
                        "plan_sha256": plan["plan_sha256"],
                        "reason": "interrupted before terminal result",
                        "commands": results,
                    },
                )
                raise
            results.append(
                {
                    "name": command["name"],
                    "kind": command["kind"],
                    "argv": command["argv"],
                    "started_at": command_started,
                    "finished_at": utc_now(),
                    "status": status,
                    "exit_code": exit_code,
                    "stdout": stdout,
                    "stderr": stderr,
                }
            )
            state["completed_commands"] = len(results)
            _write_json(run_dir / "state.json", state)
    except KeyboardInterrupt:
        raise
    except BaseException as exc:
        finished = utc_now()
        state.update(status="failed", finished_at=finished, completed_commands=len(results))
        _write_json(run_dir / "state.json", state)
        _write_json(
            run_dir / "result.json",
            {
                "schema": RESULT_SCHEMA,
                "run_id": run_id,
                "status": "failed",
                "started_at": started,
                "finished_at": finished,
                "plan_sha256": plan["plan_sha256"],
                "reason": f"scheduler error: {type(exc).__name__}: {exc}",
                "commands": results,
            },
        )
        raise

    overall = "passed" if all(item["status"] == "passed" for item in results) else "failed"
    finished = utc_now()
    state.update(status=overall, finished_at=finished, completed_commands=len(results))
    terminal = {
        "schema": RESULT_SCHEMA,
        "run_id": run_id,
        "status": overall,
        "started_at": started,
        "finished_at": finished,
        "plan_sha256": plan["plan_sha256"],
        "reason": "",
        "commands": results,
    }
    _write_json(run_dir / "result.json", terminal)
    _write_json(run_dir / "state.json", state)
    return terminal



_PLAN_FIELDS = (
    "schema",
    "root",
    "python",
    "checks",
    "timeout_seconds",
    "commands",
    "plan_sha256",
)
_STATE_FIELDS = (
    "schema",
    "run_id",
    "status",
    "started_at",
    "finished_at",
    "plan_sha256",
    "completed_commands",
)
_RESULT_FIELDS = (
    "schema",
    "run_id",
    "status",
    "started_at",
    "finished_at",
    "plan_sha256",
    "reason",
    "commands",
)
_COMMAND_RESULT_FIELDS = (
    "name",
    "kind",
    "argv",
    "started_at",
    "finished_at",
    "status",
    "exit_code",
    "stdout",
    "stderr",
)
_COMMAND_STATUSES = {"passed", "failed", "timeout"}
_TERMINAL_STATUSES = {"passed", "failed"}
_TRUNCATION_MARKER = "\n[output truncated]\n"


def _exact_keys(value: Any, fields: Sequence[str], context: str) -> None:
    require(isinstance(value, dict), f"{context} must be a JSON object")
    expected = set(fields)
    actual = set(value)
    missing = sorted(expected - actual)
    extra = sorted(actual - expected)
    require(
        not missing and not extra,
        f"{context} schema mismatch; missing={missing}, extra={extra}",
    )


def _timestamp(value: Any, context: str, allow_none: bool = False) -> datetime | None:
    if value is None and allow_none:
        return None
    require(type(value) is str and bool(value), f"{context} must be a timestamp string")
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError as exc:
        raise AutomationError(f"{context} is not ISO-8601: {value}") from exc
    require(parsed.tzinfo is not None and parsed.utcoffset() is not None,
            f"{context} must include a timezone")
    return parsed


def _plan_digest(plan: dict[str, Any]) -> str:
    unsigned = dict(plan)
    unsigned.pop("plan_sha256", None)
    encoded = json.dumps(
        unsigned,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode()
    return hashlib.sha256(encoded).hexdigest()


def _validate_plan_record(plan: Any, repo: Path) -> dict[str, Any]:
    _exact_keys(plan, _PLAN_FIELDS, "plan")
    require(plan["schema"] == PLAN_SCHEMA, "plan schema mismatch")
    require(type(plan["root"]) is str and bool(plan["root"]), "plan root is invalid")
    require(repository_root(plan["root"]) == repo, "plan root does not match inspected repository")
    require(type(plan["python"]) is str and bool(plan["python"]), "plan Python identity is invalid")
    checks = plan["checks"]
    require(type(checks) is list, "plan checks must be an array")
    require(checks == normalize_checks(checks), "plan checks are not the fixed allowlist order")
    timeout = validate_timeout(plan["timeout_seconds"])
    commands = plan["commands"]
    require(type(commands) is list and commands, "plan commands must be a non-empty array")
    expected = [_command_for(name, repo, timeout) for name in checks]
    require(commands == expected, "plan command identity does not match the fixed scheduler")
    require(
        type(plan["plan_sha256"]) is str
        and re.fullmatch(r"[0-9a-fA-F]{64}", plan["plan_sha256"]) is not None,
        "plan_sha256 is not a SHA-256 value",
    )
    require(plan["plan_sha256"].lower() == _plan_digest(plan), "plan_sha256 does not match plan bytes")
    return plan


def _validate_state_record(state: Any, plan: dict[str, Any], run_id: str) -> str:
    _exact_keys(state, _STATE_FIELDS, "state")
    require(state["schema"] == STATE_SCHEMA, "state schema mismatch")
    require(state["run_id"] == run_id, "state run-id mismatch")
    require(state["plan_sha256"] == plan["plan_sha256"], "state plan_sha256 mismatch")
    status = state["status"]
    require(status in {"running", "interrupted", *_TERMINAL_STATUSES}, "invalid state status")
    started = _timestamp(state["started_at"], "state.started_at")
    finished = _timestamp(
        state["finished_at"],
        "state.finished_at",
        allow_none=status in {"running", "interrupted"},
    )
    if status in _TERMINAL_STATUSES:
        require(finished is not None, "terminal state requires finished_at")
        require(finished >= started, "state finished_at precedes started_at")
    else:
        require(state["finished_at"] is None, "non-terminal state cannot have finished_at")
    count = state["completed_commands"]
    require(type(count) is int and not isinstance(count, bool) and 0 <= count <= len(plan["commands"]),
            "state completed_commands is invalid")
    if status in _TERMINAL_STATUSES:
        require(count == len(plan["commands"]), "terminal state has incomplete command count")
    return status


def _validate_capture(value: Any, context: str) -> None:
    require(type(value) is str, f"{context} must be captured text")
    require(len(value) <= MAX_CAPTURE_CHARS + len(_TRUNCATION_MARKER),
            f"{context} exceeds capture limit")
    if len(value) > MAX_CAPTURE_CHARS:
        require(value.endswith(_TRUNCATION_MARKER), f"{context} has an invalid truncation marker")


def _validate_command_result(item: Any, expected: dict[str, Any], context: str) -> str:
    _exact_keys(item, _COMMAND_RESULT_FIELDS, context)
    for field in ("name", "kind", "argv"):
        require(item[field] == expected[field], f"{context}.{field} does not match plan command")
    started = _timestamp(item["started_at"], f"{context}.started_at")
    finished = _timestamp(item["finished_at"], f"{context}.finished_at")
    require(finished >= started, f"{context}.finished_at precedes started_at")
    status = item["status"]
    require(status in _COMMAND_STATUSES, f"{context}.status is invalid")
    exit_code = item["exit_code"]
    if status == "timeout":
        require(exit_code is None, f"{context}.timeout must have null exit_code")
    else:
        require(type(exit_code) is int and not isinstance(exit_code, bool),
                f"{context}.exit_code must be an integer")
        require(
            (status == "passed" and exit_code == 0)
            or (status == "failed" and exit_code != 0),
            f"{context}.status and exit_code disagree",
        )
    _validate_capture(item["stdout"], f"{context}.stdout")
    _validate_capture(item["stderr"], f"{context}.stderr")
    return status



def _validate_terminal_records(
    state: dict[str, Any],
    result: Any,
    plan: dict[str, Any],
    run_id: str,
) -> dict[str, Any]:
    status = _validate_state_record(state, plan, run_id)
    require(status in _TERMINAL_STATUSES, "terminal records require terminal state")
    _exact_keys(result, _RESULT_FIELDS, "result")
    require(result["schema"] == RESULT_SCHEMA, "result schema mismatch")
    require(result["run_id"] == run_id, "result run-id mismatch")
    require(result["plan_sha256"] == plan["plan_sha256"], "result plan_sha256 mismatch")
    require(type(result["reason"]) is str, "result reason must be captured text")
    _timestamp(result["started_at"], "result.started_at")
    result_finished = _timestamp(result["finished_at"], "result.finished_at")
    require(result["started_at"] == state["started_at"], "state/result started_at mismatch")
    require(result["finished_at"] == state["finished_at"], "state/result finished_at mismatch")
    require(result_finished is not None, "terminal result requires finished_at")
    commands = result["commands"]
    require(type(commands) is list and len(commands) == len(plan["commands"]),
            "result must contain exactly every planned command")
    statuses = []
    for index, (item, expected) in enumerate(zip(commands, plan["commands"])):
        statuses.append(_validate_command_result(item, expected, f"result.commands[{index}]"))
    derived = "passed" if all(item == "passed" for item in statuses) else "failed"
    require(result["status"] == derived, "result status does not match command evidence")
    require(state["status"] == result["status"], "state/result status mismatch")
    return result


def inspect_run(run_id: str, root: str | Path | None = None) -> dict[str, Any]:
    repo = repository_root(root)
    validate_run_id(run_id)
    run_dir = _safe_path(repo / "Artifacts" / "offline-checks" / run_id)
    require(run_dir.is_dir(), f"run not found: {run_id}")
    plan = _validate_plan_record(_read_json(run_dir / "plan.json"), repo)
    state = _read_json(run_dir / "state.json")
    state_status = _validate_state_record(state, plan, run_id)
    result_path = _safe_path(run_dir / "result.json")
    if state_status in {"running", "interrupted"}:
        return {
            "schema": RESULT_SCHEMA,
            "run_id": run_id,
            "status": "needs_review",
            "reason": "run has no trustworthy terminal result",
            "state": state,
        }
    require(result_path.is_file(), f"result not found: {run_id}")
    result = _read_json(result_path)
    return _validate_terminal_records(state, result, plan, run_id)


def _parse_checks(values: list[str] | None) -> list[str]:
    return normalize_checks(values if values is not None else list(ALLOWED_CHECKS))


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="action", required=True)

    def common(subparser: argparse.ArgumentParser) -> None:
        subparser.add_argument("--root", type=Path, default=None, help="repository root")

    plan = subparsers.add_parser("plan", help="print a deterministic offline check plan")
    common(plan)
    plan.add_argument("--checks", nargs="+", default=None, metavar="CHECK")
    plan.add_argument("--timeout-seconds", type=int, default=DEFAULT_TIMEOUT_SECONDS)

    run = subparsers.add_parser("run", help="execute one explicit offline check run")
    common(run)
    run.add_argument("--run-id", required=True, metavar="ID")
    run.add_argument("--checks", nargs="+", default=None, metavar="CHECK")
    run.add_argument("--timeout-seconds", type=int, default=DEFAULT_TIMEOUT_SECONDS)

    inspect = subparsers.add_parser("inspect", help="inspect a prior run without retrying it")
    common(inspect)
    inspect.add_argument("--run-id", required=True, metavar="ID")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = _parser()
    args = parser.parse_args(argv)
    try:
        if args.action == "plan":
            value = build_plan(args.root, _parse_checks(args.checks), args.timeout_seconds)
        elif args.action == "run":
            value = run_checks(args.run_id, args.root, _parse_checks(args.checks), args.timeout_seconds)
        else:
            value = inspect_run(args.run_id, args.root)
    except KeyboardInterrupt:
        print(json.dumps({"status": "needs_review", "reason": "interrupted"}, ensure_ascii=False))
        return 130
    except (AutomationError, OSError) as exc:
        print(json.dumps({"status": "invalid", "error": str(exc)}, ensure_ascii=False), file=sys.stderr)
        return 2
    print(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True))
    if args.action in {"run", "inspect"} and value.get("status") != "passed":
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
