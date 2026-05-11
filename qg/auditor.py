"""Agent行为审计模块。

从 agent_traces 表读取数据，分析：
- 工具调用频率与分布
- 错误率与异常模式
- Token消耗与成本估算
- 异常行为检测（连续失败、循环调用）
"""

from __future__ import annotations

import logging
import os
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

DB_PATH = Path(
    os.environ.get("QG_TRACE_DB", os.environ.get("HERMES_HOME", Path.home() / ".hermes"))
) / "state.db"


def _get_conn() -> Optional[sqlite3.Connection]:
    """获取数据库连接"""
    if not DB_PATH.exists():
        logger.warning(f"state.db 不存在: {DB_PATH}")
        return None
    try:
        conn = sqlite3.connect(str(DB_PATH))
        conn.row_factory = sqlite3.Row
        return conn
    except sqlite3.Error as e:
        logger.warning(f"连接 state.db 失败: {e}")
        return None


def _table_exists(conn: sqlite3.Connection, table: str) -> bool:
    """检查表是否存在"""
    try:
        cursor = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name=?",
            (table,)
        )
        return cursor.fetchone() is not None
    except sqlite3.Error:
        return False


def audit_agent(days: int = 7) -> dict:
    """执行Agent行为审计，返回结构化报告"""
    conn = _get_conn()
    if conn is None:
        return {"error": "state.db 不可用"}

    if not _table_exists(conn, "agent_traces"):
        return {"error": "agent_traces 表不存在（未启用追踪）"}

    report: dict = {}

    # 1. 整体统计
    cursor = conn.execute("SELECT COUNT(*) as cnt FROM agent_traces")
    total = cursor.fetchone()["cnt"]
    report["total_events"] = total

    # 2. 按事件类型分布
    cursor = conn.execute(
        "SELECT event_type, COUNT(*) as cnt FROM agent_traces GROUP BY event_type ORDER BY cnt DESC"
    )
    report["event_distribution"] = {row["event_type"]: row["cnt"] for row in cursor.fetchall()}

    # 3. 按模型分布（api_call）
    cursor = conn.execute(
        "SELECT model, COUNT(*) as cnt FROM agent_traces WHERE event_type='api_call' AND model IS NOT NULL GROUP BY model ORDER BY cnt DESC LIMIT 10"
    )
    report["model_usage"] = {row["model"]: row["cnt"] for row in cursor.fetchall()}

    # 4. 工具调用排行
    cursor = conn.execute(
        "SELECT tool_name, COUNT(*) as cnt FROM agent_traces WHERE event_type='tool_call' AND tool_name IS NOT NULL GROUP BY tool_name ORDER BY cnt DESC LIMIT 15"
    )
    report["tool_ranking"] = {row["tool_name"]: row["cnt"] for row in cursor.fetchall()}

    # 5. 错误统计
    cursor = conn.execute(
        "SELECT status, COUNT(*) as cnt FROM agent_traces WHERE status != 'success' AND status IS NOT NULL GROUP BY status"
    )
    errors = {row["status"]: row["cnt"] for row in cursor.fetchall()}
    cursor = conn.execute("SELECT COUNT(*) as cnt FROM agent_traces WHERE status != 'success' OR status IS NULL")
    total_errors = cursor.fetchone()["cnt"]
    report["errors"] = errors
    report["total_errors"] = total_errors
    report["error_rate"] = round(total_errors / total * 100, 2) if total > 0 else 0

    # 6. Token消耗汇总
    cursor = conn.execute(
        "SELECT model, SUM(token_count) as total_tokens FROM agent_traces WHERE event_type='api_call' AND token_count IS NOT NULL GROUP BY model ORDER BY total_tokens DESC"
    )
    token_data = {row["model"]: row["total_tokens"] for row in cursor.fetchall()}
    report["token_consumption"] = token_data
    report["total_tokens"] = sum(token_data.values()) if token_data else 0

    # 7. 成本估算（粗略：按模型均价）
    COST_PER_1K = {
        "deepseek-v4-flash": 0.00015,
        "deepseek-v4-pro": 0.002,
        "gpt-4o": 0.0025,
        "gpt-4o-mini": 0.00015,
        "claude-sonnet-4": 0.003,
        "claude-haiku-3.5": 0.00025,
    }
    estimated_cost = 0.0
    for model, tokens in token_data.items():
        rate = 0.0005  # 默认
        for key, val in COST_PER_1K.items():
            if key in model.lower():
                rate = val
                break
        estimated_cost += (tokens / 1000) * rate
    report["estimated_cost_usd"] = round(estimated_cost, 4)

    # 8. 每日活跃度（近7天）
    report["daily_activity"] = {}
    for i in range(days - 1, -1, -1):
        day = (datetime.now() - timedelta(days=i)).strftime("%m/%d")
        cursor = conn.execute(
            "SELECT COUNT(*) as cnt FROM agent_traces WHERE timestamp LIKE ?",
            (f"{day}%",)
        )
        report["daily_activity"][day] = cursor.fetchone()["cnt"]

    # 9. 异常检测：连续同工具失败
    cursor = conn.execute(
        "SELECT session_id, tool_name, COUNT(*) as cnt FROM agent_traces WHERE event_type='tool_call' AND status != 'success' AND tool_name IS NOT NULL GROUP BY session_id, tool_name HAVING cnt >= 3 ORDER BY cnt DESC LIMIT 5"
    )
    anomalies = cursor.fetchall()
    report["anomalies"] = [dict(a) for a in anomalies] if anomalies else []

    conn.close()
    return report


def format_audit_report(report: dict) -> list[str]:
    """将审计报告格式化为可读文本"""
    if "error" in report:
        return [f"⚠️ Agent审计不可用: {report['error']}"]

    lines = []
    lines.append("━━━ 📊 Agent行为审计 ━━━")

    # 概览
    lines.append(f"总事件: {report.get('total_events', 0)} 次")
    dist = report.get("event_distribution", {})
    parts = [f"{k}={v}" for k, v in sorted(dist.items(), key=lambda x: -x[1])]
    lines.append(f"分布: {' | '.join(parts[:5])}")

    # 错误率
    err_rate = report.get("error_rate", 0)
    err_total = report.get("total_errors", 0)
    if err_rate > 0:
        lines.append(f"错误: {err_total} 次 ({err_rate}%) ⚠️")
    else:
        lines.append("错误: 0 次 ✅")

    # Token & 成本
    tokens = report.get("total_tokens", 0)
    cost = report.get("estimated_cost_usd", 0)
    lines.append(f"Token: {tokens:,} | 成本: ~${cost:.4f}")

    # 工具调用排行（Top 5）
    tools = report.get("tool_ranking", {})
    if tools:
        top5 = list(tools.items())[:5]
        lines.append(f"工具Top5: {' → '.join(f'{n}({c})' for n, c in top5)}")

    # 模型使用
    models = report.get("model_usage", {})
    if models:
        model_str = " | ".join(f"{m}: {c}" for m, c in list(models.items())[:3])
        lines.append(f"模型: {model_str}")

    # 异常
    anomalies = report.get("anomalies", [])
    if anomalies:
        for a in anomalies:
            lines.append(f"⚠️ 异常: session {a['session_id'][:12]}... {a['tool_name']} 失败 {a['cnt']} 次")

    return lines
