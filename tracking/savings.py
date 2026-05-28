"""Savings Calculator — compute actual vs baseline savings."""

import sqlite3
import time
from pathlib import Path
from typing import Optional

DB_PATH = Path(__file__).parent.parent / "memory" / "kiwi.db"


def get_savings(
    period: str = "week",
    db_path: Path = None,
) -> dict:
    """Get savings summary for a given period.

    Args:
        period: 'today', 'week', 'month', 'all'
        db_path: Override DB path (for testing)

    Returns:
        dict with totals, per-operation breakdown, daily trend
    """
    db = db_path or DB_PATH
    if not db.exists():
        return _empty_result(period)

    conn = sqlite3.connect(str(db), timeout=5)
    conn.row_factory = sqlite3.Row

    cutoff = _period_to_cutoff(period)

    totals = _get_totals(conn, cutoff)
    by_operation = _get_by_operation(conn, cutoff)
    daily = _get_daily(conn, cutoff)

    conn.close()

    return {
        "period": period,
        "totals": totals,
        "by_operation": by_operation,
        "daily": daily,
    }


def _period_to_cutoff(period: str) -> float:
    now = time.time()
    if period == "today":
        return now - 86400
    elif period == "week":
        return now - 7 * 86400
    elif period == "month":
        return now - 30 * 86400
    else:
        return 0.0


def _get_totals(conn: sqlite3.Connection, cutoff: float) -> dict:
    row = conn.execute(
        "SELECT "
        "COUNT(*) as total_ops, "
        "SUM(CASE WHEN tokens_claude = 0 THEN 1 ELSE 0 END) as local_ops, "
        "SUM(cost_actual_usd) as actual_usd, "
        "SUM(cost_baseline_usd) as baseline_usd, "
        "SUM(tokens_local) as tokens_local, "
        "SUM(tokens_baseline) as tokens_baseline, "
        "SUM(latency_ms) as latency_actual_ms, "
        "SUM(latency_baseline_ms) as latency_baseline_ms "
        "FROM usage_events WHERE timestamp > ?",
        (cutoff,),
    ).fetchone()

    total_ops = row["total_ops"] or 0
    local_ops = row["local_ops"] or 0
    actual = row["actual_usd"] or 0.0
    baseline = row["baseline_usd"] or 0.0

    return {
        "total_ops": total_ops,
        "local_ops": local_ops,
        "local_rate_pct": round(local_ops / total_ops * 100, 1) if total_ops > 0 else 0.0,
        "actual_usd": round(actual, 4),
        "baseline_usd": round(baseline, 4),
        "saved_usd": round(baseline - actual, 4),
        "savings_pct": round((baseline - actual) / baseline * 100, 1) if baseline > 0 else 0.0,
        "tokens_local": row["tokens_local"] or 0,
        "tokens_baseline": row["tokens_baseline"] or 0,
        "latency_actual_ms": row["latency_actual_ms"] or 0,
        "latency_baseline_ms": row["latency_baseline_ms"] or 0,
    }


def _get_by_operation(conn: sqlite3.Connection, cutoff: float) -> list:
    rows = conn.execute(
        "SELECT "
        "operation, "
        "COUNT(*) as ops, "
        "SUM(cost_baseline_usd) - SUM(cost_actual_usd) as saved_usd, "
        "SUM(tokens_baseline) as tokens_baseline "
        "FROM usage_events WHERE timestamp > ? "
        "GROUP BY operation ORDER BY saved_usd DESC",
        (cutoff,),
    ).fetchall()

    return [
        {
            "operation": r["operation"],
            "ops": r["ops"],
            "saved_usd": round(r["saved_usd"] or 0, 4),
            "tokens_baseline": r["tokens_baseline"] or 0,
        }
        for r in rows
    ]


def _get_daily(conn: sqlite3.Connection, cutoff: float) -> list:
    rows = conn.execute(
        "SELECT "
        "date(timestamp, 'unixepoch', 'localtime') as day, "
        "COUNT(*) as ops, "
        "SUM(cost_baseline_usd) - SUM(cost_actual_usd) as saved_usd "
        "FROM usage_events WHERE timestamp > ? "
        "GROUP BY day ORDER BY day DESC LIMIT 7",
        (cutoff,),
    ).fetchall()

    return [
        {"day": r["day"], "ops": r["ops"], "saved_usd": round(r["saved_usd"] or 0, 4)}
        for r in rows
    ]


def _empty_result(period: str) -> dict:
    return {
        "period": period,
        "totals": {
            "total_ops": 0,
            "local_ops": 0,
            "local_rate_pct": 0.0,
            "actual_usd": 0.0,
            "baseline_usd": 0.0,
            "saved_usd": 0.0,
            "savings_pct": 0.0,
            "tokens_local": 0,
            "tokens_baseline": 0,
            "latency_actual_ms": 0,
            "latency_baseline_ms": 0,
        },
        "by_operation": [],
        "daily": [],
    }