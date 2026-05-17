"""Tests for AgentGuard scanner."""

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from qg import scanner


def _config_for(path):
    return {
        "scan_dirs": [str(path)],
        "ignore_patterns": [],
    }


def test_scan_all_returns_correct_file_counts(tmp_path, monkeypatch):
    """scan_all should classify discovered files as new on first scan."""
    monkeypatch.setattr(scanner, "MANIFEST_FILE", tmp_path / "missing-manifest.json")

    (tmp_path / "one.py").write_text("print('one')\n")
    (tmp_path / "two.py").write_text("print('two')\n")
    (tmp_path / "notes.txt").write_text("not python\n")

    result = scanner.scan_all(_config_for(tmp_path))

    assert len(result["all_files"]) == 2
    assert len(result["new_files"]) == 2
    assert len(result["changed_files"]) == 0
    assert len(result["stable_files"]) == 0


def test_scan_all_handles_empty_directories(tmp_path, monkeypatch):
    """scan_all should return empty lists for an empty scan directory."""
    monkeypatch.setattr(scanner, "MANIFEST_FILE", tmp_path / "missing-manifest.json")

    result = scanner.scan_all(_config_for(tmp_path))

    assert result["all_files"] == []
    assert result["new_files"] == []
    assert result["changed_files"] == []
    assert result["stable_files"] == []
    assert result["scan_dirs"] == [str(tmp_path.resolve())]


def test_scan_all_respects_ignore_patterns(tmp_path, monkeypatch):
    """scan_all should filter files matching configured ignore patterns."""
    monkeypatch.setattr(scanner, "MANIFEST_FILE", tmp_path / "missing-manifest.json")

    keep = tmp_path / "keep.py"
    ignored_dir = tmp_path / "ignored"
    ignored_dir.mkdir()
    ignored = ignored_dir / "skip.py"

    keep.write_text("print('keep')\n")
    ignored.write_text("print('skip')\n")

    config = _config_for(tmp_path)
    config["ignore_patterns"] = ["*/ignored/*"]

    result = scanner.scan_all(config)

    assert result["all_files"] == [str(keep.resolve())]
    assert result["new_files"] == [str(keep.resolve())]


def test_scan_all_finds_py_files_correctly(tmp_path, monkeypatch):
    """scan_all should find Python files recursively and ignore other suffixes."""
    monkeypatch.setattr(scanner, "MANIFEST_FILE", tmp_path / "missing-manifest.json")

    package = tmp_path / "package"
    package.mkdir()
    root_file = tmp_path / "main.py"
    nested_file = package / "module.py"

    root_file.write_text("print('main')\n")
    nested_file.write_text("print('module')\n")
    (package / "README.md").write_text("# package\n")
    (package / "script.py.txt").write_text("not a python file\n")

    result = scanner.scan_all(_config_for(tmp_path))

    assert set(result["all_files"]) == {
        str(root_file.resolve()),
        str(nested_file.resolve()),
    }
    assert set(result["new_files"]) == set(result["all_files"])
