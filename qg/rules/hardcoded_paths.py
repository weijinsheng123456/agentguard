"""硬编码路径检测+修复规则 — FIXABLE"""
from __future__ import annotations
import re
import os

from .base import Rule, register_rule
from ..models import Issue, Severity


@register_rule
class HardcodedPathsRule(Rule):
    name = "hardcoded_paths"
    severity = Severity.FIXABLE
    description = "Hardcoded /home/*/ paths → use $HOME"

    # 排除文件
    EXCLUDE_PATTERNS = ["test_integration"]

    def diagnose(self, filepath: str) -> list[Issue]:
        issues = []
        # 排除测试文件
        for exc in self.EXCLUDE_PATTERNS:
            if exc in filepath:
                return issues

        try:
            with open(filepath) as f:
                lines = f.readlines()
            for i, line in enumerate(lines, 1):
                if re.search(r"/home/[a-zA-Z_][a-zA-Z0-9_]*/", line):
                    issues.append(Issue(
                        filepath=filepath,
                        line=i,
                        code="HARDCODE",
                        message="硬编码路径（应使用 $HOME 或 os.path.expanduser）",
                        severity=Severity.FIXABLE,
                        rule_name=self.name,
                        fixable=True,
                    ))
        except (OSError, UnicodeDecodeError):
            pass
        return issues

    def fix(self, filepath: str, issue: Issue) -> bool:
        """替换行内的硬编码路径"""
        home = os.environ.get("HOME", "/home/xiaobai")
        try:
            import subprocess
            # 用 sed 替换 /home/xiaobai/ → $HOME/
            result = subprocess.run(
                ["sed", "-i", f"{issue.line}s|/home/[a-zA-Z_][a-zA-Z0-9_]*/|{home}/|g", filepath],
                capture_output=True, text=True, timeout=10,
            )
            return result.returncode == 0
        except Exception:
            return False
