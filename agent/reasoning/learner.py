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
    """Parse session log -> extract patterns -> update memory. 0 token.

    Incremental: only re-process files that have changed (mtime) since the
    last learn pass for this session. Earlier passes already extracted from
    older versions; re-extracting them every 5 writes is O(N²) wasted work.
    """
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

    learned = {
        "status": "learned",
        "context_patterns": 0,
        "style_updates": 0,
        "bindings": 0,
        "novel_patterns": 0,
        "files_processed": 0,
        "files_skipped": 0,
    }

    # 1. Save context pattern (always — captures full session shape)
    _save_context_pattern(
        task_type=task_type,
        files_read=[r["file"] for r in reads if r["file"]],
        files_written=[w["file"] for w in theme_writes],
        read_order=[r["file"] for r in reads if r["file"]],
        theme=theme,
        session_id=session_id,
    )
    learned["context_patterns"] = 1

    # Determine which files have changed since last learn pass
    last_seen = _get_last_learned_files(session_id)
    pending_files = []
    for w in theme_writes:
        fp = w["file"]
        if not fp:
            continue
        try:
            path_obj = Path(fp)
            if not path_obj.exists():
                continue
            mtime = path_obj.stat().st_mtime
        except OSError:
            continue
        if last_seen.get(fp) == mtime:
            learned["files_skipped"] += 1
            continue
        pending_files.append((fp, path_obj, mtime))

    # 2. Extract style + bindings + novel detection in single pass per file
    try:
        from .novel_detector import detect_novel_bindings, record_novel_pattern
        novel_enabled = True
    except Exception:
        novel_enabled = False

    new_seen = dict(last_seen)
    for fp, path_obj, mtime in pending_files:
        try:
            content = path_obj.read_text(encoding="utf-8", errors="ignore")
        except (OSError, ValueError):
            continue

        learned["files_processed"] += 1

        styles = _extract_styles(content)
        if styles:
            _merge_styles(theme, styles)
            learned["style_updates"] += len(styles)

        bindings = _extract_bindings(content, theme)
        if bindings:
            _save_bindings(task_type, bindings, theme)
            learned["bindings"] += len(bindings)

            if novel_enabled:
                try:
                    novel = detect_novel_bindings(bindings, task_type, theme)
                    for pattern in novel:
                        record_novel_pattern(pattern, "binding", theme, task_type, fp)
                    learned["novel_patterns"] += len(novel)
                except Exception:
                    pass

        new_seen[fp] = mtime

    if new_seen != last_seen:
        _set_last_learned_files(session_id, new_seen)

    # 3. Compute session quality signals → populate output_quality
    try:
        quality = _compute_session_quality(session_id, task_type)
        learned["quality"] = quality
    except Exception as e:
        learned["quality"] = {"error": "output_quality table may be missing"}
        try:
            from hooks.post_edit import _log_learning_error
            _log_learning_error("compute_quality", e)
        except Exception:
            pass

    return learned


def _get_last_learned_files(session_id: str) -> dict:
    """Return {file_path: mtime} processed in earlier learn passes."""
    conn = _get_conn()
    try:
        row = conn.execute(
            "SELECT last_learned_files FROM session_learn_state WHERE session_id = ?",
            (session_id,),
        ).fetchone()
        if row and row[0]:
            return json.loads(row[0])
    except Exception:
        pass
    return {}


def _set_last_learned_files(session_id: str, files: dict) -> None:
    conn = _get_conn()
    try:
        # Cap stored map to avoid bloat on huge sessions
        if len(files) > 500:
            sorted_items = sorted(files.items(), key=lambda kv: kv[1], reverse=True)[:500]
            files = dict(sorted_items)
        payload = json.dumps(files, ensure_ascii=False)
        conn.execute(
            "INSERT INTO session_learn_state (session_id, last_learned_writes, last_learned_at, last_learned_files) "
            "VALUES (?, COALESCE((SELECT last_learned_writes FROM session_learn_state WHERE session_id = ?), 0), "
            "strftime('%s', 'now'), ?) "
            "ON CONFLICT(session_id) DO UPDATE SET last_learned_files = excluded.last_learned_files, "
            "last_learned_at = excluded.last_learned_at",
            (session_id, session_id, payload),
        )
        conn.commit()
    except Exception:
        pass


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


