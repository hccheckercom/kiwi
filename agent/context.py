"""Pre-code context builder — inject Kiwi knowledge BEFORE Claude writes code."""

import os
import re
import sys
import time
from pathlib import Path

KIWI_DIR = Path(__file__).parent.parent


class _Health:
    """Track subsystem status so degradation is visible, not silent."""

    def __init__(self):
        self.subsystems = {}

    def ok(self, name):
        self.subsystems[name] = {"status": "ok"}

    def degraded(self, name, why):
        self.subsystems[name] = {"status": "degraded", "reason": why}

    def unavailable(self, name, why):
        self.subsystems[name] = {"status": "unavailable", "reason": why}

    def report(self):
        return [
            {"name": k, **v}
            for k, v in self.subsystems.items()
            if v["status"] != "ok"
        ]

# --- F1: Task-to-Category Mapping ---
_TASK_CATEGORY_MAP = {
    # E-commerce / checkout
    "checkout": ["wezone-api", "js-contract", "php-security", "performance"],
    "payment": ["wezone-api", "php-security", "concurrency"],
    "cart": ["wezone-api", "js-contract", "edge-cases"],
    "order": ["wezone-api", "php-security", "db-schema"],
    "thanh toán": ["wezone-api", "php-security", "concurrency"],
    "đơn hàng": ["wezone-api", "php-security", "db-schema"],
    "giỏ hàng": ["wezone-api", "js-contract", "edge-cases"],
    "shipping": ["wezone-api", "edge-cases"],
    "vận chuyển": ["wezone-api", "edge-cases"],
    # Frontend
    "css": ["css-tokens"],
    "responsive": ["css-tokens"],
    "mobile": ["css-tokens", "edge-cases"],
    "tailwind": ["css-tokens"],
    "design": ["css-tokens", "file-structure"],
    "dark mode": ["css-tokens"],
    "animation": ["css-tokens", "performance"],
    # Performance
    "flash sale": ["performance", "concurrency", "db-schema"],
    "cache": ["performance"],
    "bulk": ["performance", "db-schema"],
    "import": ["db-schema", "performance"],
    "migration": ["db-schema"],
    "optimize": ["performance", "php-performance"],
    "slow": ["performance", "php-performance"],
    # Security
    "auth": ["php-security", "js-contract"],
    "login": ["php-security"],
    "nonce": ["php-security"],
    "permission": ["php-security"],
    "sanitize": ["php-security"],
    "escape": ["php-security"],
    "xss": ["php-security", "js-contract"],
    "sql injection": ["php-security", "php-db"],
    "csrf": ["php-security"],
    # API
    "rest": ["php-security", "wezone-api"],
    "ajax": ["php-security", "js-contract"],
    "api": ["wezone-api", "php-security"],
    "webhook": ["wezone-api", "concurrency"],
    "ipn": ["wezone-api", "concurrency", "php-security"],
    "endpoint": ["wezone-api", "php-security"],
    # Next.js
    "nextjs": ["nextjs-react", "supabase"],
    "react": ["nextjs-react", "react"],
    "supabase": ["supabase"],
    "component": ["nextjs-react", "react"],
    "server action": ["nextjs-react"],
    "zustand": ["nextjs-react"],
    # Ads
    "ads": ["ads-compliance"],
    "landing": ["ads-compliance", "css-tokens"],
    "seo": ["ads-compliance"],
    "google ads": ["ads-compliance"],
    "facebook ads": ["ads-compliance"],
    "policy": ["ads-compliance"],
    # Plugin/Theme dev
    "plugin": ["wezone-api", "php-security", "file-structure"],
    "theme": ["css-tokens", "file-structure", "wezone-api"],
    "loyalty": ["wezone-api", "php-security", "db-schema", "loyalty"],
    "template": ["file-structure", "wezone-api"],
    # Python / FastAPI
    "fastapi": ["fastapi", "python"],
    "python": ["python"],
    # Data
    "database": ["db-schema", "performance"],
    "query": ["performance", "db-schema", "php-security"],
    "schema": ["db-schema"],
    "wpdb": ["php-security", "php-db", "performance"],
    # Architecture
    "refactor": ["php-architecture", "performance"],
    "architecture": ["php-architecture"],
    "i18n": ["php-i18n"],
    "translate": ["php-i18n"],
    # AI
    "ai": ["ai-safety"],
    "prompt": ["ai-safety"],
    "llm": ["ai-safety"],
}

