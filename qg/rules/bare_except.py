"""裸 except 检测+修复规则 — FIXABLE"""
from __future__ import annotations
import ast

from .base import Rule, register_rule
from ..models import Issue, Severity


@register_rule
class BareExceptRule(Rule):
    name = "bare_except"
    severity = Severity.FIXABLE
    description = "Bare except (no exception type) → except Exception"

    def diagnose(self, filepath: str) -> list[Issue]:
        issues = []
        try:
            with open(filepath) as f:
                tree = ast.parse(f.read())
            for node in ast.walk(tree):
                if isinstance(node, ast.ExceptHandler) and node.type is None:
                    issues.append(Issue(
                        filepath=filepath,
                        line=node.lineno,
                        code="E722",
                        message="Bare except (specify exception type)",
                        severity=Severity.FIXABLE,
                        rule_name=self.name,
                        fixable=True,
                    ))
        except SyntaxError:
            pass  # 语法错误由 SyntaxCheckRule 处理
        return issues

    def fix(self, filepath: str, issue: Issue) -> bool:
        """将行内的 except: 替换为 except Exception:"""
        try:
            import subprocess
            result = subprocess.run(
                ["sed", "-i", f"{issue.line}s/^\\([[:space:]]*\\)except:/\\1except Exception:/", filepath],
                capture_output=True, text=True, timeout=10,
            )
            return result.returncode == 0
        except Exception:
            return False
