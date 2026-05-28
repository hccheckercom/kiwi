"""Kiwi Learner — extracts patterns from Claude sessions. 0 LLM token."""

import json
import re
import time
from collections import Counter
from pathlib import Path

from .session_logger import (
    _get_conn,
    get_session_reads,
    get_session_writes,
    get_read_order_before_write,
    mark_session_processed,
)


def learn_from_session(session_id: str) -> dict:
    """Parse session log -> extract patterns -> update memory. 0 token."""
    reads = get_session_reads(session_id)
    writes = get_session_writes(session_id)

    if not writes:
        return {"status": "skipped", "reason": "no_writes"}

    theme_writes = [w for w in writes if _is_theme_file(w["file"])]
    if not theme_writes:
        mark_session_processed(session_id)
        return {"status": "skipped", "reason": "no_theme_files"}

    task_type = _infer_task_type([w["file"] for w in theme_writes])
    theme = _detect_theme([w["file"] for w in theme_writes])

    learned = {"status": "learned", "context_patterns": 0, "style_updates": 0, "bindings": 0}

    # 1. Save context pattern
    _save_context_pattern(
        task_type=task_type,
        files_read=[r["file"] for r in reads if r["file"]],
        files_written=[w["file"] for w in theme_writes],
        read_order=[r["file"] for r in reads if r["file"]],
        theme=theme,
        session_id=session_id,
    )
    learned["context_patterns"] = 1

    # 2. Extract style + bindings from written files
    for w in theme_writes:
        fp = w["file"]
        if not fp or not Path(fp).exists():
            continue
        try:
            content = Path(fp).read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue

        styles = _extract_styles(content)
        if styles:
            _merge_styles(theme, styles)
            learned["style_updates"] += len(styles)

        bindings = _extract_bindings(content)
        if bindings:
            _save_bindings(task_type, bindings, theme)
            learned["bindings"] += len(bindings)

    # 3. Compute session quality signals → populate output_quality
    try:
        quality = _compute_session_quality(session_id, task_type)
        learned["quality"] = quality
    except Exception:
        learned["quality"] = {"error": "output_quality table may be missing"}

    # 4. R4: Detect novel patterns (reuse bindings already extracted in step 2)
    try:
        from .novel_detector import detect_novel_bindings, record_novel_pattern
        for w in theme_writes:
            fp = w["file"]
            if not fp or not Path(fp).exists():
                continue
            content = Path(fp).read_text(encoding="utf-8", errors="ignore")
            file_bindings = _extract_bindings(content)
            novel = detect_novel_bindings(file_bindings, task_type, theme)
            for pattern in novel:
                record_novel_pattern(pattern, "binding", theme, task_type, fp)
            learned["novel_patterns"] = learned.get("novel_patterns", 0) + len(novel)
    except Exception:
        pass

    mark_session_processed(session_id)
    return learned


def learn_all_unprocessed() -> list:
    """Learn from all unprocessed sessions."""
    from .session_logger import get_unprocessed_sessions

    sessions = get_unprocessed_sessions(min_writes=1)
    results = []
    for s in sessions:
        result = learn_from_session(s["session_id"])
        results.append({"session_id": s["session_id"], **result})
    return results


# --- Pattern extraction (pure Python, 0 token) ---


def _extract_styles(content: str) -> dict:
    styles = {}

    spacing = re.findall(r"py-(\d+)\s+(?:md:py-(\d+))?", content)
    if spacing:
        styles["spacing_base"] = Counter(s[0] for s in spacing).most_common(1)[0][0]
        md_vals = [s[1] for s in spacing if s[1]]
        if md_vals:
            styles["spacing_md"] = Counter(md_vals).most_common(1)[0][0]

    radius = re.findall(r"rounded-(\w+)", content)
    if radius:
        styles["radius"] = Counter(radius).most_common(1)[0][0]

    container = re.findall(r"max-w-(\w+)", content)
    if container:
        styles["container"] = Counter(container).most_common(1)[0][0]

    shadow = re.findall(r"shadow-(\w+)", content)
    shadow = [s for s in shadow if s not in ("none",)]
    if shadow:
        styles["shadow"] = Counter(shadow).most_common(1)[0][0]

    grid = re.findall(r"(?:md:|lg:)?grid-cols-(\d+)", content)
    if grid:
        styles["grid_cols"] = Counter(grid).most_common(1)[0][0]

    return styles