# --- F3: Static signal map (legacy fallback) ---
_STATIC_SIGNAL_MAP = [
    # PHP Security
    (re.compile(r"\$_(GET|POST|REQUEST|COOKIE)\["), {"LES-045", "LES-016", "LES-030"}),
    (re.compile(r"wp_ajax_"), {"LES-064", "LES-055", "LES-003"}),
    (re.compile(r"register_rest_route"), {"LES-070", "LES-071", "LES-073", "LES-074"}),
    (re.compile(r"\$wpdb\s*->"), {"LES-080", "LES-392", "LES-345"}),
    (re.compile(r"wp_mail\s*\("), {"LES-031"}),
    (re.compile(r"(?:include|require)(?:_once)?\s*\(\s*\$"), {"LES-046"}),
    (re.compile(r"handle_.*?(?:ipn|webhook)", re.IGNORECASE), {"LES-081"}),
    (re.compile(r"wp_remote_(?:get|post|request)\s*\("), {"LES-098"}),
    (re.compile(r"new WP_Query"), {"LES-050"}),
    (re.compile(r"define\s*\(\s*['\"]WEZONE_"), {"LES-066"}),
    (re.compile(r"WP_REST_Response\s*\("), {"LES-074"}),
    # JS Contract
    (re.compile(r"fetch\s*\("), {"LES-039", "LES-043"}),
    (re.compile(r"\.innerHTML\s*="), {"LES-008"}),
    (re.compile(r"wzTheme\."), {"LES-014"}),
    (re.compile(r"subtotal\s*[-+]"), {"LES-042"}),
    # CSS
    (re.compile(r"@media[^{]*max-width"), {"LES-007"}),
    (re.compile(r"preflight:\s*false"), {"LES-021", "LES-068"}),
    # Performance
    (re.compile(r"private\s+static\s+(?:array|\?array|string|int|bool)\s+\$"), {"LES-093"}),
    (re.compile(r"dbDelta|create_table_raw"), {"LES-067"}),
]

# --- F3: Dynamic signal index (auto-generated from all lessons) ---
_signal_index = None
_signal_index_time = 0
_SIGNAL_INDEX_TTL = 300

# --- F9: Project profile cache ---
_project_profile_cache = {}
_PROFILE_TTL = 3600


def _tokenize_task(task: str) -> set:
    """Split task into searchable keywords and bigrams."""
    words = re.split(r'[\s,;/\-_]+', task.lower().strip())
    words = [w for w in words if len(w) >= 3]
    keywords = set(words)
    for i in range(len(words) - 1):
        keywords.add(f"{words[i]} {words[i+1]}")
    return keywords


_dynamic_category_map_cache = None
_dynamic_category_map_time = 0
_DYN_MAP_TTL = 300


def _build_dynamic_category_map(patterns: list) -> dict:
    """Build keyword→categories map from lesson tags.

    Auto-extends static _TASK_CATEGORY_MAP coverage as new lessons are added.
    Cached for 5 min.
    """
    global _dynamic_category_map_cache, _dynamic_category_map_time

    if _dynamic_category_map_cache is not None and \
            (time.time() - _dynamic_category_map_time) < _DYN_MAP_TTL:
        return _dynamic_category_map_cache

    m = {}
    for p in patterns:
        cat = p.get("category")
        if not cat:
            continue
        for tag in (p.get("tags") or []):
            tag_lower = str(tag).lower().strip()
            if not tag_lower or len(tag_lower) < 3:
                continue
            m.setdefault(tag_lower, set()).add(cat)

    _dynamic_category_map_cache = m
    _dynamic_category_map_time = time.time()
    return m


def _map_task_to_categories(task: str, patterns: list = None) -> set:
    """Map task description to relevant lesson categories.

    Combines static _TASK_CATEGORY_MAP + dynamic map from lesson tags.
    """
    keywords = _tokenize_task(task)
    categories = set()
    for kw in keywords:
        if kw in _TASK_CATEGORY_MAP:
            categories.update(_TASK_CATEGORY_MAP[kw])
    if patterns:
        dyn = _build_dynamic_category_map(patterns)
        for kw in keywords:
            if kw in dyn:
                categories.update(dyn[kw])
    return categories


def _compute_tag_score(lesson_tags: list, task_keywords: set) -> int:
    """Score based on tag overlap with task keywords. Max 15."""
    if not lesson_tags or not task_keywords:
        return 0
    overlap = len(set(t.lower() for t in lesson_tags) & task_keywords)
    return min(overlap * 5, 15)


def _build_signal_index(patterns: list) -> list:
    """Build signal index from all loaded patterns. Cached for 5 min."""
    global _signal_index, _signal_index_time

    if _signal_index is not None and (time.time() - _signal_index_time) < _SIGNAL_INDEX_TTL:
        return _signal_index

    index = []
    for p in patterns:
        if p.get("type") in ("absence", "cross-check", "cross_check", "bom-check"):
            continue
        pattern_str = p.get("pattern")
        if not pattern_str or not isinstance(pattern_str, str):
            continue
        try:
            compiled = re.compile(pattern_str, re.MULTILINE)
            pre_check = p.get("pre_check")
            index.append((compiled, pre_check, p["id"]))
        except (re.error, TypeError):
            continue

    _signal_index = index
    _signal_index_time = time.time()
    return index


def _detect_signals_deep(target_file: str, patterns: list) -> dict:
    """Read target file and match against ALL lesson patterns.

    Returns {lesson_id: True} for matched lessons.
    """
    try:
        content = Path(target_file).read_text(encoding="utf-8")
    except (OSError, IOError):
        return {}

    matched = {}

    for signal_re, rule_ids in _STATIC_SIGNAL_MAP:
        if signal_re.search(content):
            for rid in rule_ids:
                matched[rid] = True

    index = _build_signal_index(patterns)
    for compiled_re, pre_check, lesson_id in index:
        if lesson_id in matched:
            continue
        if pre_check and pre_check not in content:
            continue
        try:
            if compiled_re.search(content):
                matched[lesson_id] = True
        except (re.error, RecursionError):
            continue

    return matched


