"""抑制系统 — 允许通过注释忽略特定规则

用法示例：
```python
x = eval(user_input)  # gate:ignore unsafe_api
os.system(cmd)  # gate:ignore unsafe_api 这个场景安全
```

抑制格式：
- `# gate:ignore <rule_name>` — 忽略该行指定规则
- `# gate:ignore <rule1>, <rule2>` — 忽略该行多个规则
- `# gate:ignore all` — 忽略该行所有规则
- `# gate:ignore-start <rule>` ... `# gate:ignore-end <rule>` — 范围忽略

抑制系统在 engine 层过滤 issue，不影响规则本身的诊断逻辑。
"""

from __future__ import annotations

import re
from typing import Optional

from .models import Issue


# 正则：单行抑制（只取第一个token作为规则名，忽略后面的说明文字）
LINE_SUPPRESS_RE = re.compile(
    r'#\s*gate:\s*ignore\s+([^\s#]+(?:\s*,\s*[^\s#]+)*)'
)

# 正则：范围抑制开始/结束
SUPPRESS_START_RE = re.compile(
    r'#\s*gate:\s*ignore-start\s*(.*?)(?:\s*#|\s*$)'
)
SUPPRESS_END_RE = re.compile(
    r'#\s*gate:\s*ignore-end\s*(.*?)(?:\s*#|\s*$)'
)


def filter_suppressed(issues: list[Issue]) -> list[Issue]:
    """过滤掉被抑制注释标记的问题"""
    if not issues:
        return []

    # 按文件分组
    files: dict[str, list[Issue]] = {}
    for issue in issues:
        files.setdefault(issue.filepath, []).append(issue)

    result: list[Issue] = []
    for filepath, file_issues in files.items():
        try:
            with open(filepath) as f:
                lines = f.readlines()
        except (OSError, UnicodeDecodeError):
            result.extend(file_issues)
            continue

        # 解析范围抑制
        range_suppressions: dict[str, set[str]] = {}  # (start_line, end_line) → rules
        current_range: Optional[tuple[int, list[str]]] = None

        # 先扫描范围抑制标记
        for line_no, line_content in enumerate(lines, 1):
            # 检查忽略开始标记
            m = SUPPRESS_START_RE.search(line_content)
            if m:
                rule_str = m.group(1).strip()
                rules = [r.strip() for r in rule_str.split(",")] if rule_str else ["all"]
                current_range = (line_no, rules)
                continue

            # 检查忽略结束标记
            m = SUPPRESS_END_RE.search(line_content)
            if m and current_range is not None:
                start_line, rules = current_range
                end_line = line_no
                for rule in rules:
                    range_suppressions[(start_line, end_line)] = rules
                current_range = None

        # 逐 issue 过滤
        for issue in file_issues:
            if issue.line < 1 or issue.line > len(lines):
                result.append(issue)
                continue

            line_content = lines[issue.line - 1]

            # 1. 检查单行抑制
            m = LINE_SUPPRESS_RE.search(line_content)
            if m:
                ignored_rules = [r.strip() for r in m.group(1).split(",")]
                if "all" in ignored_rules or issue.rule_name in ignored_rules:
                    continue  # 被抑制

            # 2. 检查范围抑制
            suppressed = False
            for (start, end), rules in range_suppressions.items():
                if start <= issue.line <= end:
                    if "all" in rules or issue.rule_name in rules:
                        suppressed = True
                        break
            if suppressed:
                continue

            result.append(issue)

    return result
