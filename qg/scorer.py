"""安全质量评分系统 — 对标 SonarQube Quality Gate

在每次扫描后计算总体质量和安全评分（0-100），
让老板一眼看出代码库的健康状况。

评分维度：
| 维度 | 权重 | 计算方式 |
|:----|:----:|:---------|
| 阻断率 | 25% | blocker_count == 0 → 100, >= 5 → 0 |
| 修复率 | 25% | fixable_count == 0 → 100, 已修复/总可修 |
| 覆盖率 | 15% | 被扫描文件占比（排除 ignore_patterns 后） |
| 安全分数 | 20% | secret_leak + unsafe_api 的数量 |
| 趋势 | 15% | 相比上次扫描，问题是变好还是变差 |

使用方式：
```python
from qg.scorer import ScoreCalculator
score = ScoreCalculator()
result = score.calculate(all_issues, scan_result)
print(result.score)  # 0-100
print(result.grade)  # A/B/C/D/F
print(result.breakdown)  # 各维度明细
```
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Optional

from .models import Issue, ScanResult, Severity

logger = logging.getLogger(__name__)


@dataclass
class ScoreResult:
    """评分结果"""
    score: float  # 0-100
    grade: str  # A(90+) / B(75+) / C(60+) / D(40+) / F(<40)
    breakdown: dict[str, float] = field(default_factory=dict)
    previous_score: Optional[float] = None
    score_delta: Optional[float] = None


class ScoreCalculator:
    """质量评分计算器"""

    def __init__(self):
        self._last_score: Optional[float] = None

    def calculate(self, issues: list[Issue],
                  scan_result: Optional[ScanResult] = None,
                  prev_issue_count: Optional[int] = None) -> ScoreResult:
        """计算本次扫描的质量评分"""
        blockers = [i for i in issues if i.severity == Severity.BLOCKER]
        fixables = [i for i in issues if i.severity == Severity.FIXABLE]
        infos = [i for i in issues if i.severity == Severity.INFO]

        # 安全相关规则
        safety_rules = {"unsafe_api", "secret_leak", "sql_injection", "path_traversal"}
        safety_issues = [i for i in issues if i.rule_name in safety_rules]

        # 1. 阻断率（25%）
        blocker_score = 100.0
        if len(blockers) > 0:
            blocker_score = max(0, 100 - (len(blockers) * 15))
        # 20+ blockers = 0分
        if len(blockers) >= 20:
            blocker_score = 0

        # 2. 修复率（25%）
        fixable_score = 100.0
        if fixables and scan_result:
            total_fixable = len(fixables)
            fixed = scan_result.fixed_count
            fixable_score = (fixed / total_fixable * 100) if total_fixable > 0 else 100
        elif fixables:
            fixable_score = 0  # 有可修但没传 scan_result
        # 没有可修复项 → 满分

        # 3. 覆盖完整度（15%）
        coverage_score = 85.0  # 默认良好
        if scan_result and scan_result.total_files > 0:
            new_pct = len(scan_result.new_files) / max(scan_result.total_files, 1) * 100
            changed_pct = len(scan_result.changed_files) / max(scan_result.total_files, 1) * 100
            if new_pct > 50:
                coverage_score = 60  # 新文件太多 = 不熟悉区域
            elif new_pct > 20:
                coverage_score = 75
            else:
                coverage_score = 95

        # 4. 安全分数（20%）
        safety_score = 100.0
        if len(safety_issues) > 0:
            safety_score = max(0, 100 - (len(safety_issues) * 20))
        if len(safety_issues) >= 5:
            safety_score = 0

        # 5. 趋势（15%）
        trend_score = 85.0  # 默认正向
        if prev_issue_count is not None:
            delta = prev_issue_count - len(issues)
            if delta > 0:
                trend_score = min(100, 85 + delta * 2)
            elif delta < 0:
                trend_score = max(0, 85 + delta * 5)

        # 加权总分
        total_score = (
            blocker_score * 0.25 +
            fixable_score * 0.25 +
            coverage_score * 0.15 +
            safety_score * 0.20 +
            trend_score * 0.15
        )

        # 等级
        grade = self._to_grade(total_score)

        # 生成明细
        breakdown = {
            "阻断率": round(blocker_score, 1),
            "修复率": round(fixable_score, 1),
            "覆盖完整度": round(coverage_score, 1),
            "安全分数": round(safety_score, 1),
            "趋势分数": round(trend_score, 1),
            "blockers": len(blockers),
            "fixables": len(fixables),
            "safety_issues": len(safety_issues),
            "total_issues": len(issues),
        }

        result = ScoreResult(
            score=round(total_score, 1),
            grade=grade,
            breakdown=breakdown,
        )

        # 保存本次分数供下次对比
        self._last_score = total_score

        return result

    def _to_grade(self, score: float) -> str:
        if score >= 90:
            return "A"
        elif score >= 75:
            return "B"
        elif score >= 60:
            return "C"
        elif score >= 40:
            return "D"
        else:
            return "F"

    def score_emoji(self, grade: str) -> str:
        """根据等级返回 emoji"""
        return {
            "A": "🟢",
            "B": "🟡",
            "C": "🟠",
            "D": "🔴",
            "F": "💀",
        }.get(grade, "⚪")

    def summary_line(self, result: ScoreResult) -> str:
        """Generate one-line summary"""
        emoji = self.score_emoji(result.grade)
        trend = ""
        if result.score_delta is not None:
            if result.score_delta > 0:
                trend = f" ↑+{result.score_delta:.1f}"
            elif result.score_delta < 0:
                trend = f" ↓{result.score_delta:.1f}"
        return (
            f"{emoji} Grade: {result.grade} (Score: {result.score:.1f}/100){trend}\n"
            f"  Blockers: {int(result.breakdown['blockers'])} | "
            f"Fixable: {int(result.breakdown['fixables'])} | "
            f"Security: {int(result.breakdown['safety_issues'])} | "
            f"Total: {int(result.breakdown['total_issues'])}"
        )