def _get_db_scores(project_path: str = "", health=None) -> dict:
    """Query violations history and confidence scores from SQLite.

    Returns {lesson_id: {"history": int, "confidence": float}}
    """
    result = {}
    try:
        from memory.db import get_project_violation_counts, get_all_confidence_scores

        if project_path:
            violations = get_project_violation_counts(project_path)
            for lid, count in violations.items():
                result.setdefault(lid, {})["history"] = count

        confidence = get_all_confidence_scores()
        for lid, conf in confidence.items():
            result.setdefault(lid, {})["confidence"] = conf

        if health:
            if not result:
                health.degraded("db_scores",
                    "chưa có lịch sử vi phạm / confidence — cold-start, "
                    "scan vài vòng để tích luỹ")
            else:
                health.ok("db_scores")
    except ImportError as e:
        if health:
            health.unavailable("db_scores", f"thiếu module memory.db: {e}")
        print(f"[kiwi] _get_db_scores ImportError: {e}", file=sys.stderr)
    except Exception as e:
        if health:
            health.degraded("db_scores", str(e))
        print(f"[kiwi] _get_db_scores error: {e}", file=sys.stderr)

    return result


# --- Embedding cache for semantic search ---
_embeddings_loaded = False
_lesson_embeddings = {}  # {lesson_id: np.ndarray}


def _get_semantic_scores(task: str, patterns: list, health=None) -> dict:
    """Compute semantic similarity between task and lesson descriptions.

    Uses batch encoding for speed. First call embeds all lessons (~5s with batch),
    caches to DB. Subsequent calls load from DB cache (~0.1s).
    Returns {lesson_id: similarity_float} for lessons with similarity > 0.4.
    """
    global _embeddings_loaded, _lesson_embeddings

    if not task or len(task) < 5:
        if health:
            health.degraded("semantic", "task quá ngắn (<5 ký tự)")
        return {}

    try:
        from learning.embeddings import embed_pattern, semantic_similarity, \
            load_embedding_from_db, cache_embeddings_to_db, get_embedding_model
        import numpy as np

        task_emb = embed_pattern(task, "")

        if not _embeddings_loaded:
            # Try loading all from DB first (fast path)
            from memory.db import get_connection
            conn = get_connection()
            try:
                rows = conn.execute("SELECT lesson_id, embedding FROM embeddings").fetchall()
            finally:
                conn.close()

            if rows:
                import pickle  # nosec: loading internal embeddings from Kiwi's own DB
                for r in rows:
                    try:
                        _lesson_embeddings[r["lesson_id"]] = pickle.loads(r["embedding"])  # nosec: internal DB
                    except Exception as e:
                        print(f"[kiwi] embedding load error: {e}", file=sys.stderr)

            # Find uncached lessons
            uncached = [p for p in patterns if p["id"] not in _lesson_embeddings]

            if uncached:
                model = get_embedding_model()
                texts = [f"{p.get('pattern', '')} {p.get('description', '')} {p.get('category', '')}"
                         for p in uncached]
                embeddings = model.encode(texts, convert_to_numpy=True, batch_size=64, show_progress_bar=False)
                for p, emb in zip(uncached, embeddings):
                    _lesson_embeddings[p["id"]] = emb
                    try:
                        cache_embeddings_to_db(p["id"], emb)
                    except Exception as e:
                        print(f"[kiwi] embedding cache error: {e}", file=sys.stderr)

            _embeddings_loaded = True

        scores = {}
        for lid, emb in _lesson_embeddings.items():
            sim = semantic_similarity(task_emb, emb)
            if sim > 0.4:
                scores[lid] = sim

        if health:
            if not _lesson_embeddings:
                health.degraded("semantic", "không có lesson nào được embed")
            elif not scores:
                health.degraded("semantic",
                    "task không match lesson nào (similarity <= 0.4)")
            else:
                health.ok("semantic")
        return scores
    except ImportError as e:
        if health:
            health.unavailable("semantic", f"thiếu dependency embedding: {e}")
        print(f"[kiwi] _get_semantic_scores ImportError: {e}", file=sys.stderr)
        return {}
    except Exception as e:
        if health:
            health.degraded("semantic", str(e))
        print(f"[kiwi] _get_semantic_scores error: {e}", file=sys.stderr)
        return {}


def _get_contextual_rules(target_file: str, health=None) -> list:
    """Get AST-learned contextual rules matching the target file.

    Returns list of {context, violation, fix, confidence} dicts.
    """
    if not target_file:
        if health:
            health.degraded("contextual_rules", "không có target_file — bỏ qua AST rules")
        return []

    try:
        from learning.context_learner import get_contextual_lessons
        lessons = get_contextual_lessons(min_confidence=0.7)

        if not lessons:
            if health:
                health.degraded("contextual_rules",
                    "chưa có AST-learned rules — chạy learning vài vòng để tích luỹ")
            return []

        content = Path(target_file).read_text(encoding="utf-8")
        matched = []
        for cl in lessons:
            ctx_pattern = cl.context_pattern if hasattr(cl, 'context_pattern') else cl.get("context_pattern", "")
            if ctx_pattern and re.search(ctx_pattern, content):
                matched.append({
                    "context": ctx_pattern,
                    "violation": cl.violation_pattern if hasattr(cl, 'violation_pattern') else cl.get("violation_pattern", ""),
                    "fix": cl.fix_pattern if hasattr(cl, 'fix_pattern') else cl.get("fix_pattern", ""),
                    "confidence": cl.confidence if hasattr(cl, 'confidence') else cl.get("confidence", 0.5),
                })
        if health:
            health.ok("contextual_rules")
        return matched[:3]
    except ImportError as e:
        if health:
            health.unavailable("contextual_rules", f"thiếu module learning.context_learner: {e}")
        print(f"[kiwi] _get_contextual_rules ImportError: {e}", file=sys.stderr)
        return []
    except Exception as e:
        if health:
            health.degraded("contextual_rules", str(e))
        print(f"[kiwi] _get_contextual_rules error: {e}", file=sys.stderr)
        return []


