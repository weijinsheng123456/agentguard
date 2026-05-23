"""TODO/注释残留检测规则 — FIXABLE

检测 AI 生成代码中常见的占位注释残留：
1. TODO/FIXME/HACK 残留
2. "这里需要..." / "需要补充..." 等中文注释
3. "implement later" / "add proper handling" 等英文占位

这些注释说明代码不完整或存在已知未修复的问题。
"""

from __future__ import annotations

import ast
import re

from ..models import Issue, Severity
from .base import Rule, register_rule


# 占位注释模式
PLACEHOLDER_PATTERNS = [
    (r'TODO\b', "TODO 残留"),
    (r'FIXME\b', "FIXME 残留"),
    (r'HACK\b', "HACK 残留 — 临时解决方案"),
    (r'XXX\b', "XXX 标记"),
    (r'需[要]?\s*(补充|完善|实现|添加|完成)', "中文占位注释"),
    (r'(implement|later|proper|somehow|someday)', "英文占位注释"),
    (r'这里[应].*[逻辑|处理|代码]', "不完整注释"),
]


@register_rule
class PlaceholderCheckRule(Rule):
    name = "placeholder_check"
    severity = Severity.FIXABLE
    description = "检测 TODO/FIXME/HACK 等占位注释残留"

    def should_check(self, filepath: str) -> bool:
        return filepath.endswith(".py")

    def diagnose(self, filepath: str) -> list[Issue]:
        issues: list[Issue] = []
        try:
            with open(filepath) as f:
                content = f.read()
        except (OSError, UnicodeDecodeError):
            return issues

        if not any(re.search(p[0], content, re.IGNORECASE) for p in PLACEHOLDER_PATTERNS):
            return issues

        lines = content.split("\n")
        for i, line in enumerate(lines, 1):
            stripped = line.strip()
            if not stripped.startswith("#"):
                continue

            for pattern, desc in PLACEHOLDER_PATTERNS:
                if re.search(pattern, stripped, re.IGNORECASE):
                    issues.append(Issue(
                        filepath=filepath,
                        line=i,
                        code="PLACEHOLDER_TODO",
                        message=f"占位注释: {desc} — \"{stripped[:60].strip()}\"",
                        severity=Severity.FIXABLE,
                        rule_name=self.name,
                        fixable=False,
                    ))
                    break  # 一行只报一次

        return issues
