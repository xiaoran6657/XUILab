"""Create and verify a portable source and evidence archive."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path, PurePosixPath, PureWindowsPath
import re
import shutil
import stat
import subprocess
import sys
from typing import Any, Iterable, Mapping

SCHEMA = "xuilab.source.archive/v1"
INDEX_NAME = "index.json"
SOURCE_ROOT = "source"
_REPARSE_POINT = 0x400
_HASH_RE = re.compile(r"^[0-9a-fA-F]{64}$")
_HEAD_RE = re.compile(r"^[0-9a-fA-F]{40}$")
_EXTRA_NAME_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]{0,63}$")
_DEVICE_NAMES = {
    "CON", "PRN", "AUX", "NUL",
    *(f"COM{i}" for i in range(1, 10)),
    *(f"LPT{i}" for i in range(1, 10)),
}
_RESERVED_NAMES = {INDEX_NAME.casefold(), SOURCE_ROOT.casefold()}
_GENERATED_PREFIXES = {
    "artifacts", ".git", ".vs", ".vscode", ".idea", "build", "builds",
    "temp", "logs", "recordings", "memorycaptures",
}
_UNITY_GENERATED_DIRS = {
    "library", "temp", "obj", "build", "builds", "logs", "usersettings",
    "memorycaptures", "recordings", "exportedobj",
}
_UNITY_GENERATED_EXTENSIONS = (
    ".csproj", ".sln", ".suo", ".user", ".userprefs", ".pidb", ".booproj",
    ".svd", ".pdb", ".mdb", ".opendb", ".vc.db", ".unityproj",
)


class ArchiveError(ValueError):
    """An archive input or output violates the portable archive contract."""


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest().upper()


def _digest(value: Any) -> str:
    if not isinstance(value, str) or not _HASH_RE.fullmatch(value):
        raise ArchiveError("invalid SHA-256")
    return value.upper()


def _portable_relative(value: Any) -> str:
    if not isinstance(value, str) or not value or "\\" in value:
        raise ArchiveError("expected portable relative path")
    parts = value.split("/")
    if (
        PurePosixPath(value).is_absolute()
        or PureWindowsPath(value).drive
        or any(
            part in {"", ".", ".."}
            or part.endswith((" ", "."))
            or part.split(".", 1)[0].upper() in _DEVICE_NAMES
            or re.search(r'[<>:"|?*\x00-\x1f]', part)
            for part in parts
        )
    ):
        raise ArchiveError("unsafe relative path: " + value)
    return value


def _inside(root: Path, relative: str) -> Path:
    return root.joinpath(*_portable_relative(relative).split("/"))


def _is_reparse(path: Path) -> bool:
    try:
        if path.is_symlink():
            return True
        info = path.lstat()
    except FileNotFoundError:
        return False
    return bool(getattr(info, "st_file_attributes", 0) & _REPARSE_POINT)


def _assert_no_reparse_components(path: Path, label: str) -> None:
    absolute = Path(path).absolute()
    for component in reversed(absolute.parents):
        if component.exists() and _is_reparse(component):
            raise ArchiveError(f"{label} contains reparse point: {component}")
    if absolute.exists() and _is_reparse(absolute):
        raise ArchiveError(f"{label} is a reparse point: {absolute}")


def _require_regular_file(path: Path, label: str) -> None:
    _assert_no_reparse_components(path, label)
    try:
        info = path.lstat()
    except FileNotFoundError as exc:
        raise ArchiveError(f"missing {label}: {path}") from exc
    if not stat.S_ISREG(info.st_mode):
        raise ArchiveError(f"{label} is not a regular file: {path}")


def _require_directory(path: Path, label: str) -> None:
    _assert_no_reparse_components(path, label)
    if not path.is_dir():
        raise ArchiveError(f"missing {label}: {path}")


def _walk_files(root: Path, label: str) -> tuple[list[str], set[str]]:
    _require_directory(root, label)
    files: list[str] = []
    directories: set[str] = set()
    for parent, dirnames, filenames in os.walk(root, topdown=True, followlinks=False):
        parent_path = Path(parent)
        for name in list(dirnames):
            candidate = parent_path / name
            _assert_no_reparse_components(candidate, label)
            if not candidate.is_dir():
                raise ArchiveError(f"{label} member is not a directory: {candidate}")
            directories.add(_portable_relative(candidate.relative_to(root).as_posix()))
        for name in filenames:
            candidate = parent_path / name
            _require_regular_file(candidate, label + " member")
            files.append(_portable_relative(candidate.relative_to(root).as_posix()))
    files.sort()
    return files, directories


def _excluded_reason(name: str) -> str | None:
    parts = _portable_relative(name).casefold().split("/")
    if parts[0] in _GENERATED_PREFIXES:
        return "generated or local workspace directory"
    if "__pycache__" in parts or parts[-1].endswith((".pyc", ".pyo", ".pyd")):
        return "generated Python cache or extension"
    if parts[0] == "xuilab" and len(parts) > 1:
        if parts[1] in _UNITY_GENERATED_DIRS:
            return "Unity generated directory"
        if len(parts) == 2 and any(parts[1].endswith(ext) for ext in _UNITY_GENERATED_EXTENSIONS):
            return "Unity generated project file"
    basename = parts[-1]
    if basename != ".env.example" and (
        basename == ".env" or basename.startswith(".env.")
        or basename.endswith((".local", ".secret"))
    ):
        return "local or secret configuration"
    if any(basename.endswith(ext) for ext in _UNITY_GENERATED_EXTENSIONS):
        return "generated IDE or Unity project file"
    return None


def _git_output(repo: Path, *arguments: str) -> bytes:
    command = ["git", "-C", str(repo), *arguments]
    try:
        result = subprocess.run(command, check=True, capture_output=True)
    except (OSError, subprocess.CalledProcessError) as exc:
        raise ArchiveError("git command failed: " + " ".join(command)) from exc
    return result.stdout


def _git_identity(repo: Path) -> tuple[str, bool]:
    try:
        head = os.fsdecode(_git_output(repo, "rev-parse", "HEAD").strip())
    except ArchiveError as exc:
        raise ArchiveError("Git HEAD is unavailable") from exc
    if not (_HEAD_RE.fullmatch(head) or head == "none"):
        raise ArchiveError("Git HEAD is not a commit id")
    status = _git_output(repo, "status", "--porcelain=v1", "--untracked-files=all", "-z")
    return head.lower(), bool(status)


def _ensure_unique(paths: Iterable[str], label: str) -> None:
    seen: dict[str, str] = {}
    for value in paths:
        safe = _portable_relative(value)
        folded = safe.casefold()
        previous = seen.get(folded)
        if previous is not None and previous != safe:
            raise ArchiveError(f"case-colliding {label}: {previous} and {safe}")
        if previous is not None:
            raise ArchiveError(f"duplicate {label}: {safe}")
        seen[folded] = safe


def source_paths(repo: Path) -> list[str]:
    raw = _git_output(repo, "ls-files", "--cached", "--others", "--exclude-standard", "-z")
    selected: list[str] = []
    for item in raw.split(b"\0"):
        if not item:
            continue
        name = _portable_relative(os.fsdecode(item))
        if _excluded_reason(name) is None:
            selected.append(name)
    _ensure_unique(selected, "source paths")
    return sorted(selected)


def _parse_extra(value: str) -> tuple[str, Path]:
    if "=" not in value:
        raise ArchiveError("extra must use NAME=PATH: " + value)
    name, raw_path = value.split("=", 1)
    if not _EXTRA_NAME_RE.fullmatch(name):
        raise ArchiveError("unsafe extra name: " + name)
    if name.casefold() in _RESERVED_NAMES:
        raise ArchiveError("reserved extra name: " + name)
    if not raw_path:
        raise ArchiveError("empty extra path: " + name)
    return name, Path(raw_path).absolute()


def _extra_identity(root: Path, name: str) -> tuple[str, str | None, dict[str, str] | None]:
    if name.casefold() not in {"core", "evidence", "evidence-core", "evidence_core"}:
        return "currentSnapshot", None, None
    bundle_index = root / "bundle.json"
    _require_regular_file(bundle_index, "core bundle index")
    list_lab = Path(__file__).resolve().parents[1] / "ListLab"
    if str(list_lab) not in sys.path:
        sys.path.insert(0, str(list_lab))
    try:
        import evidence_bundle
        _, index_sha = evidence_bundle.check_integrity(root)
    except Exception as exc:
        raise ArchiveError("core evidence bundle integrity check failed") from exc
    try:
        value = json.loads(bundle_index.read_text(encoding="utf-8"))
        catalog = value["catalog"]
        identity = {
            key: catalog[key]
            for key in ("evidenceId", "candidateId", "buildId", "sourceRevision")
        }
    except (OSError, KeyError, TypeError, UnicodeError, json.JSONDecodeError) as exc:
        raise ArchiveError("core bundle catalog identity is missing") from exc
    if not all(isinstance(item, str) and item for item in identity.values()):
        raise ArchiveError("core bundle catalog identity is invalid")
    return "historicalEvidenceBundle", index_sha, identity


def _lexical_overlap(first: Path, second: Path) -> bool:
    first = first.absolute()
    second = second.absolute()
    return first == second or first in second.parents or second in first.parents


def _copy_file(source: Path, target: Path, expected: str) -> None:
    if _sha256(source) != expected:
        raise ArchiveError("source changed before copy: " + str(source))
    target.parent.mkdir(parents=True, exist_ok=True)
    _assert_no_reparse_components(target.parent, "archive output")
    with target.open("xb") as destination, source.open("rb") as origin:
        shutil.copyfileobj(origin, destination, length=1024 * 1024)
    if _sha256(target) != expected:
        raise ArchiveError("source changed while copying: " + str(source))


def _write_json_new(path: Path, value: Mapping[str, Any]) -> None:
    _assert_no_reparse_components(path.parent, "archive output")
    with path.open("x", encoding="utf-8", newline="\n") as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2, sort_keys=False, allow_nan=False)
        stream.write("\n")


def _freeze_source(repo: Path, names: list[str]) -> list[tuple[str, Path, str]]:
    frozen: list[tuple[str, Path, str]] = []
    for name in names:
        source = _inside(repo, name)
        _require_regular_file(source, "source file")
        frozen.append((f"{SOURCE_ROOT}/{name}", source, _sha256(source)))
    return frozen


def _freeze_extra(root: Path, name: str) -> tuple[list[tuple[str, Path, str]], list[str]]:
    relative_names, _ = _walk_files(root, "extra directory")
    frozen = []
    for relative in relative_names:
        source = _inside(root, relative)
        frozen.append((f"{name}/{relative}", source, _sha256(source)))
    return frozen, relative_names


def _verify_frozen_inputs(
    repo: Path,
    source_names: list[str],
    source_inputs: list[tuple[str, Path, str]],
    parsed_extras: list[tuple[str, Path]],
    extra_names: dict[str, list[str]],
    extra_inputs: dict[str, list[tuple[str, Path, str]]],
    extra_identities: dict[str, tuple[str, str | None, dict[str, str] | None]],
    expected_head: str,
    expected_dirty: bool,
) -> None:
    if source_paths(repo) != source_names:
        raise ArchiveError("source file set changed while creating archive")
    for _, source, expected in source_inputs:
        _require_regular_file(source, "source file")
        if _sha256(source) != expected:
            raise ArchiveError("source file changed while creating archive: " + str(source))
    for name, root in parsed_extras:
        current_names, _ = _walk_files(root, "extra directory")
        if current_names != extra_names[name]:
            raise ArchiveError("extra file set changed while creating archive: " + name)
        for _, source, expected in extra_inputs[name]:
            _require_regular_file(source, "extra file")
            if _sha256(source) != expected:
                raise ArchiveError("extra file changed while creating archive: " + str(source))
        if _extra_identity(root, name) != extra_identities[name]:
            raise ArchiveError("extra identity changed while creating archive: " + name)
    if _git_identity(repo) != (expected_head, expected_dirty):
        raise ArchiveError("Git identity changed while creating archive")


def pack(repo: Path, out: Path, extras: Iterable[str] = ()) -> dict[str, Any]:
    repo = Path(repo).absolute()
    out = Path(out).absolute()
    _require_directory(repo, "repository")
    _assert_no_reparse_components(repo, "repository")
    head, dirty = _git_identity(repo)
    source_names = source_paths(repo)
    source_inputs = _freeze_source(repo, source_names)

    parsed_extras = [_parse_extra(value) for value in extras]
    _ensure_unique((name for name, _ in parsed_extras), "extra names")
    extra_inputs: dict[str, list[tuple[str, Path, str]]] = {}
    extra_names: dict[str, list[str]] = {}
    extra_identities: dict[str, tuple[str, str | None, dict[str, str] | None]] = {}
    for name, root in parsed_extras:
        _require_directory(root, "extra directory")
        if _lexical_overlap(out, root):
            raise ArchiveError("archive output overlaps extra input: " + name)
        frozen, names = _freeze_extra(root, name)
        extra_inputs[name] = frozen
        extra_names[name] = names
        extra_identities[name] = _extra_identity(root, name)

    if out == repo or any(_lexical_overlap(out, source) for _, source, _ in source_inputs):
        raise ArchiveError("archive output overlaps source input")
    if out.exists():
        raise FileExistsError(f"archive output already exists: {out}")
    _assert_no_reparse_components(out.parent, "archive output parent")
    out.parent.mkdir(parents=True, exist_ok=True)
    _assert_no_reparse_components(out.parent, "archive output parent")
    out.mkdir()
    _assert_no_reparse_components(out, "archive output")
    (out / SOURCE_ROOT).mkdir()
    for name, _ in parsed_extras:
        (out / name).mkdir()

    entries: list[dict[str, Any]] = []
    all_inputs = list(source_inputs)
    for name, _ in parsed_extras:
        all_inputs.extend(extra_inputs[name])
    for archive_name, source, expected in all_inputs:
        target = _inside(out, archive_name)
        _copy_file(source, target, expected)
        entries.append({"path": archive_name, "sha256": expected, "size": target.stat().st_size})
    entries.sort(key=lambda item: item["path"])
    _ensure_unique((item["path"] for item in entries), "archive paths")

    _verify_frozen_inputs(
        repo, source_names, source_inputs, parsed_extras, extra_names,
        extra_inputs, extra_identities, head, dirty,
    )

    source_entries = [item for item in entries if item["path"].startswith(SOURCE_ROOT + "/")]
    extra_descriptions: list[dict[str, Any]] = []
    for name, _ in parsed_extras:
        identity_type, index_sha, identity = extra_identities[name]
        members = [item for item in entries if item["path"].startswith(name + "/")]
        extra_descriptions.append({
            "name": name,
            "root": name,
            "identityType": identity_type,
            "fileCount": len(members),
            "byteCount": sum(item["size"] for item in members),
            "indexPath": f"{name}/bundle.json" if index_sha else None,
            "indexSha256": index_sha,
            "identity": identity,
        })
    extra_descriptions.sort(key=lambda item: item["name"])

    index = {
        "schemaVersion": SCHEMA,
        "source": {
            "root": SOURCE_ROOT,
            "head": head,
            "dirty": dirty,
            "fileCount": len(source_entries),
            "byteCount": sum(item["size"] for item in source_entries),
        },
        "extras": extra_descriptions,
        "files": entries,
    }
    _write_json_new(out / INDEX_NAME, index)
    return {
        "archive": str(out),
        "indexSha256": _sha256(out / INDEX_NAME),
        "sourceRevision": head,
        "dirty": dirty,
        "fileCount": len(entries),
        "extraCount": len(extra_descriptions),
    }


def _read_json(path: Path, label: str) -> Any:
    _require_regular_file(path, label)
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ArchiveError(f"invalid JSON: {label}") from exc


def _validate_index(index: Any) -> tuple[dict[str, Any], list[dict[str, Any]], list[dict[str, Any]]]:
    if not isinstance(index, dict) or set(index) != {"schemaVersion", "source", "extras", "files"}:
        raise ArchiveError("invalid archive index fields")
    if index["schemaVersion"] != SCHEMA:
        raise ArchiveError("unsupported archive schema")

    source = index["source"]
    if not isinstance(source, dict) or set(source) != {
        "root", "head", "dirty", "fileCount", "byteCount"
    }:
        raise ArchiveError("invalid source metadata")
    if source["root"] != SOURCE_ROOT:
        raise ArchiveError("invalid source root")
    if not isinstance(source["head"], str) or not (
        _HEAD_RE.fullmatch(source["head"]) or source["head"] == "none"
    ):
        raise ArchiveError("invalid source identity")
    if type(source["dirty"]) is not bool:
        raise ArchiveError("invalid source dirty state")
    for key in ("fileCount", "byteCount"):
        if type(source[key]) is not int or source[key] < 0:
            raise ArchiveError("invalid source size metadata")

    extras = index["extras"]
    if not isinstance(extras, list):
        raise ArchiveError("invalid extras metadata")
    extra_names: list[str] = []
    for item in extras:
        if not isinstance(item, dict) or set(item) != {
            "name", "root", "identityType", "fileCount", "byteCount",
            "indexPath", "indexSha256", "identity"
        }:
            raise ArchiveError("invalid extra metadata")
        name = item["name"]
        if (
            not isinstance(name, str) or not _EXTRA_NAME_RE.fullmatch(name)
            or item["root"] != name or name.casefold() in _RESERVED_NAMES
        ):
            raise ArchiveError("invalid extra name")
        extra_names.append(name)
        if item["identityType"] not in {"currentSnapshot", "historicalEvidenceBundle"}:
            raise ArchiveError("invalid extra identity type")
        for key in ("fileCount", "byteCount"):
            if type(item[key]) is not int or item[key] < 0:
                raise ArchiveError("invalid extra size metadata")
        if item["identityType"] == "currentSnapshot":
            if item["indexPath"] is not None or item["indexSha256"] is not None or item["identity"] is not None:
                raise ArchiveError("current snapshot has historical identity")
        else:
            if not isinstance(item["indexPath"], str) or not isinstance(item["indexSha256"], str):
                raise ArchiveError("historical extra lacks index identity")
            _portable_relative(item["indexPath"])
            _digest(item["indexSha256"])
            identity = item["identity"]
            if (
                not isinstance(identity, dict)
                or set(identity) != {"evidenceId", "candidateId", "buildId", "sourceRevision"}
                or not all(isinstance(value, str) and value for value in identity.values())
            ):
                raise ArchiveError("invalid historical extra identity")
    _ensure_unique(extra_names, "extra names")

    files = index["files"]
    if not isinstance(files, list) or not files:
        raise ArchiveError("empty archive file list")
    entries: list[dict[str, Any]] = []
    file_names: list[str] = []
    for item in files:
        if not isinstance(item, dict) or set(item) != {"path", "sha256", "size"}:
            raise ArchiveError("invalid archive file entry")
        path = _portable_relative(item["path"])
        if path == INDEX_NAME:
            raise ArchiveError("index.json must not be listed")
        if type(item["size"]) is not int or item["size"] < 0:
            raise ArchiveError("invalid archive file size")
        entry = {"path": path, "sha256": _digest(item["sha256"]), "size": item["size"]}
        entries.append(entry)
        file_names.append(path)
    _ensure_unique(file_names, "archive paths")
    if file_names != sorted(file_names):
        raise ArchiveError("archive file list is not sorted")

    roots = {SOURCE_ROOT.casefold()} | {item["name"].casefold() for item in extras}
    for item in entries:
        root = item["path"].split("/", 1)[0]
        if root.casefold() not in roots:
            raise ArchiveError("archive file outside declared root: " + item["path"])
    return source, extras, entries


def _expected_directories(files: Iterable[str], roots: Iterable[str]) -> set[str]:
    expected = set(roots)
    for name in files:
        parts = name.split("/")
        for index in range(1, len(parts)):
            expected.add("/".join(parts[:index]))
    return expected


def check(archive: Path, expected_index: str | None = None) -> dict[str, Any]:
    archive = Path(archive).absolute()
    _require_directory(archive, "archive")
    _assert_no_reparse_components(archive, "archive")
    index_path = archive / INDEX_NAME
    _require_regular_file(index_path, "archive index")
    index_sha = _sha256(index_path)
    if expected_index is not None and index_sha != _digest(expected_index):
        raise ArchiveError("archive index SHA mismatch")
    source, extras, entries = _validate_index(_read_json(index_path, "archive index"))

    actual_files: set[str] = set()
    actual_dirs: set[str] = set()
    for parent, dirnames, filenames in os.walk(archive, topdown=True, followlinks=False):
        parent_path = Path(parent)
        for name in list(dirnames):
            candidate = parent_path / name
            _assert_no_reparse_components(candidate, "archive member")
            actual_dirs.add(_portable_relative(candidate.relative_to(archive).as_posix()))
        for name in filenames:
            candidate = parent_path / name
            _require_regular_file(candidate, "archive member")
            actual_files.add(_portable_relative(candidate.relative_to(archive).as_posix()))

    expected_files = {INDEX_NAME} | {item["path"] for item in entries}
    if actual_files != expected_files:
        raise ArchiveError("archive contains missing or unindexed files")
    expected_dirs = _expected_directories(
        (item["path"] for item in entries),
        [SOURCE_ROOT, *(item["name"] for item in extras)],
    )
    if actual_dirs != expected_dirs:
        raise ArchiveError("archive contains unexpected directories")

    for item in entries:
        path = _inside(archive, item["path"])
        if path.stat().st_size != item["size"] or _sha256(path) != item["sha256"]:
            raise ArchiveError("archive file mismatch: " + item["path"])

    source_entries = [item for item in entries if item["path"].startswith(SOURCE_ROOT + "/")]
    if (
        source["fileCount"] != len(source_entries)
        or source["byteCount"] != sum(item["size"] for item in source_entries)
    ):
        raise ArchiveError("source size metadata mismatch")
    for extra in extras:
        members = [item for item in entries if item["path"].startswith(extra["name"] + "/")]
        if (
            extra["fileCount"] != len(members)
            or extra["byteCount"] != sum(item["size"] for item in members)
        ):
            raise ArchiveError("extra size metadata mismatch: " + extra["name"])
        if extra["identityType"] == "historicalEvidenceBundle":
            index_member = next(
                (item for item in members if item["path"] == extra["indexPath"]), None
            )
            if index_member is None or index_member["sha256"] != extra["indexSha256"]:
                raise ArchiveError("historical extra index mismatch: " + extra["name"])
            bundle = _read_json(
                _inside(archive, extra["indexPath"]), "archived bundle index"
            )
            if (
                not isinstance(bundle, dict)
                or bundle.get("schemaVersion") != "xuilab.evidence.bundle/v1"
            ):
                raise ArchiveError("archived historical extra is not a B bundle")
            catalog = bundle.get("catalog")
            if (
                not isinstance(catalog, dict)
                or any(catalog.get(key) != extra["identity"].get(key)
                       for key in extra["identity"])
            ):
                raise ArchiveError("archived historical extra identity mismatch")
    return {
        "archive": str(archive),
        "indexSha256": index_sha,
        "sourceRevision": source["head"],
        "dirty": source["dirty"],
        "fileCount": len(entries),
        "extraCount": len(extras),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    pack_parser = subparsers.add_parser("pack", help="copy source and explicit directories")
    pack_parser.add_argument("--repo", type=Path, default=Path("."))
    pack_parser.add_argument("--out", type=Path, required=True)
    pack_parser.add_argument(
        "--extra", action="append", default=[], metavar="NAME=PATH",
        help="explicit directory; core must be a valid evidence bundle",
    )
    check_parser = subparsers.add_parser("check", help="verify without the original repository")
    check_parser.add_argument("--archive", type=Path, required=True)
    check_parser.add_argument("--expected-index-sha256")
    args = parser.parse_args(argv)
    try:
        result = (
            pack(args.repo, args.out, args.extra)
            if args.command == "pack"
            else check(args.archive, args.expected_index_sha256)
        )
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0
    except Exception as exc:
        print("SOURCE ARCHIVE FAILED: " + str(exc))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