def _get_pending_anomalies(project_path: str, health=None) -> list:
    """Get pending anomaly suggestions relevant to this project.

    Returns list of {pattern, category, severity} dicts.
    """
    if not project_path:
        return []

    try:
        from memory.db import get_connection
        conn = get_connection()
        try:
            rows = conn.execute("""
                SELECT pattern, category, severity, example_file
                FROM suggested_lessons
                WHERE status = 'pending'
                ORDER BY suggested_at DESC
                LIMIT 5
            """).fetchall()
        finally:
            conn.close()

        if health:
            health.ok("anomalies")
        return [{"pattern": r["pattern"], "category": r["category"],
                 "severity": r["severity"], "example": r["example_file"]}
                for r in rows]
    except ImportError as e:
        if health:
            health.unavailable("anomalies", f"thiếu module memory.db: {e}")
        print(f"[kiwi] _get_pending_anomalies ImportError: {e}", file=sys.stderr)
        return []
    except Exception as e:
        if health:
            health.degraded("anomalies", str(e))
        print(f"[kiwi] _get_pending_anomalies error: {e}", file=sys.stderr)
        return []


def _infer_project_path(target_file: str) -> str:
    """Infer project root from target_file path."""
    if not target_file:
        return ""
    p = Path(target_file)
    markers = {".git", "composer.json", "package.json", "wp-config.php"}
    for parent in p.parents:
        if any((parent / m).exists() for m in markers):
            return str(parent)
    return str(p.parent)


def _infer_theme_slug(target_file: str, project_path: str) -> str:
    """Extract theme slug from path like '.../themes/{slug}/...'."""
    path = target_file or project_path or ""
    if not path:
        return ""
    parts = Path(path).parts
    for i, p in enumerate(parts):
        if p == "themes" and i + 1 < len(parts):
            return parts[i + 1]
    return ""


def _get_learned_conventions(theme_slug: str, max_styles: int = 8, max_bindings: int = 10, health=None) -> dict:
    """Read style/binding patterns from reasoning.db for given theme."""
    result = {"styles": [], "bindings": []}
    if not theme_slug:
        return result
    try:
        from agent.reasoning.session_logger import _get_conn
        conn = _get_conn()
        styles = conn.execute(
            "SELECT pattern_key, value, times_seen, blessed FROM style_knowledge "
            "WHERE theme = ? ORDER BY blessed DESC, times_seen DESC LIMIT ?",
            (theme_slug, max_styles)
        ).fetchall()
        result["styles"] = [
            {"key": r[0], "value": r[1], "count": r[2], "blessed": bool(r[3])} for r in styles
        ]
        bindings = conn.execute(
            "SELECT task_type, binding, times_seen, blessed FROM binding_knowledge "
            "WHERE theme = ? ORDER BY blessed DESC, times_seen DESC LIMIT ?",
            (theme_slug, max_bindings)
        ).fetchall()
        result["bindings"] = [
            {"task_type": r[0], "binding": r[1], "count": r[2], "blessed": bool(r[3])} for r in bindings
        ]
        if health:
            if not result["styles"] and not result["bindings"]:
                health.degraded("learned_conventions",
                    f"chưa học được style/binding cho theme '{theme_slug}' — "
                    "chạy kiwi_learn_session vài lần")
            else:
                health.ok("learned_conventions")
    except ImportError as e:
        if health:
            health.unavailable("learned_conventions",
                f"thiếu module agent.reasoning.session_logger: {e}")
        print(f"[kiwi] _get_learned_conventions ImportError: {e}", file=sys.stderr)
    except Exception as e:
        if health:
            health.degraded("learned_conventions", str(e))
        print(f"[kiwi] _get_learned_conventions error: {e}", file=sys.stderr)
    return result


def _get_project_profile(project_path: str) -> dict:
    """Build or load cached project profile from DB data."""
    if project_path in _project_profile_cache:
        cached = _project_profile_cache[project_path]
        if (time.time() - cached.get("_updated", 0)) < _PROFILE_TTL:
            return cached

    profile = {"violation_categories": set(), "scan_count": 0, "_updated": time.time()}
    try:
        from memory.db import get_connection
        conn = get_connection()
        try:
            rows = conn.execute("""
                SELECT v.lesson_id, COUNT(*) as cnt
                FROM violations v
                JOIN scan_history s ON v.scan_id = s.id
                WHERE s.path LIKE ?
                GROUP BY v.lesson_id
                ORDER BY cnt DESC
            """, (f"%{project_path}%",)).fetchall()
            for r in rows:
                profile["violation_categories"].add(r["lesson_id"])
            row = conn.execute(
                "SELECT COUNT(*) FROM scan_history WHERE path LIKE ?",
                (f"%{project_path}%",)
            ).fetchone()
            profile["scan_count"] = row[0] if row else 0
        finally:
            conn.close()
    except Exception as e:
        print(f"[kiwi] _get_project_profile error: {e}", file=sys.stderr)

    _project_profile_cache[project_path] = profile
    return profile


