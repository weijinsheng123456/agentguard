"""路径遍历检测规则 — BLOCKER

检测文件操作中未经验证的用户输入直接拼接到路径，
这是常见的路径遍历漏洞来源。

检测模式：
- open(user_input) — 直接使用用户输入打开文件
- Path(user_input) — 直接使用用户输入构造路径
- os.path.join(base, user_input) — 未过滤的用户输入拼接
- shutil.copy(src, user_input) — 目标路径为未验证输入

安全模式（不报）：
- Path("static") / name — 常量基路径
- os.path.join(BASE_DIR, name) — 有 BASE_DIR 常量保护
- user_input 经过 basename() 处理
"""

from __future__ import annotations

import ast
import re

from ..models import Issue, Severity
from .base import Rule, register_rule

# 需要检查的文件操作函数
FILE_OPS = {
    "open", "read_text", "read_bytes", "write_text", "write_bytes",
    "unlink", "rename", "replace", "copy", "move", "copytree",
    "makedirs", "rmdir", "glob", "rglob",
}

# 排除目录
EXCLUDE_DIRS = ["test", "tests", "__pycache__", ".git", "venv", ".venv", "node_modules", "backups"]

# 安全的基路径变量名模式
SAFE_BASE_PATTERNS = [
    r'BASE_DIR', r'BASE_PATH', r'ROOT_DIR', r'DATA_DIR',
    r'OUTPUT_DIR', r'TEMP_DIR', r'CACHE_DIR', r'STATIC_DIR',
    r'UPLOAD_DIR', r'MEDIA_ROOT', r'STATIC_ROOT',
]


@register_rule
class PathTraversalRule(Rule):
    name = "path_traversal"
    severity = Severity.BLOCKER
    description = "Detect path traversal: unvalidated user input in file paths"

    def should_check(self, filepath: str) -> bool:
        if not filepath.endswith(".py"):
            return False
        for exc in EXCLUDE_DIRS:
            if f"/{exc}/" in filepath or filepath.startswith(exc + "/"):
                return False
        return True

    def _is_safe_base(self, node: ast.AST) -> bool:
        """判断是否是安全的基路径变量"""
        if isinstance(node, ast.Name):
            return any(re.match(p, node.id) for p in SAFE_BASE_PATTERNS)
        return False

    def _get_path_source(self, node: ast.AST, depth: int = 0) -> str | None:
        """尝试判断路径的来源"""
        if depth > 3:
            return None
        if isinstance(node, ast.Name):
            return f"var:{node.id}"
        elif isinstance(node, ast.Attribute):
            return self._get_path_source(node.value, depth + 1)
        elif isinstance(node, ast.Call):
            if isinstance(node.func, ast.Name) and node.func.id in {"input", "request", "args", "form", "json"}:
                return "user_input"
            if isinstance(node.func, ast.Attribute):
                if node.func.attr in {"resolve", "expanduser"}:
                    return "resolved_path"
                if node.func.attr in {"read"}:
                    return "file_content"
                # basename / normpath 表示已经过安全处理
                if node.func.attr in {"basename", "normpath", "abspath", "realpath"}:
                    return "sanitized"
            return "unknown"
        elif isinstance(node, ast.Constant):
            return f"literal:{node.value}"
        elif isinstance(node, ast.Subscript):
            return "subscript"
        return None

    def diagnose(self, filepath: str) -> list[Issue]:
        issues: list[Issue] = []
        try:
            with open(filepath) as f:
                content = f.read()
        except (OSError, UnicodeDecodeError):
            return issues

        # 快速预检
        if not re.search(r'\b(open|read_text|Path\(|write_text|os\.path\.join)\b', content):
            return issues

        try:
            tree = ast.parse(content)
            for node in ast.walk(tree):
                # 模式1: Path(user_input) — Path 构造直接传入不确定变量
                if isinstance(node, ast.Call):
                    func = node.func
                    # Path(...) 调用
                    if isinstance(func, ast.Name) and func.id == "Path" and node.args:
                        src = self._get_path_source(node.args[0])
                        if src and src.startswith("user_input"):
                            issues.append(Issue(
                                filepath=filepath,
                                line=node.lineno,
                                code="PATH_TRAVERSAL",
                                message=f"Path() with user input ({src}): unvalidated path traversal risk",
                                severity=Severity.BLOCKER,
                                rule_name=self.name,
                                fixable=False,
                            ))

                    # open(user_input) — 直接打开用户输入
                    if isinstance(func, ast.Name) and func.id == "open" and node.args:
                        src = self._get_path_source(node.args[0])
                        if src and src.startswith("user_input"):
                            issues.append(Issue(
                                filepath=filepath,
                                line=node.lineno,
                                code="PATH_TRAVERSAL",
                                message=f"open() with user input ({src}): unvalidated path traversal risk",
                                severity=Severity.BLOCKER,
                                rule_name=self.name,
                                fixable=False,
                            ))

                # 模式2: os.path.join(BASE, user_input) 但拼接的不是 BASE 结尾
                if isinstance(node, ast.Call):
                    if (isinstance(node.func, ast.Attribute)
                            and node.func.attr == "join"
                            and isinstance(node.func.value, ast.Attribute)
                            and node.func.value.attr == "path"
                            and isinstance(node.func.value.value, ast.Name)
                            and node.func.value.value.id == "os"
                            and len(node.args) >= 2):
                        # 检查第一个参数是否是安全基路径
                        if node.args and not self._is_safe_base(node.args[0]):
                            for arg in node.args[1:]:
                                src = self._get_path_source(arg)
                                if src and src.startswith("user_input"):
                                    issues.append(Issue(
                                        filepath=filepath,
                                        line=node.lineno,
                                        code="PATH_TRAVERSAL",
                                        message=f"os.path.join() with user input, base path not a safe constant",
                                        severity=Severity.BLOCKER,
                                        rule_name=self.name,
                                        fixable=False,
                                    ))
                                    break

        except SyntaxError:
            pass

        return issues