def _extract_bindings(content: str, theme: str = "") -> list:
    if not content:
        return []
    if len(content) > _EXTRACT_MAX_BYTES:
        content = content[:_EXTRACT_MAX_BYTES]
    content = _strip_php_comments(content)

    bindings = set()

    bindings.update(_RE_WZ_CALL.findall(content))
    bindings.update(f"$product['{k}']" for k in _RE_PRODUCT_KEY.findall(content))
    bindings.update(_RE_WEZONE_HOOK.findall(content))
    bindings.update(f"wz_component('{c}')" for c in _RE_WZ_COMPONENT.findall(content))

    bindings.update(f"wp:{f}" for f in _RE_WP_FUNC_CURATED.findall(content))
    bindings.update(
        f"wp:{f}" for f in _RE_WP_FUNC_PREFIX.findall(content)
        if f not in _WP_FUNC_BLACKLIST
    )
    bindings.update(f"wp:{f}" for f in _RE_WP_CHECK.findall(content))

    for h in _RE_HOOK_NAME.findall(content):
        if not h.startswith("wezone_"):
            bindings.add(f"hook:{h}")

    if theme and theme not in ("unknown", ""):
        prefix = theme.replace("-", "_").lower()
        prefix_funcs = re.findall(rf"\b({re.escape(prefix)}_\w+)\s*\(", content)
        bindings.update(f"theme:{f}" for f in prefix_funcs)

        prefix_const_re = re.compile(rf"\b({re.escape(prefix.upper())}_[A-Z][A-Z0-9_]*)\b")
        for c in set(prefix_const_re.findall(content)):
            if c in _WP_CONST_BLACKLIST:
                continue
            bindings.add(f"const:{c}")

    return list(bindings)


_EXTRACT_MAX_BYTES = 200 * 1024  # cap regex work on huge files (~200KB)

_RE_PHP_BLOCK_COMMENT = re.compile(r"/\*.*?\*/", re.DOTALL)
_RE_PHP_LINE_COMMENT = re.compile(r"(?<!:)//[^\n]*|^\s*#[^\n]*", re.MULTILINE)


def _strip_php_comments(content: str) -> str:
    """Remove PHP/JS comments before regex extraction so commented-out code
    (e.g. ``// example: wp_nav_menu()``) does not produce false positives."""
    content = _RE_PHP_BLOCK_COMMENT.sub("", content)
    content = _RE_PHP_LINE_COMMENT.sub("", content)
    return content


_RE_WZ_CALL = re.compile(r"(wz_\w+)\s*\(")
_RE_PRODUCT_KEY = re.compile(r"\$product\['(\w+)'\]")
_RE_WEZONE_HOOK = re.compile(r"(?:do_action|apply_filters)\s*\(\s*'(wezone_\w+)'")
_RE_WZ_COMPONENT = re.compile(r"wz_component\s*\(\s*'([^']+)'")

_RE_WP_FUNC_CURATED = re.compile(
    r"\b(get_theme_mod|get_template_part|wp_nav_menu|wp_head|wp_footer|"
    r"wp_enqueue_script|wp_enqueue_style|bloginfo|language_attributes|"
    r"add_theme_support|register_nav_menus|add_action|add_filter|"
    r"esc_html|esc_url|esc_attr|esc_html_e|esc_attr_e|wp_register_script|"
    r"wp_localize_script|wp_create_nonce|check_ajax_referer|wp_send_json|"
    r"register_post_type|register_taxonomy|wp_insert_post|update_post_meta|"
    r"get_post_meta|wp_get_nav_menu_object|home_url|admin_url|site_url|"
    r"wp_kses|wp_kses_post|wp_safe_redirect|sanitize_text_field|"
    r"sanitize_email|sanitize_key|sanitize_title|wp_verify_nonce|"
    r"wp_die|current_user_can|is_admin|is_user_logged_in|get_current_user_id|"
    r"get_post|get_posts|wp_query|wp_reset_postdata|have_posts|the_post|"
    r"the_content|the_title|the_permalink|get_the_ID|get_permalink|"
    r"get_option|update_option|delete_option|wp_get_attachment_image|"
    r"wp_get_attachment_url|get_the_post_thumbnail|has_post_thumbnail)\s*\("
)