def _is_cold_start(effective_project: str, db_scores: dict,
                   learned_conventions: dict) -> bool:
    """True when we know which project this is but have no accumulated
    project-specific signal yet (no violation history, no learned conventions).

    Distinct from `degraded` (a subsystem errored): cold-start is the NORMAL
    pre-onboarding state, fixed by running `kiwi init`, not a fault. Returns
    False when there is no project context at all (a generic task-only query is
    not "cold" — there is simply nothing to onboard).
    """
    if not effective_project:
        return False
    has_history = any(
        isinstance(v, dict) and v.get("history", 0)
        for v in (db_scores or {}).values()
    )
    lc = learned_conventions or {}
    has_conventions = bool(lc.get("styles") or lc.get("bindings"))
    return not has_history and not has_conventions


def build_context(
    task: str = "",
    scope_type: str = "plugin",
    platform: str = "wp",
    files: list = None,
    max_rules: int = 15,
    max_templates: int = 3,
    compact: bool = None,
    target_file: str = "",
    project_path: str = "",
) -> dict:
    """Build pre-code context for Claude.

    Args:
        task: What will be coded (e.g. "loyalty plugin", "checkout page")
        scope_type: "plugin" or "theme"
        platform: "wp" or "nextjs"
        files: List of file types that will be created
        max_rules: Max rules to return
        max_templates: Max templates to return
        compact: True/False to force mode, None for auto-detect (F10)
        target_file: Path to file being edited — enables smart rule filtering
        project_path: Project root for history lookup (F4)
    """
    sys.path.insert(0, str(KIWI_DIR))
    from scanner.loader import load_patterns

    health = _Health()

    # Stack filtering is EXPLICIT-ONLY: only the project_path the caller passes
    # triggers requires:/conflicts: filtering. An inferred path (from target_file)
    # is used for history/conventions but NOT for filtering — keeps behaviour
    # identical for every existing caller that omits project_path.
    filter_path = project_path or None
    patterns = load_patterns(str(KIWI_DIR / "lessons"), platform=platform, scope_type=scope_type, project_path=filter_path)
    if filter_path:
        try:
            from scanner.project_profile import detect_stack
            caps = detect_stack(filter_path)
            health.ok("project_filter") if caps else health.degraded(
                "project_filter", "không nhận diện được stack — không lọc lesson")
        except Exception:
            pass

    task_categories = _map_task_to_categories(task, patterns) if task else set()
    task_keywords = _tokenize_task(task) if task else set()

    signal_files = []
    if target_file and os.path.exists(target_file):
        signal_files.append(target_file)
    if files:
        for f in files:
            if not f or not isinstance(f, str):
                continue
            if os.path.sep in f or "/" in f or os.path.exists(f):
                if os.path.exists(f) and f not in signal_files:
                    signal_files.append(f)

    if signal_files:
        relevant_ids = {}
        for sf in signal_files:
            relevant_ids.update(_detect_signals_deep(sf, patterns))
        if not relevant_ids:
            relevant_ids = None
            health.degraded("deep_signal",
                f"đọc {len(signal_files)} file nhưng không match lesson nào — "
                "lesson có thể không cover stack hiện tại")
        else:
            health.ok("deep_signal")
    else:
        relevant_ids = None
        if task:
            health.degraded("deep_signal",
                "không có file thật — mất +30 boost khớp nội dung; "
                "truyền target_file= khi sửa code có sẵn")

    effective_project = project_path or _infer_project_path(target_file)
    db_scores = _get_db_scores(effective_project, health=health)

    semantic_scores = _get_semantic_scores(task, patterns, health=health)

    if task and not task_categories and semantic_scores:
        sem_cats = {}
        pattern_by_id = {p["id"]: p for p in patterns}
        for lid, score in semantic_scores.items():
            p = pattern_by_id.get(lid)
            if not p:
                continue
            cat = p.get("category")
            if cat:
                sem_cats[cat] = sem_cats.get(cat, 0) + score
        task_categories = {
            c for c, _ in sorted(sem_cats.items(), key=lambda x: -x[1])[:3]
        }
        if task_categories:
            health.degraded("task_mapping",
                "không khớp keyword — category suy từ semantic similarity")

    if task and not task_categories:
        health.degraded("task_mapping",
            "task khớp 0 category & 0 semantic — chỉ xếp theo severity; "
            "nên mô tả rõ hơn hoặc truyền files=/target_file=")

    contextual_rules = _get_contextual_rules(target_file, health=health)

    anomalies = _get_pending_anomalies(effective_project, health=health)

    theme_slug = _infer_theme_slug(target_file, effective_project)
    learned_conventions = _get_learned_conventions(theme_slug, health=health) if theme_slug else {"styles": [], "bindings": []}

    cold_start = _is_cold_start(effective_project, db_scores, learned_conventions)

    pre_max = min(max_rules, 8) if compact is True else max_rules
    rules = _get_rules(
        scope_type, platform, files, pre_max,
        relevant_ids=relevant_ids,
        task_categories=task_categories,
        task_keywords=task_keywords,
        db_scores=db_scores,
        semantic_scores=semantic_scores,
        project_path=filter_path,
    )

    if compact is None:
        effective_compact = len(rules) > 10
    else:
        effective_compact = compact

    if effective_compact:
        anti_patterns = []
        templates = []
        snippets = []
    else:
        relevant_set = set(relevant_ids.keys()) if relevant_ids else None
        anti_patterns = _get_anti_patterns(scope_type, platform, max_rules, relevant_set, project_path=filter_path)
        templates = _get_templates(task, max_templates)
        snippets = _get_snippets(scope_type, platform, rules)

    return {
        "rules_count": len(rules),
        "anti_patterns_count": len(anti_patterns),
        "templates_count": len(templates),
        "compact": effective_compact,
        "target_file": target_file or "",
        "signals_detected": len(relevant_ids) if relevant_ids else 0,
        "task_categories": sorted(task_categories) if task_categories else [],
        "scoring_method": "composite",
        "rules": rules,
        "anti_patterns": anti_patterns,
        "templates": templates,
        "snippets": snippets,
        "contextual_rules": contextual_rules,
        "anomalies": anomalies,
        "semantic_matches": len(semantic_scores) if semantic_scores else 0,
        "theme_slug": theme_slug,
        "learned_conventions": learned_conventions,
        "degraded": health.report(),
        "cold_start": cold_start,
    }


