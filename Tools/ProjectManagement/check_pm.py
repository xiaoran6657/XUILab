"""Read-only checks for XUILab's Markdown PM contract; never grants acceptance."""
from __future__ import annotations

import argparse
from dataclasses import dataclass, field
from pathlib import Path
import re
from urllib.parse import unquote, urlsplit

SCHEMA = "xuilab.pm/v1"
LEGACY = frozenset(f"M{s}-{n:02}" for s in (0, 1) for n in range(1, 5))
STATES = frozenset("proposed ready running frozen verifying rework blocked done cancelled".split())
TERMINAL = {"done", "cancelled"}
ACTIVE = {"ready", "running", "frozen", "verifying", "done"}
STATUS_KEYS = frozenset("pm_schema task_id task_type state brief brief_revision candidate dependencies blockers recovery next_action review verification review_independence execution_independence".split())
BRIEF_KEYS = frozenset("brief_revision task_type risk review_required execution_required".split())
GLOBAL_KEYS = frozenset("current_task latest_task unity_owner unity_task".split())
LINK = re.compile(r"\[[^\]\n]*\]\(([^)\n]+)\)")
TOKEN = re.compile(r"[A-Za-z0-9][A-Za-z0-9._/-]*\Z")
MAX_FILE_BYTES = 2 * 1024 * 1024
MAX_TASKS = 256


def prose(text: str) -> str:
    """Exclude fenced examples; this is deliberately not a full Markdown parser."""
    result, fence, length = [], None, 0
    for line in text.splitlines():
        marker = re.match(r"^\s{0,3}(`{3,}|~{3,})(.*)$", line)
        if marker:
            chars, tail = marker.groups()
            if fence is None:
                fence, length = chars[0], len(chars)
                continue
            if chars[0] == fence and len(chars) >= length and not tail.strip():
                fence = None
                continue
        if fence is None:
            result.append(line)
    return "\n".join(result)


@dataclass
class Result:
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    strict_tasks: int = 0
    legacy_tasks: int = 0


