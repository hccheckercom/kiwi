"""R1 — Trust Scorer: 6-dimension trust score with learned data, 0 LLM token."""

import sqlite3
from pathlib import Path


_DB_PATH = Path(__file__).parent.parent.parent / "memory" / "reasoning.db"


def compute_trust_score(context, theme_path: str) -> tuple[float, dict]:
    from .context_assembler import PROJECT_ROOT

    theme_name = context.theme.get('name', 'unknown') if isinstance(context.theme, dict) else 'unknown'
    task_type = context.task_type

    scores = {}
    scores['spec_found'] = 1.0 if (context.spec and context.spec.get('found')) else 0.3
    scores['theme_maturity'] = _check_theme_maturity(theme_path, PROJECT_ROOT)
    scores['bindings'] = 1.0 if context.bindings else 0.4
    scores['references'] = min(len(context.reference_pages) / 3, 1.0)
    scores['lessons'] = min(len(context.lessons) / 5, 1.0)
    scores['learned_data'] = _check_learned_data(task_type, theme_name)

    weights = {
        'spec_found': 0.25,
        'theme_maturity': 0.20,
        'bindings': 0.20,
        'references': 0.15,
        'lessons': 0.10,
        'learned_data': 0.10,
    }
    trust = sum(scores[k] * weights[k] for k in scores)

    # Blend with calibrated baseline if available
    trust = _blend_with_baseline(task_type, trust)

    return trust, scores


def _check_theme_maturity(theme_path: str, project_root: Path) -> float:
    path = Path(theme_path)
    if not path.is_absolute():
        path = project_root / path

    if not path.exists():
        return 0.0

    php_count = len(list(path.rglob('*.php')))

    if php_count >= 30:
        return 1.0
    elif php_count >= 15:
        return 0.8
    elif php_count >= 5:
        return 0.5
    return 0.2


def _get_conn() -> sqlite3.Connection | None:
    if not _DB_PATH.exists():
        return None
    try:
        conn = sqlite3.connect(str(_DB_PATH), timeout=3)
        conn.execute("PRAGMA journal_mode=WAL")
        return conn
    except sqlite3.Error:
        return None


def _check_learned_data(task_type: str, theme: str) -> float:
    """Score based on how much learned data exists for this task+theme."""
    conn = _get_conn()
    if not conn:
        return 0.0
    try:
        style_count = conn.execute(
            "SELECT COUNT(*) FROM style_knowledge WHERE theme = ? AND times_seen >= 3",
            (theme,),
        ).fetchone()[0]
        binding_count = conn.execute(
            "SELECT COUNT(*) FROM binding_knowledge "
            "WHERE task_type = ? AND theme = ? AND times_seen >= 2",
            (task_type, theme),
        ).fetchone()[0]

        if style_count >= 5 and binding_count >= 5:
            return 1.0
        elif style_count >= 3 or binding_count >= 3:
            return 0.7
        elif style_count >= 1 or binding_count >= 1:
            return 0.4
        return 0.0
    except sqlite3.Error:
        return 0.0
    finally:
        conn.close()


def _blend_with_baseline(task_type: str, computed: float) -> float:
    """Blend computed trust with historical baseline (if calibrated)."""
    conn = _get_conn()
    if not conn:
        return computed
    try:
        row = conn.execute(
            "SELECT trust_score, calibration_count FROM trust_baselines WHERE task_type = ?",
            (task_type,),
        ).fetchone()
        if not row or row[1] < 3:
            return computed
        baseline = row[0]
        # Weighted average: 70% computed, 30% historical baseline
        return computed * 0.7 + baseline * 0.3
    except sqlite3.Error:
        return computed
    finally:
        conn.close()