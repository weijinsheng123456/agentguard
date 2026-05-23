"""危险API调用检测规则 — BLOCKER

检测代码中的危险函数调用，这些在AI生成的代码中常见：
- eval() / exec() — 任意代码执行
- __import__() — 动态导入
- os.system() / os.popen() — shell注入
- subprocess.Popen(shell=True) — shell注入
- pickle.loads() — 反序列化漏洞

使用AST检测，避免注释/文档字符串中的误报。
"""

from __future__ import annotations

import ast

from ..models import Issue, Severity
from .base import Rule, register_rule

# 危险调用模式：(模块名, 函数名, 描述)
DANGEROUS_CALLS: list[tuple[list[str], str, str, str]] = [
    # (模块路径, 函数名, 代码显示, 描述)
    ([], "eval", "eval(...)", "任意代码执行 ❌"),
    ([], "exec", "exec(...)", "任意代码执行 ❌"),
    ([], "__import__", "__import__(...)", "动态导入（可能加载恶意模块）⚠️"),
    (["os"], "system", "os.system()", "Shell命令注入 ❌"),
    (["os"], "popen", "os.popen()", "Shell命令注入 ❌"),
    (["subprocess"], "Popen", "subprocess.Popen(shell=True)", "需检查shell=True参数"),
    (["subprocess"], "call", "subprocess.call(shell=True)", "需检查shell=True参数"),
    (["subprocess"], "run", "subprocess.run(shell=True)", "需检查shell=True参数"),
    (["pickle"], "loads", "pickle.loads()", "反序列化漏洞 ❌"),
    (["pickle"], "load", "pickle.load()", "反序列化漏洞 ❌"),
]

# 排除目录
EXCLUDE_DIRS = ["test", "tests", "__pycache__", ".git", "venv", ".venv", "node_modules", "backups"]


@register_rule
class UnsafeApiRule(Rule):
    name = "unsafe_api"
    severity = Severity.BLOCKER
    description = "Detect dangerous API calls: eval/exec/shell injection/deserialization"

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
                if not isinstance(node, ast.Call):
                    continue

                func = node.func

                # 情况1: 直接函数调用 eval(...)
                if isinstance(func, ast.Name):
                    func_name = func.id
                    for mod_path, name, code, desc in DANGEROUS_CALLS:
                        if not mod_path and func_name == name:
                            # __import__ 带硬编码字符串参数（如 __import__("modal")）是安全的包存在性检查
                            if name == "__import__" and node.args and isinstance(node.args[0], ast.Constant) and isinstance(node.args[0].value, str):
                                continue
                            issues.append(Issue(
                                filepath=filepath,
                                line=node.lineno,
                                code=f"UNSAFE_{name.upper()}",
                                message=f"{code} — {desc}",
                                severity=Severity.BLOCKER,
                                rule_name=self.name,
                                fixable=False,
                            ))

                # 情况2: 属性调用 os.system(...)
                elif isinstance(func, ast.Attribute):
                    attr_name = func.attr
                    # 逐层展开属性链
                    mod_parts = []
                    obj = func.value
                    while isinstance(obj, ast.Attribute):
                        mod_parts.append(obj.attr)
                        obj = obj.value
                    if isinstance(obj, ast.Name):
                        mod_parts.append(obj.id)
                    mod_parts.reverse()  # 现在 mod_parts 是 ["os"] 或 ["subprocess"]

                    for mod_path, name, code, desc in DANGEROUS_CALLS:
                        if mod_path and attr_name == name:
                            # 检查模块路径是否匹配
                            if mod_parts == mod_path:
                                # 额外检查 subprocess 的 shell=True
                                if name == "Popen" or name == "call" or name == "run":
                                    shell_keyword = False
                                    for kw in node.keywords:
                                        if kw.arg == "shell" and isinstance(kw.value, ast.Constant) and kw.value.value is True:
                                            shell_keyword = True
                                            break
                                    if not shell_keyword:
                                        continue  # 没有 shell=True 不算危险

                                issues.append(Issue(
                                    filepath=filepath,
                                    line=node.lineno,
                                    code=f"UNSAFE_{name.upper()}",
                                    message=f"{code} — {desc}",
                                    severity=Severity.BLOCKER,
                                    rule_name=self.name,
                                    fixable=False,
                                ))

        except SyntaxError:
            pass

        return issues
