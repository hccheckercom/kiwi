"""Trend analysis for Kiwi scan history."""

from .db import get_connection


def violation_trend(path: str, days: int = 30) -> list:
    conn = get_connection()
    try:
        rows = conn.execute("""
            SELECT date(timestamp) as date,
                   SUM(violations_critical) as critical,
                   SUM(violations_high) as high,
                   SUM(violations_suggest) as suggest,
                   SUM(violations_total) as total,
                   SUM(violations_fixed) as fixed,
                   COUNT(*) as scans
            FROM scan_history
            WHERE path LIKE ? AND timestamp >= datetime('now', ?)
            GROUP BY date(timestamp)
            ORDER BY date
        """, (f"%{path}%", f"-{days} days")).fetchall()
    finally:
        conn.close()
    return [dict(r) for r in rows]


def regression_check(path: str) -> list:
    conn = get_connection()
    try:
        last_two = conn.execute("""
            SELECT * FROM scan_history
            WHERE path LIKE ? ORDER BY timestamp DESC LIMIT 2
        """, (f"%{path}%",)).fetchall()
    finally:
        conn.close()

    if len(last_two) < 2:
        return []

    current, previous = last_two[0], last_two[1]
    regressions = []

    for sev in ["critical", "high"]:
        col = f"violations_{sev}"
        cur_val = current[col]
        prev_val = previous[col]
        if cur_val > prev_val:
            regressions.append({
                "severity": sev.upper(),
                "previous": prev_val,
                "current": cur_val,
                "delta": cur_val - prev_val,
                "message": f"{sev.upper()} violations increased: {prev_val} → {cur_val}",
            })

    return regressions


def project_summary(path: str) -> dict:
    conn = get_connection()
    try:
        total_scans = conn.execute(
            "SELECT COUNT(*) FROM scan_history WHERE path LIKE ?", (f"%{path}%",)
        ).fetchone()[0]

        latest = conn.execute(
            "SELECT * FROM scan_history WHERE path LIKE ? ORDER BY timestamp DESC LIMIT 1",
            (f"%{path}%",)
        ).fetchone()

        total_fixes = conn.execute(
            "SELECT COUNT(*) FROM fix_outcomes WHERE file LIKE ?", (f"%{path}%",)
        ).fetchone()[0]

        total_dismissed = conn.execute(
            "SELECT COUNT(*) FROM false_positives WHERE file LIKE ? AND active=1", (f"%{path}%",)
        ).fetchone()[0]

    finally:
        conn.close()

    result = {
        "path": path,
        "total_scans": total_scans,
        "total_fixes": total_fixes,
        "total_dismissed": total_dismissed,
    }
    if latest:
        result["last_scan"] = {
            "date": latest["timestamp"],
            "critical": latest["violations_critical"],
            "high": latest["violations_high"],
            "total": latest["violations_total"],
        }
    return result


def get_high_impact_files(path: str = None, limit: int = 10) -> list:
    """
    Get files that frequently cause regressions when modified.
    Returns files sorted by number of times they triggered regressions.
    """
    conn = get_connection()
    try:

        query = """
            SELECT fixed_file,
                   COUNT(*) as fix_count,
                   SUM(regressions_found) as total_regressions,
                   AVG(regressions_found) as avg_regressions,
                   MAX(risk_level) as max_risk
            FROM impact_analysis
            WHERE regressions_found > 0
        """

        if path:
            query += " AND fixed_file LIKE ?"
            rows = conn.execute(query + " GROUP BY fixed_file ORDER BY total_regressions DESC LIMIT ?",
                               (f"%{path}%", limit)).fetchall()
        else:
            rows = conn.execute(query + " GROUP BY fixed_file ORDER BY total_regressions DESC LIMIT ?",
                               (limit,)).fetchall()

    finally:
        conn.close()
    return [dict(r) for r in rows]


def get_impact_summary(path: str = None) -> dict:
    """Get summary statistics for impact analysis."""
    conn = get_connection()
    try:

        if path:
            total_impacts = conn.execute(
                "SELECT COUNT(*) FROM impact_analysis WHERE fixed_file LIKE ?",
                (f"%{path}%",)
            ).fetchone()[0]

            total_regressions = conn.execute(
                "SELECT SUM(regressions_found) FROM impact_analysis WHERE fixed_file LIKE ?",
                (f"%{path}%",)
            ).fetchone()[0] or 0

            high_risk_count = conn.execute(
                "SELECT COUNT(*) FROM impact_analysis WHERE fixed_file LIKE ? AND risk_level IN ('HIGH', 'CRITICAL')",
                (f"%{path}%",)
            ).fetchone()[0]
        else:
            total_impacts = conn.execute(
                "SELECT COUNT(*) FROM impact_analysis"
            ).fetchone()[0]

            total_regressions = conn.execute(
                "SELECT SUM(regressions_found) FROM impact_analysis"
            ).fetchone()[0] or 0

            high_risk_count = conn.execute(
                "SELECT COUNT(*) FROM impact_analysis WHERE risk_level IN ('HIGH', 'CRITICAL')"
            ).fetchone()[0]

    finally:
        conn.close()

    return {
        "total_impacts": total_impacts,
        "total_regressions": total_regressions,
        "high_risk_count": high_risk_count,
        "regression_rate": round(total_regressions / total_impacts * 100, 1) if total_impacts > 0 else 0,
    }