class Checker:
    def __init__(self, root: Path):
        self.root = root.resolve()
        self.result = Result()
        self.tasks: dict[Path, dict[str, str]] = {}
        self.edges: dict[Path, list[Path]] = {}

    def error(self, path: Path, message: str):
        self.result.errors.append(f"{path.relative_to(self.root)}: {message}")

    def read(self, path: Path) -> str:
        try:
            if path.is_file() and path.stat().st_size > MAX_FILE_BYTES:
                self.error(path, f"file exceeds {MAX_FILE_BYTES} byte bound")
                return ""
            return prose(path.read_text(encoding="utf-8-sig"))
        except (OSError, UnicodeError) as exc:
            self.error(path, f"cannot read: {exc}")
            return ""

    def fields(self, path: Path, required: set | frozenset) -> dict[str, str]:
        values = {}
        for key, value in re.findall(r"^- ([a-z_]+): (.*)$", self.read(path), re.M):
            if key in values:
                self.error(path, f"duplicate field {key}")
            values[key] = value.strip()
        for key in sorted(required):
            if not values.get(key):
                self.error(path, f"missing field {key}")
        return values

    def links(self, path: Path, text: str) -> list[Path]:
        found = []
        for raw in LINK.findall(text):
            if "<" in raw or ">" in raw or "{" in raw or "}" in raw or "..." in raw:
                continue  # Template placeholders are not destinations.
            try:
                parts = urlsplit(raw)
            except ValueError:
                self.error(path, f"malformed link: {raw}")
                continue
            if parts.scheme or parts.netloc:
                continue
            if not parts.path:
                continue  # Fragment-only links are explicitly out of scope.
            relative = Path(unquote(parts.path))
            target = (path.parent / relative).resolve()
            if not target.is_relative_to(self.root):
                self.error(path, f"link outside repository: {raw}")
                continue
            found.append(target)
            if not target.exists():
                message = f"{path.relative_to(self.root)}: missing link {raw}"
                if target.is_relative_to(self.root / "Artifacts"):
                    self.result.warnings.append(message)
                else:
                    self.error(path, f"missing link {raw}")
        return found

    def file_link(self, path: Path, text: str, label: str) -> Path | None:
        targets = self.links(path, text)
        if (len(targets) != 1 or len(LINK.findall(text)) != 1 or
                not targets[0].is_file() or targets[0].suffix.lower() != ".md"):
            self.error(path, f"{label} requires one existing local file link")
            return None
        return targets[0]

    def table(self, path: Path, heading: str, columns: list[str]) -> dict[str, list[str]]:
        text = self.read(path)
        sections = re.split(r"^## ", text, flags=re.M)
        matches = [s.partition("\n")[2] for s in sections[1:] if s.partition("\n")[0].strip() == heading]
        if len(matches) != 1:
            self.error(path, f"requires one section {heading}")
            return {}
        rows = [line.strip().strip("|").split("|") for line in matches[0].splitlines() if line.strip().startswith("|")]
        rows = [[cell.strip() for cell in row] for row in rows]
        if len(rows) < 3 or rows[0] != columns or len(rows[1]) != len(columns) or not all(re.fullmatch(r":?-{3,}:?", cell) for cell in rows[1]):
            self.error(path, f"invalid or empty {heading} table")
            return {}
        data = {}
        for row in rows[2:]:
            if len(row) != len(columns) or not all(row):
                self.error(path, f"invalid {heading} row")
                continue
            if not re.fullmatch(r"[A-Za-z0-9_-]+", row[0]) or row[0] in data:
                self.error(path, f"invalid or duplicate acceptance ID {row[0]}")
            data[row[0]] = row[1:]
        return data

    def report(self, path: Path, values: dict, kind: str) -> dict:
        reference = values.get(kind, "")
        if reference == "not_run":
            return {}
        report = self.file_link(path, reference, kind)
        if report is None:
            return {}
        metadata = self.fields(report, {"candidate", "brief_revision"} | ({"verdict"} if kind == "review" else set()))
        for key in ("candidate", "brief_revision"):
            if metadata.get(key) != values.get(key):
                self.error(path, f"{kind} {key} mismatch")
        if kind == "review" and metadata.get("verdict") not in {"accept", "changes_requested", "not_reviewable"}:
            self.error(path, "invalid review verdict")
        return metadata

    def task(self, path: Path, values: dict, roadmap_ids: set[str]):
        self.result.strict_tasks += 1
        if values.get("pm_schema") != SCHEMA:
            self.error(path, "unknown or missing pm_schema")
        if set(values) - STATUS_KEYS:
            self.error(path, f"unknown fields: {sorted(set(values) - STATUS_KEYS)}")
        task_id, kind, state = values.get("task_id", ""), values.get("task_type"), values.get("state")
        if task_id != path.parent.name:
            self.error(path, "task_id does not match directory")
        if not ((kind == "infra" and re.fullmatch(r"INFRA-\d{3}", task_id)) or (kind == "mvp" and task_id in roadmap_ids)):
            self.error(path, "invalid task_type or task_id (MVP IDs must be in roadmap)")
        if state not in STATES:
            self.error(path, "invalid state")
        if not re.fullmatch(r"r\d+", values.get("brief_revision", "")):
            self.error(path, "invalid brief_revision")
        candidate = values.get("candidate", "")
        if not TOKEN.fullmatch(candidate) or (state in {"frozen", "verifying", "done"} and candidate == "none"):
            self.error(path, "invalid or unfrozen candidate")
        for key, allowed in (("review_independence", {"independent", "self-check", "not_run", "not_applicable"}), ("execution_independence", {"independent", "shared-operator", "self-check", "not_run", "not_applicable"})):
            if values.get(key) not in allowed:
                self.error(path, f"invalid {key}")
        if state == "blocked" and any(values.get(k) in {None, "", "none"} for k in ("blockers", "recovery")):
            self.error(path, "blocked requires blockers and recovery")
        self.edges[path] = []
        dependency = values.get("dependencies", "")
        if dependency != "none":
            targets = self.links(path, dependency)
            if not targets or len(targets) != len(LINK.findall(dependency)):
                self.error(path, "dependencies require task links or none")
            for target in targets:
                if target.name != "TASK_STATUS.md" or target not in self.tasks:
                    self.error(path, "dependency is not a known TASK_STATUS")
                else:
                    self.edges[path].append(target)
                    if target == path or targets.count(target) > 1:
                        self.error(path, "self or duplicate dependency")
                    if state in ACTIVE and self.tasks[target].get("state") not in TERMINAL:
                        self.error(path, "unfinished dependency for execution state")
        brief = self.file_link(path, values.get("brief", ""), "brief")
        if brief is None:
            return
        if brief != path.with_name("TASK_BRIEF.md"):
            self.error(path, "brief must be this task's TASK_BRIEF.md")
        contract = self.fields(brief, BRIEF_KEYS)
        for key in ("brief_revision", "task_type"):
            if contract.get(key) != values.get(key):
                self.error(path, f"brief {key} mismatch")
        if contract.get("risk") not in {"R0", "R1", "R2", "R3"}:
            self.error(brief, "invalid risk")
        for key in ("review_required", "execution_required"):
            if contract.get(key) not in {"true", "false"}:
                self.error(brief, f"invalid {key}")
        if contract.get("risk") in {"R2", "R3"} and contract.get("review_required") != "true":
            self.error(brief, "R2/R3 requires independent review")
        criteria = self.table(brief, "验收矩阵", ["ID", "requirement", "判据"])
        actual = self.table(path, "验收状态", ["ID", "result", "candidate", "evidence"])
        if criteria.keys() != actual.keys():
            self.error(path, "acceptance IDs differ from Brief")
        for item, (requirement, _criterion) in criteria.items():
            if requirement not in {"required", "not_applicable"}:
                self.error(brief, f"invalid requirement {item}")
            if item not in actual:
                continue
            result, row_candidate, evidence = actual[item]
            if result not in {"pass", "fail", "not_run", "not_applicable"}:
                self.error(path, f"invalid result {item}")
            if requirement == "required" and (result == "not_applicable" or (state == "done" and result != "pass")):
                self.error(path, f"required acceptance not passed: {item}")
            if requirement == "not_applicable" and state == "done" and result != "not_applicable":
                self.error(path, f"not_applicable acceptance mismatch: {item}")
            if result == "pass":
                if candidate == "none" or row_candidate != candidate:
                    self.error(path, f"acceptance candidate mismatch: {item}")
                targets = self.links(path, evidence)
                if not targets or len(targets) != len(LINK.findall(evidence)) or not all(p.is_file() for p in targets):
                    self.error(path, f"acceptance requires existing evidence files: {item}")
        review = self.report(path, values, "review")
        verification = self.report(path, values, "verification")
        if state == "done":
            if contract.get("review_required") == "true" and (values.get("review_independence") != "independent" or review.get("verdict") != "accept"):
                self.error(path, "done requires independent accepted review")
            if review and review.get("verdict") != "accept":
                self.error(path, "done conflicts with review verdict")
            if contract.get("execution_required") == "true" and (values.get("execution_independence") != "independent" or not verification):
                self.error(path, "done requires independent verification")

    def global_state(self):
        path = self.root / "Docs/PM/PROJECT_STATUS.md"
        values = self.fields(path, GLOBAL_KEYS)
        for key in ("current_task", "latest_task", "unity_task"):
            value = values.get(key, "")
            if value == "none":
                if key == "latest_task" and any(t.get("state") in TERMINAL for t in self.tasks.values()):
                    self.error(path, "latest_task may be none only before any terminal tasks exist")
                continue
            target = self.file_link(path, value, key)
            if target not in self.tasks:
                self.error(path, f"{key} is not a known task")
                continue
            terminal = self.tasks[target].get("state") in TERMINAL
            if (key == "current_task" and terminal) or (key == "latest_task" and not terminal):
                self.error(path, f"{key} contradicts task state")
        owner = values.get("unity_owner", "")
        if not re.fullmatch(r"[A-Za-z0-9_./@-]+", owner):
            self.error(path, "unity_owner must contain one owner ID")
        if (owner == "none") != (values.get("unity_task") == "none"):
            self.error(path, "unity owner/task must be paired")
        if re.search(r"^- owner[：:]", self.read(path), re.M):
            self.error(path, "use only unity_owner; duplicate legacy owner register")
        queue = self.root / "Docs/PM/Next_Actions.md"
        seen = set()
        for target in self.links(queue, self.read(queue)):
            if target.name != "TASK_STATUS.md":
                continue
            if target not in self.tasks:
                self.error(queue, "unknown queued task")
            elif self.tasks[target].get("state") in TERMINAL:
                self.error(queue, "terminal task in Next Actions")
            if target in seen:
                self.error(queue, "duplicate queued task")
            seen.add(target)

    def run(self) -> Result:
        roadmap = self.root / "Docs/MVP/ROADMAP.md"
        roadmap_ids = set(re.findall(r"^\|\s*(M\d-[A-Z]?\d+)\s*\|", self.read(roadmap), re.M))
        task_root = self.root / "Docs/PM/Tasks"
        if not task_root.is_dir():
            self.error(task_root, "missing task directory")
        folders = sorted(task_root.iterdir() if task_root.is_dir() else [])
        if len(folders) > MAX_TASKS:
            self.error(task_root, f"task count exceeds {MAX_TASKS}")
        for folder in folders[:MAX_TASKS]:
            if not folder.is_dir():
                continue
            path = folder / "TASK_STATUS.md"
            text = self.read(path)
            if folder.name in LEGACY and not re.search(r"^- pm_schema[：:]", text, re.M):
                states = re.findall(r"^- state[：:]\s*([a-z_]+)(?=$|[\s（(])", text, re.M)
                self.tasks[path] = {"state": states[0] if states else "unknown"}
                self.result.legacy_tasks += 1
                self.result.warnings.append(f"{folder.name}: legacy state only; acceptance/candidate not checked")
            else:
                self.tasks[path] = self.fields(path, STATUS_KEYS)
        for path, values in self.tasks.items():
            if "pm_schema" in values or path.parent.name not in LEGACY:
                self.task(path, values, roadmap_ids)
        visiting, visited = set(), set()

        def visit(path):
            if path in visiting:
                self.error(path, "dependency cycle")
                return
            if path in visited:
                return
            visiting.add(path)
            for target in self.edges.get(path, []):
                visit(target)
            visiting.remove(path)
            visited.add(path)

        for path in self.tasks:
            visit(path)
        self.global_state()
        docs = {self.root / name for name in ("AGENTS.md", "README.md", "Docs/README.md", "Docs/PM/PROJECT_STATUS.md", "Docs/PM/Next_Actions.md")}
        for directory in ("Docs/Agents", "Docs/Agents/templates", "Docs/MVP"):
            docs.update((self.root / directory).glob("*.md"))
        for path, values in self.tasks.items():
            if "pm_schema" in values or path.parent.name not in LEGACY:
                docs.update(path.parent.glob("*.md"))
        for path in sorted(docs):
            self.links(path, self.read(path))
        self.result.errors = list(dict.fromkeys(self.result.errors))
        self.result.warnings = list(dict.fromkeys(self.result.warnings))
        return self.result


def check(root: Path) -> Result:
    return Checker(root).run()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[2])
    args = parser.parse_args()
    result = check(args.root)
    for message in result.warnings:
        print("WARNING:", message)
    for message in result.errors:
        print("ERROR:", message)
    print(f"PM structure {'FAIL' if result.errors else 'PASS'}: {result.strict_tasks} v1, {result.legacy_tasks} legacy; acceptance not inferred")
    return 1 if result.errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