def _extract_bindings(content: str) -> list:
    bindings = set()

    wz_calls = re.findall(r"(wz_\w+)\s*\(", content)
    bindings.update(wz_calls)

    product_keys = re.findall(r"\$product\['(\w+)'\]", content)
    bindings.update(f"$product['{k}']" for k in product_keys)

    hooks = re.findall(r"(?:do_action|apply_filters)\s*\(\s*'(wezone_\w+)'", content)
    bindings.update(hooks)

    components = re.findall(r"wz_component\s*\(\s*'([^']+)'", content)
    bindings.update(f"wz_component('{c}')" for c in components)

    return list(bindings)


# --- Task type inference ---


def _infer_task_type(files: list) -> str:
    keywords = {
        "checkout": "checkout_page",
        "cart": "cart_page",
        "product": "product_page",
        "single": "product_page",
        "home": "home_page",
        "index": "home_page",
        "archive": "archive_page",
        "search": "search_page",
        "account": "account_page",
        "login": "login_page",
        "thank": "thankyou_page",
        "order": "order_page",
        "wishlist": "wishlist_page",
        "dashboard": "dashboard_page",
        "hero": "hero_component",
        "header": "header_component",
        "footer": "footer_component",
    }

    for f in files:
        if not f:
            continue
        normalized = f.replace("\\", "/").lower()
        for kw, task_type in keywords.items():
            if kw in normalized:
                return task_type

    exts = [Path(f).suffix.lower() for f in files if f]
    if all(e == ".css" for e in exts):
        return "fix_css"
    if all(e == ".js" for e in exts):
        return "fix_js"

    return "generic"


def _detect_theme(paths: list) -> str:
    for p in paths:
        if not p:
            continue
        normalized = p.replace("\\", "/")
        if "themes/" in normalized:
            parts = normalized.split("themes/")[1].split("/")
            if parts:
                return parts[0]
    return "unknown"


def _is_theme_file(path: str) -> bool:
    if not path:
        return False
    normalized = path.replace("\\", "/")
    return "themes/" in normalized


# --- DB operations ---


def _save_context_pattern(task_type, files_read, files_written, read_order, theme, session_id):
    conn = _get_conn()
    conn.execute(
        "INSERT INTO context_patterns (task_type, files_read, files_written, read_order, theme, session_id, created_at) "
        "VALUES (?, ?, ?, ?, ?, ?, ?)",
        (
            task_type,
            json.dumps(files_read, ensure_ascii=False),
            json.dumps(files_written, ensure_ascii=False),
            json.dumps(read_order, ensure_ascii=False),
            theme,
            session_id,
            time.time(),
        ),
    )
    # FIFO eviction: max 1000 patterns per task_type
    count = conn.execute(
        "SELECT COUNT(*) FROM context_patterns WHERE task_type = ?", (task_type,)
    ).fetchone()[0]
    if count > 1000:
        conn.execute(
            "DELETE FROM context_patterns WHERE id IN ("
            "  SELECT id FROM context_patterns WHERE task_type = ? ORDER BY created_at ASC LIMIT ?"
            ")",
            (task_type, count - 1000),
        )
    conn.commit()


def _merge_styles(theme: str, styles: dict):
    conn = _get_conn()
    now = time.time()
    for key, value in styles.items():
        if value is None:
            continue
        existing = conn.execute(
            "SELECT value, times_seen FROM style_knowledge WHERE theme = ? AND pattern_key = ?",
            (theme, key),
        ).fetchone()

        if existing:
            if existing[0] == value:
                conn.execute(
                    "UPDATE style_knowledge SET times_seen = times_seen + 1, last_seen = ? "
                    "WHERE theme = ? AND pattern_key = ?",
                    (now, theme, key),
                )
            else:
                conn.execute(
                    "UPDATE style_knowledge SET value = ?, times_seen = 1, last_seen = ? "
                    "WHERE theme = ? AND pattern_key = ?",
                    (value, now, theme, key),
                )
        else:
            conn.execute(
                "INSERT INTO style_knowledge (theme, pattern_key, value, times_seen, last_seen) "
                "VALUES (?, ?, ?, 1, ?)",
                (theme, key, value, now),
            )
    conn.commit()


