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
    """Generate a structured quality gate report.

    Returns:
        Report lines (suitable for console/log output)
    """
    date_str = datetime.now().strftime("%m/%d")
    lines: list[str] = []

    if score_line:
        lines.append(score_line)
        lines.append("")

    if result.total_issues == 0 and result.fixed_count == 0:
        lines.append(f"━━━ ✅ Quality Gate {date_str} ━━━")
        lines.append(f"Scanned: {result.total_files} files")
        lines.append("Result: All clear, zero issues")
    elif result.total_issues == 0 and result.fixed_count > 0:
        lines.append(f"━━━ ✅ Quality Gate {date_str} ━━━")
        lines.append(f"Scanned: {result.total_files} files (+{len(result.new_files)}/~{len(result.changed_files)})")
        lines.append(f"Fixed: {result.fixed_count} auto-fixes ✅")
        if result.commit_count > 0:
            lines.append(f"Committed: {result.commit_count} repos ✅")
    else:
        lines.append(f"━━━ ⚠️ Quality Gate {date_str} ━━━")
        lines.append(f"Scanned: {result.total_files} files (+{len(result.new_files)}/~{len(result.changed_files)})")

        if result.blocker_count > 0:
            lines.append(f"Blockers: {result.blocker_count} ❌ manual review needed")
            for i in result.blockers[:3]:
                lines.append(f"  ❌ {i.short_path}:L{i.line}  {i.code}")
            if result.blocker_count > 3:
                lines.append(f"  ...and {result.blocker_count - 3} more")

        if result.fixed_count > 0:
            lines.append(f"Fixed: {result.fixed_count} ✅")
        if result.commit_count > 0:
            lines.append(f"Committed: {result.commit_count} repos ✅")

    return lines


def write_log(report_lines: list[str]):
    """Write report to log file"""
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
    """Convert to WeChat message format (compact)"""
    return "\n".join(report_lines)
