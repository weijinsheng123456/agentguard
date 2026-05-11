"""语法检查规则 — BLOCKER"""
from __future__ import annotations

import py_compile

from ..models import Issue, Severity
from .base import Rule, register_rule


@register_rule
class SyntaxCheckRule(Rule):
    name = "syntax_check"
    severity = Severity.BLOCKER
    description = "Python 语法检查（py_compile）"

    def diagnose(self, filepath: str) -> list[Issue]:
        try:
            py_compile.compile(filepath, doraise=True)
            return []
        except py_compile.PyCompileError as e:
            # 从异常中提取行号
            msg = str(e)
            line = 0
            # 尝试解析行号
            for word in msg.split():
                if word.isdigit():
                    line = int(word)
                    break
            return [Issue(
                filepath=filepath,
                line=line,
                code="SYNTAX",
                message=msg.split("\n")[0][:80],
                severity=Severity.BLOCKER,
                rule_name=self.name,
                fixable=False,
            )]
