"""R7 — Intelligence Dashboard: is Kiwi getting smarter? 0 LLM token."""

import time

from .session_logger import _get_conn
from .metrics import epoch_week


def generate_dashboard(weeks: int = 8) -> dict:
    conn = _get_conn()
    current_week = epoch_week()

    dashboard = {
        'generated_at': time.time(),
        'period_weeks': weeks,
        'weekly_trends': [],
        'task_type_breakdown': {},
        'autonomy_progression': {},
        'intelligence_score': 0.0,
    }

    for w in range(current_week - weeks, current_week + 1):
        row = conn.execute(
            "SELECT "
            "  AVG(tokens_estimated) as avg_tokens, "
            "  AVG(files_re_read) as avg_re_reads, "
            "  AVG(edits_after_first) as avg_edits, "
            "  AVG(trust_score) as avg_trust, "
            "  AVG(brief_level) as avg_level, "
            "  COUNT(*) as sessions "
            "FROM output_quality WHERE week = ?",
            (w,)
        ).fetchone()

        if row and row[5] > 0:
            dashboard['weekly_trends'].append({
                'week': w,
                'avg_tokens': round(row[0] or 0),
                'avg_re_reads': round(row[1] or 0, 1),
                'avg_edits': round(row[2] or 0, 1),
                'avg_trust': round(row[3] or 0, 3),
                'avg_level': round(row[4] or 0, 1),
                'sessions': row[5],
            })

    task_rows = conn.execute(
        "SELECT task_type, "
        "  AVG(tokens_estimated), AVG(trust_score), COUNT(*) "
        "FROM output_quality WHERE week >= ? "
        "GROUP BY task_type ORDER BY COUNT(*) DESC",
        (current_week - weeks,)
    ).fetchall()

    for task_type, avg_tokens, avg_trust, count in task_rows:
        dashboard['task_type_breakdown'][task_type] = {
            'avg_tokens': round(avg_tokens or 0),
            'avg_trust': round(avg_trust or 0, 3),
            'sessions': count,
        }

    level_rows = conn.execute(
        "SELECT autonomy_level, COUNT(*) "
        "FROM output_quality WHERE week >= ? "
        "GROUP BY autonomy_level",
        (current_week - 4,)
    ).fetchall()

    total_sessions = sum(r[1] for r in level_rows) if level_rows else 1
    for level, count in level_rows:
        dashboard['autonomy_progression'][level or 'none'] = {
            'count': count,
            'percentage': round(count / total_sessions * 100, 1),
        }

    dashboard['intelligence_score'] = compute_intelligence_score(dashboard)
    return dashboard


def compute_intelligence_score(dashboard: dict) -> float:
    trends = dashboard.get('weekly_trends', [])
    if len(trends) < 2:
        return 0.0

    latest = trends[-1]
    first = trends[0]
    scores = []

    # Token reduction (0-30 points)
    if first['avg_tokens'] > 0:
        token_reduction = 1 - (latest['avg_tokens'] / first['avg_tokens'])
        scores.append(min(max(token_reduction * 100, 0), 30))
    else:
        scores.append(0)

    # Trust level (0-30 points)
    scores.append(min(latest['avg_trust'] * 30, 30))

    # Brief level (0-20 points)
    scores.append(min(latest['avg_level'] / 3 * 20, 20))

    # Re-read reduction (0-20 points)
    if first['avg_re_reads'] > 0:
        reread_reduction = 1 - (latest['avg_re_reads'] / first['avg_re_reads'])
        scores.append(min(max(reread_reduction * 20, 0), 20))
    else:
        scores.append(20)

    return round(sum(scores), 1)


def print_dashboard(dashboard: dict):
    print("\n" + "=" * 60)
    print(f"  KIWI INTELLIGENCE DASHBOARD")
    print(f"  Score: {dashboard['intelligence_score']}/100")
    print("=" * 60)

    print("\n  Weekly Token Trend (lower = smarter):")
    print("  " + "-" * 50)

    for week in dashboard['weekly_trends']:
        bar_len = min(int(week['avg_tokens'] / 500), 40)
        bar = "#" * bar_len
        print(f"  W{week['week']:05d}: {bar} {week['avg_tokens']:,} tok "
              f"(trust:{week['avg_trust']:.2f}, L{week['avg_level']:.0f})")

    print("\n  Autonomy Distribution (last 4 weeks):")
    for level, data in dashboard['autonomy_progression'].items():
        print(f"    {level:12s}: {data['percentage']:5.1f}% ({data['count']} sessions)")

    print("\n  Task Type Performance:")
    for task, data in list(dashboard['task_type_breakdown'].items())[:5]:
        print(f"    {task:20s}: {data['avg_tokens']:,} tok, "
              f"trust {data['avg_trust']:.2f} ({data['sessions']} sessions)")

    print("\n" + "=" * 60)


if __name__ == "__main__":
    d = generate_dashboard()
    print_dashboard(d)