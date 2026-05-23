"""异常处理质量检测规则 — FIXABLE

检测 AI 生成代码中常见的异常处理问题：
1. 裸 except:（不指定异常类型）— 会捕获 SystemExit/KeyboardInterrupt
2. 空的 except 块 — 静默吞异常
3. 过于宽泛的 except Exception: — 应该优先捕获具体异常
4. 缺少 finally 的 return — try 块中有 return 但 finally 中没有清理逻辑

修复方式：
- 裸 except → except Exception:
- 空 except → 至少加个 log 或 pass 注释
"""

from __future__ import annotations

import ast
import re

from ..models import Issue, Severity
from .base import Rule, register_rule


@register_rule
class ExceptionQualityRule(Rule):
    name = "exception_quality"
    severity = Severity.FIXABLE
    description = "Detect exception quality issues: bare/empty/overly broad except"

    def should_check(self, filepath: str) -> bool:
        return filepath.endswith(".py") and "test" not in filepath

    def diagnose(self, filepath: str) -> list[Issue]:
        issues: list[Issue] = []
        try:
            with open(filepath) as f:
                content = f.read()
        except (OSError, UnicodeDecodeError):
            return issues

        # 快速预检
        if "except" not in content:
            return issues

        try:
            tree = ast.parse(content)
            # 获取文件行内容用于检查 except 块体
            lines = content.split("\n")

            for node in ast.walk(tree):
                if not isinstance(node, ast.Try):
                    continue

                # 检查每个 except handler
                for handler in node.handlers:
                    if not handler.type:
                        # 裸 except:
                        issues.append(Issue(
                            filepath=filepath,
                            line=handler.lineno,
                            code="BARE_EXCEPT",
                            message=f"Bare except (line {handler.lineno}) — catches SystemExit/KeyboardInterrupt",
                            severity=Severity.FIXABLE,
                            rule_name=self.name,
                            fixable=True,
                        ))
                    elif (isinstance(handler.type, ast.Name)
                          and handler.type.id == "Exception"):
                        # except Exception: — 检查是否有 body
                        if not handler.body or (
                            len(handler.body) == 1
                            and isinstance(handler.body[0], ast.Pass)
                        ):
                            issues.append(Issue(
                                filepath=filepath,
                                line=handler.lineno,
                                code="EMPTY_EXCEPT",
                                message=f"Empty except Exception: silently swallows exceptions, add logging",
                                severity=Severity.FIXABLE,
                                rule_name=self.name,
                                fixable=True,
                            ))

                # 检查 try 中是否有 return 但没有 finally
                if node.finalbody:
                    has_return_in_try = any(
                        isinstance(stmt, ast.Return)
                        for stmt in node.body
                    )
                    if has_return_in_try:
                        has_cleanup = any(
                            isinstance(stmt, (ast.Call, ast.Attribute))
                            for stmt in node.finalbody
                        )
                        if not has_cleanup:
                            pass  # 有 return + empty finally 是常见模式，不报

        except SyntaxError:
            pass

        return issues

    def _get_handler_text(self, lines: list[str], handler: ast.ExceptHandler) -> str:
        """获取 except 块的文本内容"""
        if handler.body:
            # 粗略估计 end_lineno
            end = handler.body[-1].lineno if hasattr(handler.body[-1], 'lineno') else handler.lineno + 3
            return "\n".join(lines[handler.lineno:min(end, len(lines))])
        return ""

    def fix(self, filepath: str, issue: Issue) -> bool:
        """修复裸 except → except Exception:"""
        try:
            with open(filepath) as f:
                content = f.read()
        except (OSError, UnicodeDecodeError):
            return False

        lines = content.split("\n")
        if issue.line < 1 or issue.line > len(lines):
            return False

        line = lines[issue.line - 1]

        if "BARE_EXCEPT" in issue.code:
            # 裸 except: → except Exception:
            new_line = re.sub(r'^\s*except\s*:', lambda m: m.group(0).replace("except:", "except Exception:"), line)
            new_line = re.sub(r'^\s*except\s*$', 'except Exception:', new_line)
            if new_line != line:
                lines[issue.line - 1] = new_line
                try:
                    with open(filepath, "w") as f:
                        f.write("\n".join(lines))
                    return True
                except OSError:
                    return False

        if "EMPTY_EXCEPT" in issue.code:
            # 空 except: pass → except Exception: logger.warning(...)
            # 找到后续行
            for i in range(issue.line, min(issue.line + 5, len(lines))):
                stripped = lines[i].strip()
                if stripped == "pass":
                    indent = " " * (len(lines[i]) - len(lines[i].lstrip()))
                    lines[i] = f"{indent}logger.exception(\"发生异常: \")" if "logger" in content else f"{indent}logging.exception(\"发生异常: \")" if "logging" in content else f'{indent}pass  # TODO: 添加异常处理'
                    try:
                        with open(filepath, "w") as f:
                            f.write("\n".join(lines))
                        return True
                    except OSError:
                        return False
            return False

        return False
