"""R7 — Stagnation Alerts: detect when Kiwi stops improving. 0 LLM token."""

import time

from .session_logger import _get_conn
from .metrics import epoch_week


def check_stagnation() -> dict | None:
    conn = _get_conn()
    current_week = epoch_week()

    recent = _get_period_metrics(conn, current_week - 1, current_week)
    baseline = _get_period_metrics(conn, current_week - 3, current_week - 2)

    if not recent or not baseline:
        return None

    token_improvement = (baseline['avg_tokens'] - recent['avg_tokens']) / max(baseline['avg_tokens'], 1)
    trust_improvement = recent['avg_trust'] - baseline['avg_trust']
    level_improvement = recent['avg_level'] - baseline['avg_level']

    confidence = min((recent['sessions'] + baseline['sessions']) / 10, 1.0)

    if confidence < 0.5:
        return None

    if token_improvement < 0.05 and trust_improvement < 0.02 and level_improvement < 0.1:
        return {
            'type': 'stagnation',
            'confidence': round(confidence, 2),
            'message': (
                f"Kiwi not improving: tokens {token_improvement:+.1%}, "
                f"trust {trust_improvement:+.3f}, level {level_improvement:+.1f}. "
                f"Check learning pipeline."
            ),
            'metrics': {
                'token_improvement': round(token_improvement, 4),
                'trust_improvement': round(trust_improvement, 4),
                'level_improvement': round(level_improvement, 2),
            },
            'suggestions': _suggest_fixes(token_improvement, trust_improvement, level_improvement),
        }

    return None


def _get_period_metrics(conn, week_start: int, week_end: int) -> dict | None:
    row = conn.execute(
        "SELECT AVG(tokens_estimated), AVG(trust_score), AVG(brief_level), COUNT(*) "
        "FROM output_quality WHERE week BETWEEN ? AND ?",
        (week_start, week_end)
    ).fetchone()

    if not row or row[3] < 3:
        return None

    return {
        'avg_tokens': row[0] or 0,
        'avg_trust': row[1] or 0,
        'avg_level': row[2] or 0,
        'sessions': row[3],
    }


def _suggest_fixes(token_imp: float, trust_imp: float, level_imp: float) -> list:
    suggestions = []

    if token_imp < 0:
        suggestions.append("Tokens increasing — briefs may be causing confusion (Claude re-reading more)")

    if trust_imp < 0:
        suggestions.append("Trust decreasing — run smart_forget() to clear stale knowledge")

    if level_imp == 0 and trust_imp >= 0:
        suggestions.append("Level stuck but trust OK — may need more data for level-up threshold")

    if not suggestions:
        suggestions.append("All metrics flat — check if learning pipeline is running (sessions being processed?)")

    return suggestions