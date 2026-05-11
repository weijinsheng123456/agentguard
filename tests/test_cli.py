"""Tests for AgentGuard CLI commands."""

from __future__ import annotations
import subprocess
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


def test_cli_version():
    """gate version should return version string."""
    result = subprocess.run(
        [sys.executable, "gate.py", "version"],
        capture_output=True, text=True, timeout=10,
        cwd=os.path.join(os.path.dirname(__file__), ".."),
    )
    assert result.returncode == 0
    assert "AgentGuard" in result.stdout or "v1." in result.stdout or "1.0" in result.stdout


def test_cli_quick_check():
    """gate run --quick should work (even with no staged files)."""
    result = subprocess.run(
        [sys.executable, "gate.py", "run", "--quick"],
        capture_output=True, text=True, timeout=30,
        cwd=os.path.join(os.path.dirname(__file__), ".."),
    )
    assert result.returncode == 0


def test_cli_trend():
    """gate trend should work (even with no data)."""
    result = subprocess.run(
        [sys.executable, "gate.py", "trend"],
        capture_output=True, text=True, timeout=10,
        cwd=os.path.join(os.path.dirname(__file__), ".."),
    )
    assert result.returncode == 0