def format_context(ctx: dict) -> str:
    """Format context dict into a readable string for Claude."""
    if ctx.get("compact"):
        return _format_compact(ctx)
    return _format_full(ctx)


def _format_compact(ctx: dict) -> str:
    """One-line-per-severity format. ~200 tokens vs ~2000."""
    lines = [f"# Kiwi ({ctx['rules_count']} rules)"]

    if ctx.get("degraded"):
        lines.append("⚠️ **Kiwi chạy chế độ giảm** — một số tín hiệu không khả dụng:")
        for d in ctx["degraded"]:
            lines.append(f"  - {d['name']}: {d['status']} ({d.get('reason','')})")
        lines.append("")

    if ctx.get("cold_start"):
        lines.append("ℹ️ Cold start: chưa có lịch sử vi phạm / convention dự án. "
                     "Đang xếp theo category + severity + semantic. "
                     "Chạy `kiwi_init` để nạp đủ → tăng độ chính xác.")
        lines.append("")

    if ctx.get("task_categories"):
        lines.append(f"Focus: {', '.join(ctx['task_categories'])}")

    by_sev = {}
    for r in ctx["rules"]:
        by_sev.setdefault(r["severity"], []).append(f"{r['id']} {r['title']}")

    for sev in ["CRITICAL", "HIGH"]:
        items = by_sev.get(sev, [])
        if items:
            lines.append(f"{sev}: {' | '.join(items)}")

    if ctx.get("contextual_rules"):
        lines.append(f"AST-learned: {len(ctx['contextual_rules'])} context rules active")

    if ctx.get("anomalies"):
        lines.append(f"Anomalies: {len(ctx['anomalies'])} pending patterns detected")

    lc = ctx.get("learned_conventions") or {}
    if lc.get("styles") or lc.get("bindings"):
        slug = ctx.get("theme_slug", "")
        lines.append(f"Learned conventions ({slug}): {len(lc.get('styles', []))} styles, {len(lc.get('bindings', []))} bindings")

    return "\n".join(lines)


