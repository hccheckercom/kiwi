"""R8 — Think Cache: avoid re-thinking the same question. Per-trigger TTL."""

import json
import time

from .session_logger import _get_conn

TRIGGER_TTL = {
    'pattern_conflict': 1800,
    'borderline_trust': 900,
    'novel_validation': 86400,
    'style_ambiguity': 86400,
}

DEFAULT_TTL = 3600
MAX_CACHE_SIZE = 200


def get_cached(cache_key: str, trigger: str) -> dict | None:
    conn = _get_conn()
    if not conn:
        return None

    try:
        row = conn.execute(
            "SELECT decision, reasoning, confidence, extra, created_at "
            "FROM think_cache WHERE cache_key = ?",
            (cache_key,),
        ).fetchone()

        if not row:
            return None

        ttl = TRIGGER_TTL.get(trigger, DEFAULT_TTL)
        if (time.time() - row[4]) > ttl:
            conn.execute("DELETE FROM think_cache WHERE cache_key = ?", (cache_key,))
            conn.commit()
            return None

        extra = {}
        if row[3]:
            try:
                extra = json.loads(row[3])
            except (json.JSONDecodeError, TypeError):
                pass

        return {
            'decision': row[0],
            'reasoning': row[1],
            'confidence': row[2],
            'extra': extra,
        }
    except Exception:
        return None


def save_cached(cache_key: str, trigger: str, task_type: str, theme: str, result: dict):
    conn = _get_conn()
    if not conn:
        return

    extra_json = json.dumps(result.get('extra', {})) if result.get('extra') else None

    try:
        conn.execute(
            "INSERT OR REPLACE INTO think_cache "
            "(cache_key, trigger, task_type, theme, decision, reasoning, confidence, extra, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (cache_key, trigger, task_type, theme,
             result['decision'], result.get('reasoning', ''),
             result.get('confidence', 0.5), extra_json, time.time()),
        )

        count = conn.execute("SELECT COUNT(*) FROM think_cache").fetchone()[0]
        if count > MAX_CACHE_SIZE:
            conn.execute(
                "DELETE FROM think_cache WHERE rowid IN ("
                "  SELECT rowid FROM think_cache ORDER BY created_at ASC LIMIT ?"
                ")",
                (count - MAX_CACHE_SIZE,),
            )
        conn.commit()
    except Exception:
        pass


def invalidate_cache(task_type: str = None, theme: str = None, trigger: str = None):
    conn = _get_conn()
    if not conn:
        return

    try:
        conditions = []
        params = []
        if task_type:
            conditions.append("task_type = ?")
            params.append(task_type)
        if theme:
            conditions.append("theme = ?")
            params.append(theme)
        if trigger:
            conditions.append("trigger = ?")
            params.append(trigger)

        if not conditions:
            return

        conn.execute(
            f"DELETE FROM think_cache WHERE {' AND '.join(conditions)}",
            params,
        )
        conn.commit()
    except Exception:
        pass
