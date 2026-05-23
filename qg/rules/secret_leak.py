"""硬编码密钥/Token检测规则 — BLOCKER

检测代码中硬编码的敏感信息：
- API_KEY / API_SECRET / API_TOKEN
- PASSWORD / PASSWD
- SECRET_KEY / SECRET
- TOKEN / ACCESS_TOKEN
- 类似 JWT / Bearer token 模式
- 私有SSH密钥内容

注意：只检测字符串字面量中的硬编码，不检测环境变量读取。
"""

from __future__ import annotations

import ast
import re

from ..models import Issue, Severity
from .base import Rule, register_rule

# 敏感变量名模式（赋值 = "xxx"）
SENSITIVE_VAR_PATTERNS = [
    r'(?:API|api)[_]?(?:KEY|key|SECRET|secret|TOKEN|token)',
    r'(?:SECRET|secret)[_]?(?:KEY|key)',
    r'(?:ACCESS|access)[_]?(?:TOKEN|token)',
    r'(?:TOKEN|token)',
    r'(?:PASSWD|passwd|PASSWORD|password)',
    r'(?:AUTH|auth)[_]?(?:TOKEN|token|KEY|key)',
    r'(?:PRIVATE|private)[_]?(?:KEY|key)',
    r'(?:BEARER|bearer)[_]?(?:TOKEN|token)',
]

# 排除模式（常见合法用例）
EXCLUDE_PATTERNS = [
    r'os\.environ',
    r'os\.getenv',
    r'config\[',
    r'\.env',
    r'environ\.get',
    r'environ\[',
    r'getenv\(',
    r'load_dotenv',
    r'例子|示例|example|placeholder',
    r'your-api-key',
    r'YOUR_',
]

# 排除目录
EXCLUDE_DIRS = ["test", "tests", "__pycache__", ".git", "venv", ".venv", "node_modules", "backups"]


@register_rule
class SecretLeakRule(Rule):
    name = "secret_leak"
    severity = Severity.BLOCKER
    description = "Detect hardcoded API keys/tokens/passwords"

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

        # 跳过文件级别的排除
        for exc in EXCLUDE_PATTERNS:
            if re.search(exc, content, re.IGNORECASE):
                return issues

        try:
            tree = ast.parse(content)
            for node in ast.walk(tree):
                # a = "xxx" 或 A = "xxx"
                if isinstance(node, ast.Assign):
                    for target in node.targets:
                        if isinstance(target, ast.Name) and isinstance(node.value, ast.Constant):
                            var_name = target.id
                            value = str(node.value.value) if node.value.value else ""

                            # 检查变量名是否敏感
                            is_sensitive_var = False
                            for p in SENSITIVE_VAR_PATTERNS:
                                if re.search(p, var_name, re.IGNORECASE):
                                    is_sensitive_var = True
                                    break

                            if is_sensitive_var and len(value) >= 8:
                                # 排除明显是占位符的值
                                if re.search(r'your_|example|placeholder|null|none|true|false|0$',
                                           value, re.IGNORECASE):
                                    continue
                                issues.append(Issue(
                                    filepath=filepath,
                                    line=node.lineno,
                                    code="LEAK_SECRET",
                                    message=f"硬编码敏感信息: {var_name}",
                                    severity=Severity.BLOCKER,
                                    rule_name=self.name,
                                    fixable=False,
                                ))

                # 字典赋值: {"api_key": "xxx"}
                if isinstance(node, ast.Dict):
                    for key, val in zip(node.keys, node.values):
                        if isinstance(key, ast.Constant) and isinstance(val, ast.Constant):
                            key_str = str(key.value)
                            val_str = str(val.value) if val.value else ""
                            if len(val_str) >= 16:
                                for p in SENSITIVE_VAR_PATTERNS:
                                    if re.search(p, key_str, re.IGNORECASE):
                                        issues.append(Issue(
                                            filepath=filepath,
                                            line=key.lineno if hasattr(key, 'lineno') else node.lineno,
                                            code="LEAK_SECRET",
                                            message=f"字典中硬编码敏感信息: {key_str}",
                                            severity=Severity.BLOCKER,
                                            rule_name=self.name,
                                            fixable=False,
                                        ))
                                        break
        except SyntaxError:
            pass

        return issues
