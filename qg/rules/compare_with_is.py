"""is比较检测规则 — FIXABLE

检测用 `is` 比较字符串/数字字面量，应使用 `==`。
Python 中 `is` 是比较对象身份，不是值相等。

检测模式：
- x is "string" — 应改为 x == "string"
- x is None — ✅ 正确（None 是单例）
- x is True — ✅ 正确（True/False 是单例）
- x is 42 — 应改为 x == 42（小整数被缓存但不保证）
"""

from __future__ import annotations

import ast
import re

from ..models import Issue, Severity
from .base import Rule, register_rule


@register_rule
class CompareWithIsRule(Rule):
    name = "compare_with_is"
    severity = Severity.FIXABLE
    description = "检测用 is 比较字符串/数字字面量，应使用 =="

    def should_check(self, filepath: str) -> bool:
        return filepath.endswith(".py")

    def diagnose(self, filepath: str) -> list[Issue]:
        issues: list[Issue] = []
        try:
            with open(filepath) as f:
                content = f.read()
        except (OSError, UnicodeDecodeError):
            return issues

        if " is " not in content:
            return issues

        try:
            tree = ast.parse(content)
            for node in ast.walk(tree):
                if not isinstance(node, ast.Compare):
                    continue
                if not any(isinstance(op, ast.Is) for op in node.ops):
                    continue

                for i, op in enumerate(node.ops):
                    if not isinstance(op, ast.Is):
                        continue

                    # 获取比较的右边值
                    right_idx = min(i, len(node.comparators) - 1)
                    right = node.comparators[right_idx]

                    # is None / is True / is False — 正确的用法
                    if isinstance(right, ast.Constant) and right.value is None:
                        continue
                    if isinstance(right, ast.Name) and right.id in {"True", "False", "None"}:
                        continue

                    # 其他常量：is "string" / is 42 / is 3.14
                    if isinstance(right, ast.Constant) and isinstance(right.value, (str, int, float)):
                        issues.append(Issue(
                            filepath=filepath,
                            line=node.lineno,
                            code="IS_COMPARE",
                            message=f"用 is 比较 {type(right.value).__name__} 字面量: 应使用 == 而非 is",
                            severity=Severity.FIXABLE,
                            rule_name=self.name,
                            fixable=True,
                        ))

        except SyntaxError:
            pass

        return issues

    def fix(self, filepath: str, issue: Issue) -> bool:
        """修复 is → ==（简单替换）"""
        try:
            with open(filepath) as f:
                content = f.read()
        except (OSError, UnicodeDecodeError):
            return False

        lines = content.split("\n")
        if issue.line < 1 or issue.line > len(lines):
            return False

        old_line = lines[issue.line - 1]

        # 尝试替换 is "xxx" → == "xxx"
        # 以及 is xxx → 是 == xxx（当 xxx 不是 None/True/False）
        import re
        # 不替换 is None / is True / is False
        new_line = re.sub(
            r'\bis\s+(?!"(?:None|True|False)")(["\'])',
            r'== \1',
            old_line
        )
        # 替换 is 42 / is 3.14 等
        new_line = re.sub(
            r'\bis\s+(\d+(?:\.\d+)?)',
            r'== \1',
            new_line
        )

        if new_line != old_line:
            lines[issue.line - 1] = new_line
            try:
                with open(filepath, "w") as f:
                    f.write("\n".join(lines))
                return True
            except OSError:
                return False

        return False
