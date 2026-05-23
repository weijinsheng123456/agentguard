"""SQL注入检测规则 — BLOCKER

检测通过 f-string / format() / % 拼接 SQL 查询的模式，
这些在 AI 生成的代码中常见且危险。

检测模式：
- execute(f"SELECT ... {var}") — f-string 拼接 SQL
- execute("SELECT ... %s" % var) — % 格式化
- execute("SELECT {}".format(var)) — .format() 拼接
- raw_sql / cursor.execute 直接拼接变量

使用 AST 分析，区分安全的参数化查询：
- execute("SELECT ... %s", (param,)) — ✅ 参数化安全
- execute("SELECT ... ?", [param])     — ✅ 参数化安全
"""

from __future__ import annotations

import ast
import re

from ..models import Issue, Severity
from .base import Rule, register_rule

# SQL相关函数名
SQL_FUNCS = {"execute", "executemany", "executescript", "query", "raw_sql", "session.query"}

# 排除目录
EXCLUDE_DIRS = ["test", "tests", "__pycache__", ".git", "venv", ".venv", "node_modules", "backups"]


@register_rule
class SqlInjectionRule(Rule):
    name = "sql_injection"
    severity = Severity.BLOCKER
    description = "检测SQL注入风险：f-string/format拼接SQL"

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

        # 快速预检：如果没有 SQL 关键字，跳过
        if not re.search(r'\b(execute|executemany|query|raw_sql|session\.query)\b', content, re.IGNORECASE):
            return issues

        try:
            tree = ast.parse(content)
            for node in ast.walk(tree):
                if not isinstance(node, ast.Call):
                    continue

                func = self._get_call_name(node)
                if not func or func not in SQL_FUNCS:
                    continue

                # 检查第一个参数是否有可能的拼接模式
                if not node.args:
                    continue
                first_arg = node.args[0]

                # f-string 检测: ast.JoinedStr
                if isinstance(first_arg, ast.JoinedStr):
                    # 检查是否有变量插值
                    has_interpolation = any(
                        isinstance(v, (ast.FormattedValue, ast.Name, ast.Attribute))
                        for v in first_arg.values
                    )
                    if has_interpolation:
                        # 检查第二个参数是否存在（参数化查询）
                        has_params = len(node.args) >= 2 or any(
                            kw.arg in ("params", "parameters") for kw in node.keywords
                        )
                        if not has_params:
                            issues.append(Issue(
                                filepath=filepath,
                                line=node.lineno,
                                code="SQLI_FSTRING",
                                message=f"f-string 拼接 SQL 查询: {func}(f\"...\") — 存在注入风险",
                                severity=Severity.BLOCKER,
                                rule_name=self.name,
                                fixable=False,
                            ))

                # % 格式化检测
                elif isinstance(first_arg, ast.BinOp) and isinstance(first_arg.op, ast.Mod):
                    issues.append(Issue(
                        filepath=filepath,
                        line=node.lineno,
                        code="SQLI_PERCENT",
                        message=f"SQL 查询使用 % 格式化: {func}() — 存在注入风险，应使用参数化查询",
                        severity=Severity.BLOCKER,
                        rule_name=self.name,
                        fixable=False,
                    ))

                # .format() 调用
                elif isinstance(first_arg, ast.Call):
                    if self._is_format_call(first_arg):
                        issues.append(Issue(
                            filepath=filepath,
                            line=node.lineno,
                            code="SQLI_FORMAT",
                            message=f"SQL 查询使用 .format(): {func}() — 存在注入风险，应使用参数化查询",
                            severity=Severity.BLOCKER,
                            rule_name=self.name,
                            fixable=False,
                        ))

                # 字符串变量拼接（如 query + condition）
                elif isinstance(first_arg, ast.BinOp) and isinstance(first_arg.op, ast.Add):
                    issues.append(Issue(
                        filepath=filepath,
                        line=node.lineno,
                        code="SQLI_CONCAT",
                        message=f"SQL 查询字符串拼接: {func}() — 存在注入风险",
                        severity=Severity.BLOCKER,
                        rule_name=self.name,
                        fixable=False,
                    ))

        except SyntaxError:
            pass

        return issues

    def _get_call_name(self, node: ast.Call) -> str | None:
        """获取调用名，处理属性链如 cursor.execute(...)"""
        if isinstance(node.func, ast.Name):
            return node.func.id
        elif isinstance(node.func, ast.Attribute):
            return node.func.attr
        return None

    def _is_format_call(self, node: ast.Call) -> bool:
        """判断是否是 .format() 调用"""
        return (isinstance(node.func, ast.Attribute)
                and node.func.attr == "format"
                and isinstance(node.func.value, ast.Constant))