def _save_bindings(task_type: str, bindings: list, theme: str):
    conn = _get_conn()
    now = time.time()
    for binding in bindings:
        conn.execute(
            "INSERT INTO binding_knowledge (task_type, binding, theme, times_seen, last_seen) "
            "VALUES (?, ?, ?, 1, ?) "
            "ON CONFLICT(task_type, binding, theme) DO UPDATE SET "
            "times_seen = times_seen + 1, last_seen = ?",
            (task_type, binding, theme, now, now),
        )
    conn.commit()


# --- Accuracy detector (R2 closed loop) ---


def _compute_session_quality(session_id: str, task_type: str) -> dict:
    """Analyze session signals to measure brief usefulness. Populates output_quality."""
    conn = _get_conn()

    # Count files read more than once (re-read = brief missed something)
    re_reads = conn.execute(
        "SELECT COUNT(*) FROM ("
        "  SELECT file_path FROM session_log"
        "  WHERE session_id = ? AND tool = 'Read' AND file_path IS NOT NULL"
        "  GROUP BY file_path HAVING COUNT(*) > 1"
        ")",
        (session_id,),
    ).fetchone()[0]

    # Count files edited more than twice (trial-and-error = brief was wrong)
    multi_edits = conn.execute(
        "SELECT COUNT(*) FROM ("
        "  SELECT file_path FROM session_log"
        "  WHERE session_id = ? AND tool IN ('Edit', 'Write') AND file_path IS NOT NULL"
        "  GROUP BY file_path HAVING COUNT(*) > 2"
        ")",
        (session_id,),
    ).fetchone()[0]

    # Total tool calls in session
    total_calls = conn.execute(
        "SELECT COUNT(*) FROM session_log WHERE session_id = ?",
        (session_id,),
    ).fetchone()[0]

    week = int(time.time() / 604800)

    conn.execute(
        "INSERT INTO output_quality "
        "(session_id, week, task_type, trust_score, files_re_read, "
        "edits_after_first, total_tool_calls, created_at) "
        "VALUES (?, ?, ?, NULL, ?, ?, ?, ?)",
        (session_id, week, task_type, re_reads, multi_edits, total_calls, time.time()),
    )
    conn.commit()

    return {"re_reads": re_reads, "multi_edits": multi_edits, "total_calls": total_calls}


def calibrate_trust_baselines():
    """Aggregate output_quality → update trust_baselines per task_type.
    Call periodically (e.g., every 10 sessions or weekly)."""
    conn = _get_conn()
    try:
        rows = conn.execute(
            "SELECT task_type, AVG(files_re_read), AVG(edits_after_first), COUNT(*) "
            "FROM output_quality GROUP BY task_type HAVING COUNT(*) >= 3"
        ).fetchall()

        now = time.time()
        for task_type, avg_re_reads, avg_multi_edits, count in rows:
            # Lower re-reads + multi-edits = higher trust (brief was useful)
            # Scale: 0 re-reads + 0 multi-edits = 1.0, 5+ each = 0.3
            penalty = min((avg_re_reads * 0.08) + (avg_multi_edits * 0.12), 0.7)
            trust = max(1.0 - penalty, 0.3)

            conn.execute(
                "INSERT INTO trust_baselines (task_type, trust_score, last_calibrated, calibration_count) "
                "VALUES (?, ?, ?, 1) "
                "ON CONFLICT(task_type) DO UPDATE SET "
                "trust_score = ?, last_calibrated = ?, calibration_count = calibration_count + 1",
                (task_type, trust, now, trust, now),
            )
        conn.commit()
        return {"calibrated": len(rows)}
    except Exception:
        return {"calibrated": 0, "error": "calibration failed"}