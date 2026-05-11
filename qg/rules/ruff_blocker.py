"""ruff BLOCKER 规则 — F821(未定义变量), E999(语法错误)。

批量模式：在目录级运行 ruff，比逐文件快 10-50 倍。
"""
from __future__ import annotations

import json
import subprocess

from ..models import Issue, Severity
from .base import BatchRule, register_rule


@register_rule
class RuffBlockerRule(BatchRule):
    name = "ruff_blocker"
    severity = Severity.BLOCKER
    description = "ruff 阻断级检查：F821(未定义变量) E999(语法错误)"

    CODES = ["F821", "E999"]

    def _run_ruff(self, target: str) -> list[Issue]:
        """对单个目标运行 ruff，返回问题列表"""
        issues = []
        try:
            result = subprocess.run(
                ["ruff", "check", f"--select={','.join(self.CODES)}", "--output-format=json", target],
                capture_output=True, text=True, timeout=60,
            )
            if result.stdout.strip() and result.stdout.strip() != "[]":
                data = json.loads(result.stdout)
                for item in data:
                    issues.append(Issue(
                        filepath=item["filename"],
                        line=item["location"]["row"],
                        code=item["code"],
                        message=item["message"][:80],
                        severity=Severity.BLOCKER,
                        rule_name=self.name,
                        fixable=False,
                    ))
        except (subprocess.TimeoutExpired, json.JSONDecodeError, FileNotFoundError):
            pass
        return issues

    def diagnose_batch(self, scan_dirs: list[str]) -> list[Issue]:
        """批量检查多个目录（快）"""
        all_issues = []
        for d in scan_dirs:
            issues = self._run_ruff(d)
            all_issues.extend(issues)
        return all_issues
