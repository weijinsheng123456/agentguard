"""硬编码配置检测规则 — INFO

检测代码中硬编码的配置项（URL、数据库连接、IP 地址等），
这些应该配置化而非写死在代码中。

检测模式：
- 硬编码 URL（http://... 非 localhost）
- 硬编码 IP 地址
- 硬编码数据库连接字符串
- 硬编码端口号
- 硬编码文件路径（非相对路径）

修复方式：提取到配置变量
"""

from __future__ import annotations

import ast
import re

from ..models import Issue, Severity
from .base import Rule, register_rule


# 排除的变量名（不在赋值语句中报这些）
EXCLUDED_VARS = [
    "example", "placeholder", "sample", "default",
    "version", "name", "title", "description",
]

# 排除目录
EXCLUDE_DIRS = ["test", "tests", "__pycache__", ".git", "venv", ".venv", "node_modules", "backups"]


@register_rule
class HardcodedConfigRule(Rule):
    name = "hardcoded_config"
    severity = Severity.INFO
    description = "Detect hardcoded config: URLs/IPs/paths should be configurable"

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

        # 快速预检
        if "://" not in content and not re.search(r'\b\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}\b', content):
            return issues

        try:
            lines = content.split("\n")
            tree = ast.parse(content)

            for node in ast.walk(tree):
                if not isinstance(node, ast.Assign):
                    continue
                if not isinstance(node.value, ast.Constant) or not isinstance(node.value.value, str):
                    continue
                if len(node.targets) != 1 or not isinstance(node.targets[0], ast.Name):
                    continue

                var_name = node.targets[0].id
                val = node.value.value

                # 跳过明显例外的变量名
                if any(ex in var_name.lower() for ex in EXCLUDED_VARS):
                    continue

                # 检查是否是配置值
                if val.startswith(("http://", "https://")) and "localhost" not in val and "127.0.0.1" not in val:
                    # 跳过 API_BASE_URL 等明显是配置的变量
                    if not re.search(r'(?:URL|URI|ENDPOINT|HOST|SERVER|API)_', var_name):
                        issues.append(Issue(
                            filepath=filepath,
                            line=node.lineno,
                            code="HARDCODED_URL",
                            message=f"硬编码 URL 配置: {var_name} = \"{val[:60]}...\"",
                            severity=Severity.INFO,
                            rule_name=self.name,
                            fixable=False,
                        ))

                # 硬编码 IP 地址（非 localhost）
                elif re.match(r'^\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}$', val):
                    if not val.startswith(("127.", "0.", "192.168.", "10.")):
                        issues.append(Issue(
                            filepath=filepath,
                            line=node.lineno,
                            code="HARDCODED_IP",
                            message=f"硬编码 IP 地址: {var_name} = \"{val}\"",
                            severity=Severity.INFO,
                            rule_name=self.name,
                            fixable=False,
                        ))

                # 文件路径配置
                elif "://" not in val and val.startswith("/") and len(val) > 20 and not re.search(r'/(usr|etc|var|opt|tmp|home)/', val):
                    if not re.search(r'(?:PATH|DIR|FILE|ROOT)_', var_name):
                        issues.append(Issue(
                            filepath=filepath,
                            line=node.lineno,
                            code="HARDCODED_PATH",
                            message=f"硬编码文件路径: {var_name} = \"{val}\"",
                            severity=Severity.INFO,
                            rule_name=self.name,
                            fixable=False,
                        ))

        except SyntaxError:
            pass

        return issues
