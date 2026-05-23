"""ruff FIXABLE 规则 — F401(未用import) F841(未用变量) E711/E712(None比较)。

批量模式：在目录级运行 ruff，比逐文件快 10-50 倍。
"""
from __future__ import annotations

import json
import subprocess

from ..models import Issue, Severity
from .base import BatchRule, register_rule


@register_rule
class RuffFixableRule(BatchRule):
    name = "ruff_fixable"
    severity = Severity.FIXABLE
    description = "ruff auto-fixable: F401(unused import) F841/E711/E712"

    CODES = ["F401", "F841", "E711", "E712"]

    def diagnose_batch(self, scan_dirs: list[str]) -> list[Issue]:
        """批量检查多个目录"""
        issues = []
        for d in scan_dirs:
            try:
                result = subprocess.run(
                    ["ruff", "check", f"--select={','.join(self.CODES)}", "--output-format=json", d],
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
                            severity=Severity.FIXABLE,
                            rule_name=self.name,
                            fixable=True,
                        ))
            except (subprocess.TimeoutExpired, json.JSONDecodeError, FileNotFoundError):
                pass
        return issues

    def fix(self, filepath: str, issue: Issue) -> bool:
        """使用 ruff --fix 修复整个文件"""
        try:
            result = subprocess.run(
                ["ruff", "check", "--fix", "--quiet", filepath],
                capture_output=True, text=True, timeout=30,
            )
            return True
        except (subprocess.TimeoutExpired, FileNotFoundError):
            return False
