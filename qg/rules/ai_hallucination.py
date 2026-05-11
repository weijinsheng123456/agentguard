"""AI幻觉/虚假代码模式检测规则 — INFO

检测AI生成代码中常见的"幻觉"模式：
1. 虚假模块/函数引用（检查import是否真的存在）
2. 虚构的文档URL/链接
3. 自我引用的占位注释（"TODO: implement" / "Add your logic here"）
4. 重复的样板代码
5. 明显的"AI插入"标记
"""

from __future__ import annotations

import ast
import re

from ..models import Issue, Severity
from .base import Rule, register_rule

# AI留下痕迹的注释模式
AI_COMMENT_PATTERNS = [
    r'#\s*TODO:\s*implement\s*(the|this|your)',
    r'#\s*Add\s+(your|the)\s+(code|logic|implementation|handler)',
    r'#\s*Implement\s+(the|your|this)\s+(function|method|logic)',
    r'#\s*Your\s+(code|logic|solution|implementation)\s+(here|goes|below)',
    r'#\s*Replace\s+(this|the)\s+(with|by)',
    r'#\s*FIXME:\s*(implement|add|write)',
    r'#\s*This\s+is\s+(a|an)\s+(placeholder|example|template)',
]

# 可能虚假的模块模式（import 可能不存在）
SUSPICIOUS_MODULES = [
    r'^import\s+utils$',
    r'^from\s+utils\s+import',
    r'^import\s+helpers$',
    r'^from\s+helpers\s+import',
    r'^import\s+config$',
    r'^from\s+common\s+import',
    r'^import\s+common$',
]


@register_rule
class AiHallucinationRule(Rule):
    name = "ai_hallucination"
    severity = Severity.INFO
    description = "检测AI生成的幻觉代码模式"

    def should_check(self, filepath: str) -> bool:
        return filepath.endswith(".py")

    def diagnose(self, filepath: str) -> list[Issue]:
        issues: list[Issue] = []
        try:
            with open(filepath) as f:
                lines = f.readlines()
        except (OSError, UnicodeDecodeError):
            return issues

        content = "".join(lines)

        # 1. AI残留的注释占位
        for i, line in enumerate(lines, 1):
            stripped = line.strip()
            for pattern in AI_COMMENT_PATTERNS:
                if re.search(pattern, stripped, re.IGNORECASE):
                    issues.append(Issue(
                        filepath=filepath,
                        line=i,
                        code="AI_PLACEHOLDER",
                        message=f"AI残留占位注释: {stripped[:60]}",
                        severity=Severity.INFO,
                        rule_name=self.name,
                        fixable=False,
                    ))
                    break

        # 2. 可疑的模块名
        for i, line in enumerate(lines, 1):
            stripped = line.strip()
            for pattern in SUSPICIOUS_MODULES:
                if re.match(pattern, stripped):
                    issues.append(Issue(
                        filepath=filepath,
                        line=i,
                        code="AI_SUSPICIOUS_MODULE",
                        message=f"可疑模块名: {stripped}",
                        severity=Severity.INFO,
                        rule_name=self.name,
                        fixable=False,
                    ))
                    break

        # 3. 过大的单函数（AI容易生成超长函数）
        try:
            tree = ast.parse(content)
            for node in ast.walk(tree):
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    # 计算行数
                    if hasattr(node, 'end_lineno') and hasattr(node, 'lineno'):
                        func_lines = node.end_lineno - node.lineno
                        if func_lines > 200:
                            issues.append(Issue(
                                filepath=filepath,
                                line=node.lineno,
                                code="AI_GIANT_FUNCTION",
                                message=f"函数 {node.name} 过长 ({func_lines}行)，可能由AI生成",
                                severity=Severity.INFO,
                                rule_name=self.name,
                                fixable=False,
                            ))
        except SyntaxError:
            pass

        return issues
