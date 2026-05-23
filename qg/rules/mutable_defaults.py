"""可变默认参数检测规则 — FIXABLE

检测函数定义中的可变默认参数（list/dict/set），
这是 Python 中常见的陷阱——默认值在函数定义时只创建一次，
后续调用会复用同一个可变对象。

检测模式：
- def foo(a=[]) — 可变列表默认值
- def foo(a={}) — 可变字典默认值
- def foo(a=set()) — 可变集合默认值

修复方式：改为 None + 函数体内初始化
"""

from __future__ import annotations

import ast
import re

from ..models import Issue, Severity
from .base import Rule, register_rule


@register_rule
class MutableDefaultsRule(Rule):
    name = "mutable_defaults"
    severity = Severity.FIXABLE
    description = "Detect mutable default args: def foo(a=[]) → None + body init"

    def should_check(self, filepath: str) -> bool:
        return filepath.endswith(".py") and "test" not in filepath

    def _has_mutable(self, node: ast.expr) -> bool:
        """检查是否是可变默认值"""
        if isinstance(node, ast.List):
            return True
        if isinstance(node, ast.Dict):
            return True
        if isinstance(node, ast.Set):
            return True
        if isinstance(node, ast.Call):
            if isinstance(node.func, ast.Name) and node.func.id in {"list", "dict", "set", "OrderedDict", "defaultdict"}:
                return True
        return False

    def diagnose(self, filepath: str) -> list[Issue]:
        issues: list[Issue] = []
        try:
            with open(filepath) as f:
                content = f.read()
        except (OSError, UnicodeDecodeError):
            return issues

        # 预检
        if "=[]" not in content and "={}" not in content and "=set(" not in content:
            return issues

        try:
            tree = ast.parse(content)
            for node in ast.walk(tree):
                if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    continue

                for default in node.args.defaults:
                    if self._has_mutable(default):
                        # 找到对应的参数名
                        defaults_start = len(node.args.args) - len(node.args.defaults)
                        param_idx = node.args.args.index(
                            [a for a in node.args.args
                             if isinstance(a, ast.arg)][-1]
                        )  # 简化：通过 index 找
                        param_name = "?"
                        for i, d in enumerate(node.args.defaults):
                            if d is default:
                                arg_idx = defaults_start + i
                                if arg_idx < len(node.args.args):
                                    param_name = node.args.args[arg_idx].arg
                                break

                        type_str = "list" if isinstance(default, ast.List) else \
                                   "dict" if isinstance(default, ast.Dict) else \
                                   "set" if isinstance(default, ast.Set) else "mutable"
                        issues.append(Issue(
                            filepath=filepath,
                            line=node.lineno,
                            code="MUTABLE_DEFAULT",
                            message=f"可变默认参数 '{param_name}={type_str}()': 应改为 None + 函数体内初始化",
                            severity=Severity.FIXABLE,
                            rule_name=self.name,
                            fixable=True,
                        ))

        except SyntaxError:
            pass

        return issues

    def fix(self, filepath: str, issue: Issue) -> bool:
        """自动修复可变默认参数"""
        try:
            with open(filepath) as f:
                content = f.read()
        except (OSError, UnicodeDecodeError):
            return False

        # 解析问题行找到具体的参数
        lines = content.split("\n")
        if issue.line < 1 or issue.line > len(lines):
            return False

        line = lines[issue.line - 1]

        # 提取参数名和类型
        import re
        param_match = re.search(r"'(\w+)'", issue.message)
        if not param_match:
            return False
        param_name = param_match.group(1)
        type_match = re.search(r"(\w+)\(\)", issue.message)
        type_name = type_match.group(1) if type_match else "list"

        # 找到函数定义范围
        # 简单的逐行替换
        # 替换 "param_name=[]" 为 "param_name=None"
        # 替换 "param_name={}" 为 "param_name=None"
        import re
        old_patterns = [
            f"{param_name}=[]",
            f"{param_name}=[ ]]",
            f"{param_name}={{}}",
            f"{param_name}=set()",
            f"{param_name}=list()",
            f"{param_name}=dict()",
            f"{param_name}=OrderedDict()",
        ]

        new_line = line
        found = False
        for old in old_patterns:
            if old in line:
                new_line = line.replace(old, f"{param_name}=None")
                found = True
                break

        if not found:
            return False

        lines[issue.line - 1] = new_line
        try:
            with open(filepath, "w") as f:
                f.write("\n".join(lines))
            return True
        except OSError:
            return False