def _format_full(ctx: dict) -> str:
    """Original verbose format with code blocks."""
    lines = []

    lines.append(f"# Kiwi Pre-Code Context ({ctx['rules_count']} rules, {ctx['anti_patterns_count']} anti-patterns)")
    lines.append("")

    if ctx.get("degraded"):
        lines.append("⚠️ **Kiwi chạy chế độ giảm** — một số tín hiệu không khả dụng:")
        for d in ctx["degraded"]:
            lines.append(f"- **{d['name']}**: {d['status']} ({d.get('reason','')})")
        lines.append("")

    if ctx.get("cold_start"):
        lines.append("ℹ️ **Kiwi cold start** — chưa có lịch sử vi phạm / convention dự án.")
        lines.append("Đang xếp hạng theo: category + severity + semantic.")
        lines.append("Chạy `kiwi_init` (MCP) hoặc `python -m agent.cli <project> --init` "
                     "để nạp đủ → tăng độ chính xác.")
        lines.append("")

    if ctx.get("task_categories"):
        lines.append(f"**Focus categories:** {', '.join(ctx['task_categories'])}")
        lines.append("")

    if ctx["rules"]:
        lines.append("## MUST-FOLLOW Rules")
        for r in ctx["rules"]:
            lines.append(f"- **{r['id']}** [{r['severity']}]: {r['title']}")
            if r.get("pattern"):
                lines.append(f"  Scan: `{r['pattern']}` in `{r.get('scope', '*')}`")
        lines.append("")

    if ctx["anti_patterns"]:
        lines.append("## Anti-Patterns (DO NOT)")
        for a in ctx["anti_patterns"]:
            sev = a.get("severity", "")
            sev_tag = f"[{sev}] " if sev else ""
            lines.append(f"- **{a['id']}** {sev_tag}{a['title']}")
            if a.get("bad_example"):
                lines.append(f"  ```\n  {a['bad_example']}\n  ```")
        lines.append("")

    if ctx["snippets"]:
        lines.append("## Required Code Patterns")
        for s in ctx["snippets"]:
            lines.append(f"### {s['name']}")
            lines.append(f"```php\n{s['code']}\n```")
        lines.append("")

    if ctx["templates"]:
        lines.append("## Available Templates")
        for t in ctx["templates"]:
            lines.append(f"- **{t['id']}** [{t['section']}]: {t['title']}")
        lines.append("")

    if ctx.get("contextual_rules"):
        lines.append("## AST-Learned Context Rules")
        for cr in ctx["contextual_rules"]:
            lines.append(f"- Context: `{cr['context']}` → Ensure: `{cr['fix']}`  (confidence: {cr['confidence']:.0%})")
        lines.append("")

    if ctx.get("anomalies"):
        lines.append("## Pending Anomaly Alerts")
        for a in ctx["anomalies"]:
            lines.append(f"- [{a['severity']}] {a['category']}: `{a['pattern'][:60]}`")
        lines.append("")

    lc = ctx.get("learned_conventions") or {}
    if lc.get("styles") or lc.get("bindings"):
        slug = ctx.get("theme_slug", "")
        lines.append(f"## Theme conventions Kiwi đã học ({slug})")

        blessed_styles = [s for s in lc.get("styles", []) if s.get("blessed")]
        obs_styles = [s for s in lc.get("styles", []) if not s.get("blessed")]
        blessed_binds = [b for b in lc.get("bindings", []) if b.get("blessed")]
        obs_binds = [b for b in lc.get("bindings", []) if not b.get("blessed")]

        if blessed_binds or blessed_styles:
            lines.append("**✓ Blessed conventions (ENFORCE — dùng đúng như đã học):**")
            for b in blessed_binds:
                lines.append(f"- `{b['binding']}` ({b['task_type']}, seen {b['count']}x) ✓")
            for s in blessed_styles:
                lines.append(f"- `{s['key']}` = `{s['value']}` (seen {s['count']}x) ✓")

        if obs_styles:
            lines.append("**Style preferences (observed):**")
            for s in obs_styles:
                lines.append(f"- `{s['key']}` = `{s['value']}` (seen {s['count']}x)")
        if obs_binds:
            lines.append("**Common bindings (observed):**")
            for b in obs_binds:
                lines.append(f"- `{b['binding']}` ({b['task_type']}, seen {b['count']}x)")
        lines.append("")

    return "\n".join(lines)


def _get_rules(
    scope_type: str,
    platform: str,
    files: list,
    max_rules: int,
    relevant_ids: dict = None,
    task_categories: set = None,
    task_keywords: set = None,
    db_scores: dict = None,
    semantic_scores: dict = None,
    project_path: str = None,
) -> list:
    """Get must-follow rules ranked by composite relevance score."""
    from scanner.loader import load_patterns

    patterns = load_patterns(str(KIWI_DIR / "lessons"), platform=platform, scope_type=scope_type, project_path=project_path)

    file_extensions = set()
    if files:
        for f in files:
            ext = Path(f).suffix.lower()
            if ext:
                file_extensions.add(ext)
        if len(file_extensions) > 1:
            max_rules = min(max_rules + len(file_extensions) * 3, max_rules + 10)

    candidates = []
    for p in patterns:
        if p["severity"] not in ("CRITICAL", "HIGH"):
            continue

        if file_extensions:
            scope = p.get("scope", "**/*")
            scope_exts = set()
            for part in scope.replace("|", "\n").splitlines():
                part = part.strip()
                ext = Path(part).suffix.lower()
                if ext:
                    scope_exts.add(ext)
            if scope_exts and not (scope_exts & file_extensions):
                continue

        score = 0
        sev = p["severity"]
        score += {"CRITICAL": 40, "HIGH": 20, "SUGGEST": 5}.get(sev, 10)

        if task_categories and p["category"] in task_categories:
            score += 25

        if task_keywords and p.get("tags"):
            score += _compute_tag_score(p["tags"], task_keywords)

        if relevant_ids and p["id"] in relevant_ids:
            score += 30

        if db_scores and p["id"] in db_scores:
            score += min(db_scores[p["id"]].get("history", 0) * 3, 15)
            conf = db_scores[p["id"]].get("confidence", 1.0)
            score += int((conf - 0.5) * 20)

        if semantic_scores and p["id"] in semantic_scores:
            score += int(semantic_scores[p["id"]] * 20)

        candidates.append({
            "id": p["id"],
            "severity": sev,
            "category": p["category"],
            "title": p.get("description", ""),
            "pattern": p.get("pattern", ""),
            "scope": p.get("scope", ""),
            "_score": score,
        })

    candidates.sort(key=lambda r: (-r["_score"], r["id"]))

    for c in candidates[:max_rules]:
        del c["_score"]

    return candidates[:max_rules]


