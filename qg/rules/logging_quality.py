"""日志规范检测规则 — FIXABLE

检测代码中使用 print() 代替 logging 的常见情况。
AI 生成的代码普遍用 print 调试，生产代码应该用 logging。

检测模式：
- print(f"...") — 信息性打印
- print("ERROR: ...") — 错误打印
- print("DEBUG: ...") — 调试打印

例外（不报）：
- CLI 工具/脚本中的 print（没有 import logging）
- 测试文件中的 print
- print() 用于进度显示（end='' 或 flush=True）
"""

from __future__ import annotations

import ast
import re

from ..models import Issue, Severity
from .base import Rule, register_rule


@register_rule
class LoggingQualityRule(Rule):
    name = "logging_quality"
    severity = Severity.INFO
    description = "Detect print() used instead of logging"

    def should_check(self, filepath: str) -> bool:
        return filepath.endswith(".py") and "test" not in filepath

    def diagnose(self, filepath: str) -> list[Issue]:
        issues: list[Issue] = []
        try:
            with open(filepath) as f:
                content = f.read()
        except (OSError, UnicodeDecodeError):
            return issues

        # 检查是否有 import logging
        has_logging = "import logging" in content or "from logging" in content
        if not has_logging:
            return issues  # 没有 logging 模块，不做强制要求

        # 快速预检
        if "print(" not in content:
            return issues

        try:
            tree = ast.parse(content)
            for node in ast.walk(tree):
                if not isinstance(node, ast.Call):
                    continue
                if not (isinstance(node.func, ast.Name) and node.func.id == "print"):
                    continue

                # 跳过进度显示（flush=True 或 end=''）
                has_flush = any(
                    kw.arg == "flush" and isinstance(kw.value, ast.Constant) and kw.value.value is True
                    for kw in node.keywords
                )
                has_end = any(
                    kw.arg == "end" for kw in node.keywords
                )
                if has_flush or has_end:
                    continue

                # 获取打印内容
                if node.args:
                    arg = node.args[0]
                    if isinstance(arg, ast.Constant) and isinstance(arg.value, str):
                        val = arg.value
                        # 判断是否是调试/信息打印
                        if any(val.lower().startswith(p) for p in ("error", "debug", "info", "warning", "trace")):
                            issues.append(Issue(
                                filepath=filepath,
                                line=node.lineno,
                                code="PRINT_LOGGING",
                                message=f"使用 print() 替代 logging: 建议用 logging.{val.split()[0].lower()}()",
                                severity=Severity.INFO,
                                rule_name=self.name,
                                fixable=True,
                            ))
                        elif len(val) > 40:
                            issues.append(Issue(
                                filepath=filepath,
                                line=node.lineno,
                                code="PRINT_LOGGING",
                                message=f"使用 print() 输出较长的内容（{len(val)}字符），建议用 logging.info()",
                                severity=Severity.INFO,
                                rule_name=self.name,
                                fixable=True,
                            ))

        except SyntaxError:
            pass

        return issues
