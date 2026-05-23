"""趋势仪表盘模块。

每天跑完质量门禁后，将关键指标存入 SQLite 历史表。
支持查看最近 N 天的趋势图（纯文本，不依赖外部库）。
"""

from __future__ import annotations

import logging
import sqlite3
from datetime import datetime
from pathlib import Path

logger = logging.getLogger(__name__)

DB_PATH = Path.home() / ".hermes" / "quality-gate" / "trends.db"


def _get_conn() -> sqlite3.Connection:
    """获取数据库连接，自动建表"""
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    conn.execute("""
        CREATE TABLE IF NOT EXISTS daily_metrics (
            date TEXT PRIMARY KEY,
            total_files INTEGER DEFAULT 0,
            new_files INTEGER DEFAULT 0,
            changed_files INTEGER DEFAULT 0,
            stable_files INTEGER DEFAULT 0,
            total_issues INTEGER DEFAULT 0,
            blocker_count INTEGER DEFAULT 0,
            fixable_count INTEGER DEFAULT 0,
            info_count INTEGER DEFAULT 0,
            fixed_count INTEGER DEFAULT 0,
            commit_count INTEGER DEFAULT 0,
            quality_score REAL DEFAULT NULL,
            timestamp TEXT DEFAULT (datetime('now'))
        )
    """)
    # 兼容旧表：添加新列（如果不存在）
    try:
        conn.execute("ALTER TABLE daily_metrics ADD COLUMN quality_score REAL DEFAULT NULL")
    except sqlite3.OperationalError:
        pass  # 列已存在
    conn.commit()
    conn.commit()
    return conn


def save_metrics(result, quality_score: float | None = None) -> None:
    """保存一次扫描结果到历史表"""
    conn = _get_conn()
    date_str = datetime.now().strftime("%Y-%m-%d")

    conn.execute("""
        INSERT OR REPLACE INTO daily_metrics
            (date, total_files, new_files, changed_files, stable_files,
             total_issues, blocker_count, fixable_count, info_count,
             fixed_count, commit_count, quality_score)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        date_str,
        result.total_files,
        len(result.new_files),
        len(result.changed_files),
        len(result.stable_files),
        result.total_issues,
        result.blocker_count,
        result.fixable_count,
        result.info_count,
        result.fixed_count,
        result.commit_count,
        quality_score,
    ))
    conn.commit()
    conn.close()
    logger.info(f"📈 趋势数据已保存: {date_str}")


def get_trend(days: int = 14) -> list[dict]:
    """获取最近 N 天的趋势数据"""
    conn = _get_conn()
    cursor = conn.execute(
        "SELECT * FROM daily_metrics ORDER BY date DESC LIMIT ?",
        (days,)
    )
    rows = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return list(reversed(rows))


def format_trend_chart(trend_data: list[dict]) -> list[str]:
    """将趋势数据格式化为文本图表"""
    if not trend_data:
        return ["📈 暂无趋势数据（明天跑完第一次才有）"]

    lines = []
    lines.append(f"━━━ 📈 质量门禁趋势 (最近{len(trend_data)}天) ━━━")

    # 问题趋势图（用 █ 表示比例）
    max_issues = max(
        (r.get("total_issues", 0) or 1) for r in trend_data
    )
    max_issues = max(max_issues, 1)

    for row in trend_data:
        date = row["date"][5:]  # MM-DD
        total = row.get("total_issues", 0)
        fixed = row.get("fixed_count", 0)
        blockers = row.get("blocker_count", 0)
        files = row.get("total_files", 0)

        bar_len = max(1, int(total / max_issues * 16))
        bar = "█" * bar_len + "░" * (16 - bar_len)

        status = "✅" if total == 0 else ("⚠️" if blockers == 0 else "❌")
        extra = f" 修{fixed}" if fixed > 0 else ""
        extra += f" ❌{blockers}" if blockers > 0 else ""

        lines.append(f"  {date} {bar} {total:3d}问题{extra} {status}")

    # 文件数趋势
    lines.append("")
    lines.append("文件数趋势:")
    max_files = max((r.get("total_files", 0) or 1) for r in trend_data)
    max_files = max(max_files, 1)

    for row in trend_data[-7:]:  # 只显示最近7天的文件数
        date = row["date"][5:]
        files = row.get("total_files", 0)
        bar_len = max(1, int(files / max_files * 20))
        bar = "▓" * bar_len + "░" * (20 - bar_len)
        lines.append(f"  {date} {bar} {files}")

    # 汇总
    avg_issues = sum(r.get("total_issues", 0) for r in trend_data) / len(trend_data)
    avg_score = sum(r.get("quality_score", 0) or 0 for r in trend_data) / len(trend_data)
    lines.append("")
    lines.append(f"日均问题数: {avg_issues:.1f}  |  平均评分: {avg_score:.1f}/100")
    lines.append(f"健康天数: {sum(1 for r in trend_data if r.get('total_issues', 0) == 0)}/{len(trend_data)}")

    # 评分趋势
    scores = [r.get("quality_score") for r in trend_data if r.get("quality_score") is not None]
    if len(scores) >= 2:
        delta = scores[-1] - scores[0]
        trend = "↗️" if delta > 1 else ("↘️" if delta < -1 else "→")
        lines.append(f"评分趋势: {scores[0]:.0f} → {scores[-1]:.0f} {trend} ({delta:+.1f})")

    return lines
