"""总结汇报 + 日志输出 + 微信推送。

职责：汇总所有阶段结果 → 生成结构化报告 → 日志归档 → 可选微信格式输出
"""

from __future__ import annotations

import logging
from datetime import datetime

from .config import HERMES_HOME
from .models import ScanResult

logger = logging.getLogger(__name__)


def generate_report(result: ScanResult, score_line: str = "") -> list[str]:
    """生成结构化的质量门禁报告。

    Returns:
        报告行列表（适合微信/日志输出）
    """
    date_str = datetime.now().strftime("%m/%d")
    lines: list[str] = []

    if score_line:
        lines.append(score_line)
        lines.append("")

    if result.total_issues == 0 and result.fixed_count == 0:
        lines.append(f"━━━ ✅ 质量门禁 {date_str} ━━━")
        lines.append(f"扫描: {result.total_files} 个文件")
        lines.append("结果: 全部通过，零问题")
    elif result.total_issues == 0 and result.fixed_count > 0:
        lines.append(f"━━━ ✅ 质量门禁 {date_str} ━━━")
        lines.append(f"扫描: {result.total_files} 个文件（+{len(result.new_files)}/~{len(result.changed_files)}）")
        lines.append(f"修复: {result.fixed_count} 处自动修复 ✅")
        if result.commit_count > 0:
            lines.append(f"提交: {result.commit_count} 个仓库已自动提交 ✅")
    else:
        lines.append(f"━━━ ⚠️ 质量门禁 {date_str} ━━━")
        lines.append(f"扫描: {result.total_files} 个文件（+{len(result.new_files)}/~{len(result.changed_files)}）")

        if result.blocker_count > 0:
            lines.append(f"阻塞: {result.blocker_count} 项 ❌ 需人工")
            for i in result.blockers[:3]:
                lines.append(f"  ❌ {i.short_path}:L{i.line}  {i.code}")
            if result.blocker_count > 3:
                lines.append(f"  ...及 {result.blocker_count - 3} 项")

        if result.fixed_count > 0:
            lines.append(f"修复: {result.fixed_count} 处 ✅")
        if result.commit_count > 0:
            lines.append(f"提交: {result.commit_count} 个仓库 ✅")

    return lines


def write_log(report_lines: list[str]):
    """写入日志文件"""
    log_dir = HERMES_HOME / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    log_file = log_dir / "quality-gate.log"

    with open(log_file, "a") as f:
        f.write("\n")
        f.write("━" * 40 + "\n")
        f.write(f"[{datetime.now().isoformat()}]\n")
        for line in report_lines:
            f.write(line + "\n")
        f.write("━" * 40 + "\n")


def format_wechat(report_lines: list[str]) -> str:
    """转换为微信消息格式（浓缩版）"""
    # 直接返回报告行，已经很紧凑了
    return "\n".join(report_lines)
