"""R5 — Cross-Theme Transfer: multi-pattern support with layout clustering."""

import hashlib
import json
import time

from .session_logger import _get_conn

MAX_PATTERNS_PER_TASK = 3


def _layout_hash(structure: dict) -> str:
    keys = sorted(structure.keys()) if structure else []
    return hashlib.md5("|".join(keys).encode()).hexdigest()[:12]


def find_transferable_pattern(task_type: str, target_theme: str) -> dict | None:
    """Find the best successful pattern from other themes for this task_type."""
    conn = _get_conn()
    if not conn:
        return None

    try:
        rows = conn.execute(
            "SELECT structure, themes_applied, bindings, success_count, failure_count "
            "FROM cross_theme_patterns WHERE task_type = ? "
            "ORDER BY success_count DESC",
            (task_type,),
        ).fetchall()

        if not rows:
            return None

        best = None
        best_rate = 0.0
        for row in rows:
            success_count = row[3]
            failure_count = row[4]
            if success_count < 2:
                continue
            rate = success_count / max(success_count + failure_count, 1)
            if rate < 0.7:
                continue
            if rate > best_rate:
                best_rate = rate
                structure = json.loads(row[0]) if row[0] else {}
                themes_applied = json.loads(row[1]) if row[1] else []
                bindings = json.loads(row[2]) if row[2] else []
                best = {
                    "task_type": task_type,
                    "structure": structure,
                    "source_themes": themes_applied,
                    "bindings": bindings,
                    "confidence": round(rate, 2),
                    "is_new_for_theme": target_theme not in themes_applied,
                }

        return best
    except Exception:
        return None


def record_pattern_outcome(task_type: str, theme: str, structure: dict,
                           bindings: list, success: bool):
    """After session: record whether the cross-theme pattern worked."""
    conn = _get_conn()
    if not conn:
        return

    try:
        lhash = _layout_hash(structure)
        existing = conn.execute(
            "SELECT id, themes_applied FROM cross_theme_patterns "
            "WHERE task_type = ? AND layout_hash = ?",
            (task_type, lhash),
        ).fetchone()

        now = time.time()
        if existing:
            themes = json.loads(existing[1]) if existing[1] else []
            if theme not in themes:
                themes.append(theme)

            col = "success_count" if success else "failure_count"
            conn.execute(
                f"UPDATE cross_theme_patterns SET themes_applied = ?, "
                f"structure = ?, bindings = ?, "
                f"{col} = {col} + 1, last_updated = ? WHERE id = ?",
                (json.dumps(themes), json.dumps(structure), json.dumps(bindings), now, existing[0]),
            )
        else:
            _evict_if_needed(conn, task_type)
            conn.execute(
                "INSERT INTO cross_theme_patterns "
                "(task_type, layout_hash, structure, themes_applied, bindings, "
                "success_count, failure_count, last_updated) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (task_type, lhash, json.dumps(structure), json.dumps([theme]),
                 json.dumps(bindings), 1 if success else 0, 0 if success else 1, now),
            )
        conn.commit()
    except Exception:
        pass


def _evict_if_needed(conn, task_type: str):
    """Keep max MAX_PATTERNS_PER_TASK patterns per task_type. Evict lowest success_rate."""
    count = conn.execute(
        "SELECT COUNT(*) FROM cross_theme_patterns WHERE task_type = ?",
        (task_type,),
    ).fetchone()[0]

    if count >= MAX_PATTERNS_PER_TASK:
        worst = conn.execute(
            "SELECT id, success_count, failure_count FROM cross_theme_patterns "
            "WHERE task_type = ? ORDER BY "
            "CAST(success_count AS REAL) / MAX(success_count + failure_count, 1) ASC "
            "LIMIT 1",
            (task_type,),
        ).fetchone()
        if worst:
            conn.execute("DELETE FROM cross_theme_patterns WHERE id = ?", (worst[0],))