def _get_anti_patterns(scope_type: str, platform: str, max_count: int, relevant_ids: set = None, project_path: str = None) -> list:
    """Get anti-patterns with bad code examples from CRITICAL and HIGH lessons."""
    from scanner.loader import load_patterns, get_lesson_frontmatter

    patterns = load_patterns(str(KIWI_DIR / "lessons"), platform=platform, scope_type=scope_type, project_path=project_path)
    # CRITICAL + HIGH both represent "DO NOT" anti-patterns worth surfacing
    relevant = [p for p in patterns if p["severity"] in ("CRITICAL", "HIGH")]

    if relevant_ids:
        relevant = [p for p in relevant if p["id"] in relevant_ids]

    results = []
    for p in relevant:
        fm, body = get_lesson_frontmatter(p["id"], str(KIWI_DIR / "lessons"))
        if not fm or not body:
            continue

        bad_example = ""
        bad_match = re.search(r"(?:❌|SAI|Bad|## Bad).*?\n```\w*\n(.*?)```", body, re.DOTALL | re.IGNORECASE)
        if bad_match:
            bad_example = bad_match.group(1).strip()[:200]

        results.append({
            "id": p["id"],
            "severity": p["severity"],
            "title": p.get("description", ""),
            "bad_example": bad_example,
        })

    # CRITICAL before HIGH so the cap never drops a CRITICAL in favor of a HIGH
    _sev_order = {"CRITICAL": 0, "HIGH": 1}
    results.sort(key=lambda r: (_sev_order.get(r["severity"], 2), r["id"]))
    return results[:max_count]


def _get_templates(task: str, max_count: int) -> list:
    """Get relevant templates based on task keywords."""
    if not task:
        return []

    try:
        sys.path.insert(0, str(KIWI_DIR / "templates" / "tools"))
        from query import load_all_templates, filter_templates

        templates = load_all_templates()
        filtered = filter_templates(templates, keyword=task)

        if not filtered:
            for word in task.lower().split():
                if len(word) > 3:
                    filtered = filter_templates(templates, keyword=word)
                    if filtered:
                        break

        results = []
        for t in filtered[:max_count]:
            results.append({
                "id": t.get("id", "?"),
                "section": t.get("section", ""),
                "title": t.get("title", ""),
                "theme_source": t.get("theme_source", ""),
            })
        return results
    except Exception as e:
        print(f"WARNING: Template query failed: {e}", file=sys.stderr)
        return []


def _get_snippets(scope_type: str, platform: str, matched_rules: list = None) -> list:
    """Get required code snippets based on scope type + dynamic from matched rules."""
    snippets = []

    if platform == "wp" and scope_type == "plugin":
        snippets.append({
            "name": "Plugin boot() entry point",
            "code": (
                "public function boot(): void {\n"
                "    if ( function_exists( 'wz_config' ) ) {\n"
                "        wz_config( 'plugin-name' );\n"
                "    }\n"
                "    if ( function_exists( 'wezone_is_active' ) && ! wezone_is_active( 'feature' ) ) {\n"
                "        return;\n"
                "    }\n"
                "    // register hooks, filters, etc.\n"
                "}"
            ),
        })
        snippets.append({
            "name": "Bulk insert (NOT N+1 loop)",
            "code": (
                "// CORRECT — single query\n"
                "wz_bulk_insert( $table, $rows, array( '%d', '%s', '%f' ) );\n\n"
                "// WRONG — N queries in loop\n"
                "// foreach ( $rows as $row ) { $wpdb->insert( $table, $row ); }"
            ),
        })
        snippets.append({
            "name": "AJAX with nonce",
            "code": (
                "$.ajax({\n"
                "    url: wezone_ajax.rest_url + 'wezone/v1/endpoint',\n"
                "    method: 'POST',\n"
                "    headers: { 'X-WP-Nonce': wezone_ajax.nonce },\n"
                "    data: payload,\n"
                "});"
            ),
        })

    elif platform == "wp" and scope_type == "theme":
        snippets.append({
            "name": "Template with wz_component()",
            "code": (
                "<?php\n"
                "// CORRECT — use wz_component\n"
                "wz_component( 'product-card', $product );\n\n"
                "// WRONG — raw HTML\n"
                "// echo '<div class=\"product\">' . $product['name'] . '</div>';"
            ),
        })
        snippets.append({
            "name": "CSS mobile-first",
            "code": (
                "/* CORRECT — mobile-first with min-width */\n"
                ".hero { padding: 1rem; }\n"
                "@media (min-width: 768px) { .hero { padding: 2rem; } }\n\n"
                "/* WRONG — desktop-first with max-width */\n"
                "/* @media (max-width: 767px) { .hero { padding: 1rem; } } */"
            ),
        })

    if matched_rules:
        from scanner.loader import get_lesson_frontmatter
        added = 0
        for r in matched_rules[:5]:
            if added >= 3:
                break
            fm, body = get_lesson_frontmatter(r["id"], str(KIWI_DIR / "lessons"))
            if not body:
                continue
            good_match = re.search(
                r"(?:✅|ĐÚNG|Good|## Good|# Good Code|Correct|## Fix|# Fix).*?\n```\w*\n(.*?)```",
                body, re.DOTALL | re.IGNORECASE
            )
            if good_match:
                code = good_match.group(1).strip()[:300]
                snippets.append({
                    "name": f"{r['id']}: {r.get('title', '')[:50]}",
                    "code": code,
                })
                added += 1

    return snippets