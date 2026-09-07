"""Focused source archive tests using temporary Git repositories."""
from __future__ import annotations

import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent))
import source_archive as archive


class SourceArchiveTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)
        self.repo = self.base / "repo"
        self.repo.mkdir()
        self._git("init", "-q")
        self._git("config", "user.email", "archive@example.invalid")
        self._git("config", "user.name", "Archive Test")
        (self.repo / ".gitignore").write_text(
            "Artifacts/\nXUILab/Library/\n", encoding="utf-8"
        )
        (self.repo / "README.md").write_bytes(b"original\n")
        (self.repo / "Docs" / "References").mkdir(parents=True)
        (self.repo / "Docs" / "References" / "private.md").write_bytes(b"reference\n")
        (self.repo / "source.cs").write_bytes(b"class Fixture {}\n")
        (self.repo / "XUILab" / "ProjectSettings").mkdir(parents=True)
        (self.repo / "XUILab" / "ProjectSettings" / "settings.asset").write_bytes(b"settings\n")
        (self.repo / "XUILab.sln").write_bytes(b"generated\n")
        self._git("add", ".")
        self._git("commit", "-qm", "fixture")
        (self.repo / "README.md").write_bytes(b"dirty\n")
        (self.repo / "new.py").write_bytes(b"print('new')\n")
        (self.repo / ".env.local").write_bytes(b"secret\n")
        (self.repo / "Artifacts" / "old").mkdir(parents=True)
        (self.repo / "Artifacts" / "old" / "raw.bin").write_bytes(b"raw\n")
        (self.repo / "XUILab" / "Library").mkdir(parents=True)
        (self.repo / "XUILab" / "Library" / "cache.bin").write_bytes(b"cache\n")

    def _git(self, *args: str) -> None:
        subprocess.run(
            ["git", "-C", str(self.repo), *args],
            check=True, capture_output=True
        )

    def _pack(self, *extras: str) -> Path:
        output = self.base / "archive"
        result = archive.pack(self.repo, output, extras)
        self.assertTrue(result["dirty"])
        return output

    def test_pack_excludes_generated_and_keeps_existing_references(self) -> None:
        output = self._pack()
        index = json.loads((output / "index.json").read_text(encoding="utf-8"))
        paths = {entry["path"] for entry in index["files"]}
        self.assertEqual(
            paths,
            {
                "source/.gitignore",
                "source/README.md",
                "source/Docs/References/private.md",
                "source/new.py",
                "source/source.cs",
                "source/XUILab/ProjectSettings/settings.asset",
            },
        )
        self.assertEqual(index["source"]["fileCount"], 6)
        archive.check(output, archive._sha256(output / "index.json"))

    def test_check_is_independent_after_source_removal_and_relocation(self) -> None:
        output = self._pack()
        moved = self.base / "moved"
        shutil.copytree(output, moved)
        self.repo.rename(self.base / "repo-removed")
        result = archive.check(moved)
        self.assertEqual(result["fileCount"], 6)

    def test_check_rejects_tamper_and_extra_file(self) -> None:
        output = self._pack()
        (output / "source" / "README.md").write_bytes(b"tampered\n")
        with self.assertRaisesRegex(ValueError, "file mismatch"):
            archive.check(output)
        (output / "source" / "README.md").write_bytes(b"dirty\n")
        (output / "extra.bin").write_bytes(b"extra")
        with self.assertRaisesRegex(ValueError, "unindexed"):
            archive.check(output)

    def test_pack_does_not_overwrite_existing_output(self) -> None:
        output = self._pack()
        with self.assertRaises(FileExistsError):
            archive.pack(self.repo, output)

    def test_expected_index_digest_is_checked(self) -> None:
        output = self._pack()
        with self.assertRaisesRegex(ValueError, "index SHA"):
            archive.check(output, "0" * 64)

    def test_current_snapshot_extra_is_explicitly_labelled(self) -> None:
        media = self.base / "media"
        media.mkdir()
        (media / "frame.bin").write_bytes(b"frame")
        output = self._pack(f"media={media}")
        index = json.loads((output / "index.json").read_text(encoding="utf-8"))
        self.assertEqual(index["extras"][0]["identityType"], "currentSnapshot")
        self.assertIsNone(index["extras"][0]["identity"])
        self.assertEqual(archive.check(output)["extraCount"], 1)

    def test_core_extra_requires_valid_bundle(self) -> None:
        core = self.base / "core"
        core.mkdir()
        (core / "bundle.json").write_text("{}", encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "core evidence bundle"):
            archive.pack(self.repo, self.base / "core-archive", [f"core={core}"])

    def test_pack_freezes_paths_and_hashes_before_copy(self) -> None:
        output = self.base / "changed-during-copy"
        original_copy = archive._copy_file
        changed = False

        def copy_then_mutate(source: Path, target: Path, expected: str) -> None:
            nonlocal changed
            original_copy(source, target, expected)
            if not changed:
                changed = True
                (self.repo / ".gitignore").write_bytes(b"changed after copy\n")
                (self.repo / "appeared-after-freeze.txt").write_bytes(b"new\n")

        with patch.object(archive, "_copy_file", side_effect=copy_then_mutate):
            with self.assertRaisesRegex(ValueError, "changed while creating archive"):
                archive.pack(self.repo, output)
        self.assertFalse((output / "index.json").exists())

    def test_pack_rejects_head_identity_drift_with_same_selected_inputs(self) -> None:
        output = self.base / "head-drift"
        original_copy = archive._copy_file
        changed = False

        def copy_then_commit(source: Path, target: Path, expected: str) -> None:
            nonlocal changed
            original_copy(source, target, expected)
            if not changed:
                changed = True
                self._git("commit", "--allow-empty", "-qm", "mid-pack")

        with patch.object(archive, "_copy_file", side_effect=copy_then_commit):
            with self.assertRaisesRegex(ValueError, "Git identity changed"):
                archive.pack(self.repo, output)
        self.assertFalse((output / "index.json").exists())

    def test_pack_rejects_dirty_identity_drift_with_same_selected_inputs(self) -> None:
        self._git("checkout", "--", ".")
        self._git("clean", "-fdx")
        self.assertEqual(archive._git_identity(self.repo)[1], False)
        output = self.base / "dirty-drift"
        original_copy = archive._copy_file
        changed = False

        def copy_then_mutate_generated(source: Path, target: Path, expected: str) -> None:
            nonlocal changed
            original_copy(source, target, expected)
            if not changed:
                changed = True
                (self.repo / "XUILab.sln").write_bytes(b"generated changed during copy\n")

        with patch.object(archive, "_copy_file", side_effect=copy_then_mutate_generated):
            with self.assertRaisesRegex(ValueError, "Git identity changed"):
                archive.pack(self.repo, output)
        self.assertFalse((output / "index.json").exists())

    def test_rejects_case_colliding_paths_and_unsafe_names(self) -> None:
        with self.assertRaisesRegex(ValueError, "case-colliding"):
            archive._ensure_unique(["source/A.txt", "source/a.txt"], "fixture")
        for value in ("../escape", "a\\b", "C:/escape", "NUL.txt", "a//b", "a."):
            with self.subTest(value=value), self.assertRaises(ValueError):
                archive._portable_relative(value)

    def test_reparse_extra_is_rejected(self) -> None:
        target = self.base / "target"
        target.mkdir()
        link = self.base / "media-link"
        try:
            link.symlink_to(target, target_is_directory=True)
        except (OSError, NotImplementedError):
            self.skipTest("symbolic links unavailable")
        with self.assertRaisesRegex(ValueError, "reparse"):
            archive.pack(self.repo, self.base / "reparse-archive", [f"media={link}"])


if __name__ == "__main__":
    unittest.main()