_RE_WP_FUNC_PREFIX = re.compile(r"\b(wp_[a-z][a-z0-9_]*)\s*\(")

_WP_FUNC_BLACKLIST = frozenset({
    "wp_die",
    "wp_send_json",
    "wp_safe_redirect",
})

_RE_WP_CHECK = re.compile(r"\b(is_[a-z][a-z0-9_]*|has_[a-z][a-z0-9_]*)\s*\(")

_RE_HOOK_NAME = re.compile(
    r"(?:add_action|add_filter|do_action|apply_filters)\s*\(\s*'([a-z_][a-z0-9_]*)'"
)

_WP_CONST_BLACKLIST = frozenset({
    "WP_DEBUG", "WP_DEBUG_LOG", "WP_DEBUG_DISPLAY", "WP_HOME", "WP_SITEURL",
    "WP_CONTENT_DIR", "WP_CONTENT_URL", "WP_PLUGIN_DIR", "WP_PLUGIN_URL",
    "WPINC", "ABSPATH", "WP_LANG_DIR", "WP_TEMP_DIR",
    "WP_MEMORY_LIMIT", "WP_MAX_MEMORY_LIMIT", "WP_AUTO_UPDATE_CORE",
    "WP_DEFAULT_THEME", "WP_USE_THEMES", "WP_CACHE",
})


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
    # Global cap (BUG #12): hard ceiling across all task_types to bound DB size
    total = conn.execute("SELECT COUNT(*) FROM context_patterns").fetchone()[0]
    if total > _CONTEXT_PATTERNS_GLOBAL_CAP:
        conn.execute(
            "DELETE FROM context_patterns WHERE id IN ("
            "  SELECT id FROM context_patterns ORDER BY created_at ASC LIMIT ?"
            ")",
            (total - _CONTEXT_PATTERNS_GLOBAL_CAP,),
        )
    conn.commit()


_CONTEXT_PATTERNS_GLOBAL_CAP = 5000


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
    if not bindings:
        return
    valid = _sanitize_bindings(bindings)
    if not valid:
        return
    conn = _get_conn()
    now = time.time()
    for binding in valid:
        conn.execute(
            "INSERT INTO binding_knowledge (task_type, binding, theme, times_seen, last_seen) "
            "VALUES (?, ?, ?, 1, ?) "
            "ON CONFLICT(task_type, binding, theme) DO UPDATE SET "
            "times_seen = times_seen + 1, last_seen = ?",
            (task_type, binding, theme, now, now),
        )
    conn.commit()


_BINDING_MAX_LEN = 200
_BINDING_VALID_RE = re.compile(r"^[A-Za-z0-9_:$\[\]'\"\-./()]+$")


def _sanitize_bindings(bindings: list) -> list:
    """Drop bindings that are empty, too long, contain control chars, or
    fail a printable-ASCII whitelist. Prevents DB bloat and dirty data
    when a regex match accidentally captures junk."""
    out = []
    seen = set()
    for b in bindings:
        if not isinstance(b, str):
            continue
        s = b.strip()
        if not s or len(s) > _BINDING_MAX_LEN:
            continue
        if "\x00" in s or any(ord(c) < 32 for c in s):
            continue
        if not _BINDING_VALID_RE.match(s):
            continue
        if s in seen:
            continue
        seen.add(s)
        out.append(s)
    return out


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