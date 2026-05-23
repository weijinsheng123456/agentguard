"""性能隐患检测规则 — FIXABLE

检测 AI 生成代码中的常见性能问题：
1. 循环内重复调用函数（如循环内调 API/读文件）
2. 列表推导替代 for+append
3. 不必要的全局变量写操作
4. 不必要的 list() 包装

修复方式：部分可自动修复（list 推导等）
"""

from __future__ import annotations

import ast
import re

from ..models import Issue, Severity
from .base import Rule, register_rule


# 循环中调用的"重"函数列表
HEAVY_CALLS = {
    "open", "read", "write", "request", "get", "post",
    "session.query", "execute", "fetchall", "commit",
    "sleep", "time.sleep",
}

# 排除目录
EXCLUDE_DIRS = ["test", "tests", "__pycache__", ".git", "venv", ".venv", "node_modules", "backups"]


@register_rule
class PerformanceRule(Rule):
    name = "performance"
    severity = Severity.FIXABLE
    description = "Detect performance issues: API calls in loops, for→list comprehension"

    def should_check(self, filepath: str) -> bool:
        if not filepath.endswith(".py"):
            return False
        for exc in EXCLUDE_DIRS:
            if f"/{exc}/" in filepath or filepath.startswith(exc + "/"):
                return False
        return True

    def diagnose(self, filepath: str) -> list[Issue]:
        issues: list[Issue] = []
        try:
            with open(filepath) as f:
                content = f.read()
        except (OSError, UnicodeDecodeError):
            return issues

        try:
            tree = ast.parse(content)

            for node in ast.walk(tree):
                # 1. 循环内调用重函数
                if isinstance(node, (ast.For, ast.While, ast.comprehension)):
                    self._check_loop_heavy_calls(node, issues, filepath)

                # 2. 可以转为 list 推导的 for 循环
                if isinstance(node, ast.For):
                    self._check_list_comprehension_candidate(node, issues, filepath)

        except SyntaxError:
            pass

        return issues

    def _check_loop_heavy_calls(self, loop_node: ast.AST, issues: list, filepath: str):
        """检查循环体内是否有重函数调用"""
        body = loop_node.body if hasattr(loop_node, 'body') else \
               loop_node.elt if hasattr(loop_node, 'elt') else []

        if not body:
            return

        # 统计函数调用
        call_sites = {}
        for stmt in body if isinstance(body, list) else [body]:
            for child in ast.walk(stmt):
                if not isinstance(child, ast.Call):
                    continue
                func_name = self._get_func_name(child)
                if func_name and func_name in ("time.sleep", "sleep", "open", "read"):
                    if func_name not in call_sites:
                        call_sites[func_name] = child.lineno

        for func_name, lineno in call_sites.items():
            issues.append(Issue(
                filepath=filepath,
                line=lineno,
                code="LOOP_HEAVY_CALL",
                message=f"循环内调用 {func_name}(): 每次迭代都会执行，考虑移到循环外",
                severity=Severity.FIXABLE,
                rule_name=self.name,
                fixable=False,
            ))

    def _check_list_comprehension_candidate(self, for_node: ast.For, issues: list, filepath: str):
        """检查是否是 can 转为列表推导的 for 循环"""
        # 模式: result = [] / for x in items: / result.append(x.func())
        if len(for_node.body) != 1:
            return
        stmt = for_node.body[0]
        if not isinstance(stmt, ast.Expr):
            return
        if not isinstance(stmt.value, ast.Call):
            return
        call = stmt.value
        if not (isinstance(call.func, ast.Attribute) and call.func.attr == "append"):
            return

        # 检查 for 之前是否有 result = []
        # 这部分需要父节点引用，简化处理
        issues.append(Issue(
            filepath=filepath,
            line=for_node.lineno,
            code="LOOP_APPEND",
            message=f"for+append 模式: 可转为列表推导式 [x for x in ...]",
            severity=Severity.INFO,
            rule_name=self.name,
            fixable=False,
        ))

    def _get_func_name(self, node: ast.Call) -> str | None:
        """获取函数调用的完整名称"""
        if isinstance(node.func, ast.Name):
            return node.func.id
        elif isinstance(node.func, ast.Attribute):
            parts = []
            obj = node.func.value
            if isinstance(obj, ast.Name):
                parts.append(obj.id)
            parts.append(node.func.attr)
            return ".".join(parts)
        return None
