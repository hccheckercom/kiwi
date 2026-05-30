"""Kiwi MCP Server — Bug pattern scanner + knowledge base as MCP tools."""

import json
import os
import re
import sys
from pathlib import Path

KIWI_DIR = Path(__file__).parent
LESSONS_DIR = KIWI_DIR / "lessons"
META_PATH = KIWI_DIR / "_meta.json"

# Lazy-loaded modules
_scanner_loaded = False


def _ensure_scanner():
    global _scanner_loaded
    if _scanner_loaded:
        return
    sys.path.insert(0, str(KIWI_DIR))
    _scanner_loaded = True


def _resolve_path(path_or_name: str) -> str:
    if os.path.isdir(path_or_name):
        return os.path.abspath(path_or_name)
    try:
        meta = json.loads(META_PATH.read_text(encoding="utf-8"))
        resolved = meta.get("projects", {}).get(path_or_name)
        if resolved and os.path.isdir(resolved):
            return resolved
    except (json.JSONDecodeError, OSError):
        pass
    return path_or_name


def _load_lesson_file(lesson_id: str) -> tuple:
    _ensure_scanner()
    from scanner.loader import get_lesson_frontmatter
    return get_lesson_frontmatter(lesson_id, str(LESSONS_DIR))


# --- Tool handlers ---

def _handle_scan(args: dict) -> str:
    """
    Scan project/theme for bug patterns.

    Args:
        path: Project path or name (e.g., 'wezone-plugins', 'themes/sfvn')
        severity: Filter by severity (CRITICAL, HIGH, SUGGEST, ALL)
        platform: Filter by platform (wp, nextjs)
        scope: Force scope type (theme, plugin)
        diff_only: Only scan git-modified files
        max_per_lesson: Cap violations per lesson (default: 5)

    Returns:
        Formatted scan report with violations grouped by severity

    Example:
        kiwi_scan(path="wezone-plugins", severity="CRITICAL")
    """
    _ensure_scanner()
    from scanner.cli import scan_theme, scan_monorepo, _detect_project_type, _discover_themes_in_folder, _find_theme_root

    path = _resolve_path(args["path"])
    if not os.path.isdir(path):
        return f"ERROR: Directory not found: {path}"

    severity = args.get("severity", "ALL")
    platform = args.get("platform")
    scope = args.get("scope")
    diff_only = args.get("diff_only", False)
    max_per = int(args.get("max_per_lesson", 5))

    project_type = _detect_project_type(path)
    if project_type not in ("monorepo", "themes_folder"):
        path = _find_theme_root(path)

    if project_type == "monorepo" and not scope:
        report = scan_monorepo(path, severity_filter=severity, diff_only=diff_only, platform=platform)
    elif project_type == "themes_folder" and not scope:
        from scanner.models import Report
        themes = _discover_themes_in_folder(path)
        merged = Report(theme_path=path)
        sub_reports = []
        for sub_path, scope_type, label in themes:
            sub = scan_theme(sub_path, severity_filter=severity, diff_only=diff_only,
                             platform=platform, scope_type=scope_type,
                             skip_root_patterns=True, rewrite_scopes=True)
            for v in sub.violations:
                v.file = f"{label}/{v.file}" if not v.file.startswith("[") else f"[{label}] {v.file}"
            merged.patterns_checked = max(merged.patterns_checked, sub.patterns_checked)
            merged.files_scanned += sub.files_scanned
            merged.violations.extend(sub.violations)
            sub_reports.append((label, scope_type, sub))
        merged._sub_reports = sub_reports
        report = merged
    else:
        effective_scope = scope or (project_type if project_type in ("theme", "plugin") else None)
        should_skip_empty = project_type in ("unknown", "plugin")
        report = scan_theme(path, severity_filter=severity, diff_only=diff_only,
                            platform=platform, scope_type=effective_scope,
                            skip_empty_scope=should_skip_empty,
                            rewrite_scopes=(project_type == "theme"))

    if max_per > 0:
        report = report.cap_per_lesson(max_per)

    grouped = report.grouped()
    lines = [f"Kiwi Scan: {path}",
             f"Patterns: {report.patterns_checked} | Files: {report.files_scanned}",
             f"Summary: {report.critical_count} CRITICAL | {report.high_count} HIGH | {report.suggest_count} SUGGEST",
             ""]

    for sev in ["CRITICAL", "HIGH", "SUGGEST"]:
        sev_lessons = {lid: vs for lid, vs in grouped.items() if vs[0].severity == sev}
        if not sev_lessons:
            continue
        lines.append(f"{sev} ({sum(len(v) for v in sev_lessons.values())}):")
        for lid, vs in sorted(sev_lessons.items()):
            lines.append(f"  {lid} [{vs[0].category}] {vs[0].description} ({len(vs)} hits)")
            for v in vs[:3]:
                lines.append(f"    → {v.file}:{v.line}  {v.match_text[:80]}")
            if len(vs) > 3:
                lines.append(f"    ... +{len(vs)-3} more")
        lines.append("")

    if not report.violations:
        lines.append("No violations found.")

    return "\n".join(lines)


def _handle_query(args: dict) -> str:
    """
    Search Kiwi knowledge base by keyword, category, or severity.

    Args:
        keyword: Search term (e.g., 'IDOR', 'XSS', 'mobile-first')
        category: Filter by category
        severity: Filter by severity (CRITICAL, HIGH, SUGGEST, INFO)
        platform: Filter by platform (wp, nextjs)
        limit: Max results to return (default: 10)

    Returns:
        List of matching lessons with ID, title, category, severity

    Example:
        kiwi_query(keyword="nonce csrf", severity="CRITICAL")
    """
    _ensure_scanner()
    from scanner.loader import load_patterns

    keyword = args.get("keyword", "").lower()
    category = args.get("category")
    severity = args.get("severity")
    platform = args.get("platform")
    limit = int(args.get("limit", 10))

    patterns = load_patterns(str(LESSONS_DIR), platform=platform)
    results = []
    for p in patterns:
        if category and p.get("category") != category:
            continue
        if severity and p.get("severity") != severity:
            continue
        if keyword:
            searchable = f"{p.get('title','')} {p.get('pattern','')} {p.get('category','')}".lower()
            if keyword not in searchable:
                fm, body = _load_lesson_file(p["id"])
                if body and keyword in body.lower():
                    pass
                else:
                    continue
        results.append(p)

    results = results[:limit]
    if not results:
        return "No matching lessons found."

    lines = [f"Kiwi Query: {len(results)} results\n"]
    for i, p in enumerate(results, 1):
        lines.append(f"{i}. {p['id']} [{p['severity']}] [{p['category']}]")
        lines.append(f"   {p.get('title', '')}")
        lines.append(f"   Pattern: {p.get('pattern', '')}")
        lines.append(f"   Scope: {p.get('scope', '')}")
        lines.append("")
    return "\n".join(lines)


def _handle_lesson(args: dict) -> str:
    """
    Read full lesson: Bad/Good/Why/Grep pattern.

    Args:
        id: Lesson ID (e.g., 'LES-016', 'FEA-025')

    Returns:
        Complete lesson content with bad example, good example, explanation, and grep pattern

    Example:
        kiwi_lesson(id="LES-020")
    """
    lesson_id = args["id"]
    fm, body = _load_lesson_file(lesson_id)
    if fm is None:
        return f"Lesson {lesson_id} not found."

    lines = [f"# {lesson_id} [{fm.get('severity','')}] [{fm.get('category','')}]",
             f"**{fm.get('title', '')}**", ""]
    scan = fm.get("scan", {})
    if scan:
        lines.append(f"Type: {scan.get('type','')} | Pattern: `{scan.get('pattern','')}`")
        lines.append(f"Scope: `{scan.get('scope','')}`")
        if scan.get("exclude"):
            lines.append(f"Exclude: `{scan['exclude']}`")
        if scan.get("cross_check"):
            lines.append(f"Cross-check: `{scan['cross_check']}`")
        lines.append("")
    lines.append(body)
    return "\n".join(lines)


def _handle_stats(args: dict) -> str:
    """
    View Kiwi knowledge base statistics.

    Returns:
        Summary of lessons by severity, category, and check type

    Example:
        kiwi_stats()
    """
    _ensure_scanner()
    from scanner.loader import load_patterns

    patterns = load_patterns(str(LESSONS_DIR))

    sev = {}
    cats = {}
    types = {}
    for p in patterns:
        s = p["severity"]
        sev[s] = sev.get(s, 0) + 1
        c = p["category"]
        cats[c] = cats.get(c, 0) + 1
        t = p["type"]
        types[t] = types.get(t, 0) + 1

    lines = [f"Kiwi Knowledge Base — {len(patterns)} patterns", ""]
    lines.append("Severity:")
    for s in ["CRITICAL", "HIGH", "SUGGEST", "INFO"]:
        if s in sev:
            lines.append(f"  {s:10s} {sev[s]:3d}")
    lines.append("\nCategory:")
    for c, count in sorted(cats.items(), key=lambda x: -x[1]):
        lines.append(f"  {c:20s} {count:3d}")
    lines.append("\nCheck Type:")
    for t, count in sorted(types.items(), key=lambda x: -x[1]):
        lines.append(f"  {t:15s} {count:3d}")
    return "\n".join(lines)


def _handle_learning_health(args: dict) -> str:
    """Health snapshot of Kiwi active-learning system.

    Returns sessions logged, bindings/styles/patterns learned, suggestions pending,
    fail counters, themes touched, top bindings — read-only.

    Status values:
      healthy   — sessions logged in last 7d, fail_counts low
      degraded  — fail_counts > 50 (something keeps breaking)
      stalled   — no sessions in last 7d (or DB empty)
      disabled  — KIWI_LEARNING_DISABLED=1 or .learning_disabled flag file present

    Example:
        kiwi_learning_health()
    """
    try:
        sys.path.insert(0, str(KIWI_DIR))
        from tools.learning_health import get_health
        return json.dumps(get_health(), indent=2, ensure_ascii=False)
    except Exception as e:
        return json.dumps({"status": "error", "error": f"{type(e).__name__}: {e}"})


def _handle_fix(args: dict) -> str:
    """
    Fix suggestion or auto-fix violation.

    Without file: returns Good example code.
    With file: previews diff.
    With file + apply=true: applies fix.

    Args:
        lesson_id: Lesson ID (e.g., 'LES-020')
        file: Path to file containing violation (optional)
        line: Line number of violation (optional)
        apply: true = apply fix, false = preview only (default: false)

    Returns:
        Good example code, diff preview, or fix confirmation

    Example:
        kiwi_fix(lesson_id="LES-020", file="src/Plugin.php", line=42, apply=true)
    """
    _ensure_scanner()
    from scanner.cli import get_fix_for_lesson

    lesson_id = args["lesson_id"]
    file_path = args.get("file")
    line = int(args.get("line", 0))
    apply = args.get("apply", False)

    fm, body = _load_lesson_file(lesson_id)
    if fm is None:
        return f"Lesson {lesson_id} not found."

    fix_config = fm.get("fix")

    if fix_config and file_path:
        from scanner.fixer import apply_fix
        from scanner.models import Violation

        violation = Violation(
            lesson_id=lesson_id,
            severity=fm.get("severity", "HIGH"),
            category=fm.get("category", ""),
            description=fm.get("title", ""),
            file=file_path,
            line=line,
        )
        result = apply_fix(violation, fix_config, dry_run=not apply)

        # Close the contextual-learning loop: a successfully APPLIED fix is a
        # confirmed before→after, so feed it to the AST learner. This is the
        # only producer of `contextual_lessons`; without it that table stays
        # empty and kiwi_context reports "contextual_rules: degraded" forever.
        if apply and result.success and file_path:
            try:
                from learning.context_learner import (
                    learn_from_fix_context,
                    save_contextual_lesson,
                )
                lesson = learn_from_fix_context(file_path, line, result.diff or "")
                if lesson and lesson.confidence >= 0.7:
                    save_contextual_lesson(lesson)
            except Exception:
                pass  # Learning is best-effort; never block a fix on it.

        if result.success:
            action = "Applied" if apply else "Preview"
            lines = [f"{action} fix for {lesson_id} ({result.fix_type}):"]
            lines.append(f"```diff\n{result.diff}```")
            return "\n".join(lines)
        elif result.error:
            lines = [f"Auto-fix failed: {result.error}"]
            _ensure_memory()
            from memory.db import get_learned_fix
            learned = get_learned_fix(lesson_id)
            if learned and learned["applied_count"] >= 2:
                lines.append(f"\nLearned fix ({learned['applied_count']}x verified):\n```diff\n{learned['diff_preview']}\n```")
            good = get_fix_for_lesson(lesson_id, str(LESSONS_DIR))
            if good:
                lines.append(f"\nFallback — Good example:\n```\n{good}\n```")
            return "\n".join(lines)

    lines = [f"Fix suggestion for {lesson_id}: {fm.get('title','')}"]

    if fix_config:
        lines.append(f"\nAuto-fix available (type: {fix_config.get('type','')})")
        if fix_config.get("type") == "llm":
            lines.append(f"LLM prompt: {fix_config.get('prompt','')}")
        else:
            lines.append("Pass file + line + apply=true to apply.")

    good = get_fix_for_lesson(lesson_id, str(LESSONS_DIR))
    if good:
        lines.append(f"\nGood example:\n```\n{good}\n```")

    why_match = re.search(r"## Why\s*\n(.*?)(?=\n## |\Z)", body or "", re.DOTALL)
    if why_match:
        lines.append(f"\nWhy: {why_match.group(1).strip()}")

    return "\n".join(lines)


def _handle_add(args: dict) -> str:
    """
    Add new lesson to Kiwi knowledge base.

    Creates lesson file, updates _meta.json, rebuilds README.

    Args:
        category: Lesson category
        severity: CRITICAL, HIGH, or SUGGEST
        title: Lesson title
        pattern: Grep pattern to detect violation
        bad_code: Bad example code
        good_code: Good example code
        why: Explanation of why this is a problem
        scope: File scope pattern (default: **/*.php)
        scan_type: presence, absence, cross-check, or bom-check
        platform: wp, nextjs, or both
        tags: List of tags (default: ['theme'])

    Returns:
        Confirmation with new lesson ID

    Example:
        kiwi_add(category="php-security", severity="CRITICAL", title="SQL Injection", pattern="\\$wpdb->query\\(.*\\$")
    """
    sys.path.insert(0, str(KIWI_DIR / "tools"))
    from add import add_lesson, _auto_rebuild

    try:
        lesson_id, filepath = add_lesson(
            category=args["category"],
            severity=args["severity"],
            title=args["title"],
            scan_type=args.get("scan_type", "presence"),
            pattern=args.get("pattern", ""),
            scope=args.get("scope", "**/*.php"),
            tags=",".join(args.get("tags", ["theme"])),
            bad_code=args.get("bad_code", ""),
            good_code=args.get("good_code", ""),
            why=args.get("why", ""),
            source=args.get("source", ""),
        )
        _auto_rebuild()
        return f"Created: {lesson_id} → {filepath}"
    except Exception as e:
        return f"Error adding lesson: {e}"


def _handle_agent(args: dict) -> str:
    """
    Run Kiwi Agent: autonomous scan → analyze → fix → verify loop.

    Args:
        path: Project path or name
        mode: review (read-only report), interactive (ask before fix), auto (fix all + verify)
        severity: Filter by severity (CRITICAL, HIGH, ALL)
        max_fixes: Max fixes to apply (default: 10)

    Returns:
        Agent execution report with fixes applied and verification results

    Example:
        kiwi_agent(path="wezone-plugins", mode="auto", severity="CRITICAL", max_fixes=5)
    """
    _ensure_scanner()
    from agent.loop import run_agent

    path = _resolve_path(args["path"])
    mode = args.get("mode", "review")
    severity = args.get("severity", "CRITICAL")
    max_fixes = int(args.get("max_fixes", 10))

    try:
        report = run_agent(
            path=path, mode=mode, severity=severity,
            max_fixes=max_fixes, verbose=False,
        )
    except Exception as e:
        return f"Agent error: {e}"

    lines = [
        f"Kiwi Agent Report ({mode})",
        f"Path: {report['path']}",
        f"Scans: {report['scans']} | Duration: {report['elapsed_seconds']}s",
        f"Violations: {report['violations_found']} found → {report['fixes_applied']} fixed, {report['violations_remaining']} remaining",
        "",
    ]

    if report.get("history"):
        lines.append("History:")
        for h in report["history"]:
            detail = f" — {h['detail']}" if h.get("detail") else ""
            lines.append(f"  [{h['action']}]{detail}")
        lines.append("")

    if report.get("final_message"):
        lines.append(report["final_message"])

    return "\n".join(lines)


def _handle_template(args: dict) -> str:
    sys.path.insert(0, str(KIWI_DIR / "templates" / "tools"))
    from query import load_all_templates, filter_templates

    templates = load_all_templates()
    filtered = filter_templates(
        templates,
        section=args.get("section"),
        tag=args.get("tag"),
        keyword=args.get("keyword"),
    )

    if not filtered:
        return "No matching templates found."

    detail = args.get("detail", False)
    lines = [f"Kiwi Templates: {len(filtered)} results\n"]
    for t in filtered:
        tid = t.get("id", "?")
        lines.append(f"  {tid} [{t.get('section','')}] {t.get('title','')}")
        lines.append(f"    Source: {t.get('theme_source','')} | Style: {t.get('design_style','')}")
        if detail:
            tpath = t.get("_path")
            if tpath and os.path.isfile(tpath):
                lines.append(f"\n{Path(tpath).read_text(encoding='utf-8')}")
    return "\n".join(lines)


def _ensure_memory():
    """Initialize memory DB on first use."""
    sys.path.insert(0, str(KIWI_DIR))
    from memory.db import init_db
    init_db()


def _handle_dismiss(args: dict) -> str:
    """
    Mark violation as false positive.

    Dismissed violations won't appear in future scans.

    Args:
        lesson_id: Lesson ID
        file: File path containing violation
        reason: Why this is a false positive
        scope: file (this file only), project, or global (default: file)

    Returns:
        Confirmation with updated confidence score

    Example:
        kiwi_dismiss(lesson_id="LES-020", file="src/Plugin.php", reason="intentional for legacy compat", scope="file")
    """
    _ensure_memory()
    from memory.db import dismiss_violation, get_dismissed_list
    from memory.confidence import update_hit, recalculate_confidence

    lesson_id = args["lesson_id"]
    file = args["file"]
    reason = args["reason"]
    scope = args.get("scope", "file")

    dismiss_violation(lesson_id, file, reason=reason, scope=scope)
    update_hit(lesson_id, is_true_positive=False)
    conf = recalculate_confidence(lesson_id)

    return f"Dismissed {lesson_id} in {file} (scope={scope}). Confidence: {conf:.2f}"


def _handle_deploy_history(args: dict) -> str:
    """
    Query deployment history with filtering.

    Track timestamp, user, target, success/failure, rollback events.

    Args:
        path: Filter by project path (optional)
        target: Filter by environment - staging or production (optional)
        limit: Max deployments to return (default: 50)

    Returns:
        Deployment history with scan results, health checks, and error details

    Example:
        kiwi_deploy_history(path="themes/sfvn", target="production", limit=10)
    """
    _ensure_memory()
    from memory.db import get_deployment_history

    path = args.get("path")
    if path:
        path = _resolve_path(path)
    target = args.get("target")
    limit = int(args.get("limit", 50))

    deployments = get_deployment_history(path=path, target=target, limit=limit)

    if not deployments:
        return "No deployment history found."

    lines = [f"Deployment History (last {len(deployments)} deployments)", ""]

    for d in deployments:
        status = "SUCCESS" if d["success"] else "FAILED"
        if d["rollback"]:
            status = "ROLLBACK"

        lines.append(f"[{d['timestamp']}] {status}")
        lines.append(f"  Path: {d['path']}")
        lines.append(f"  Type: {d['deploy_type']} -> {d['target']}")
        if d["user"]:
            lines.append(f"  User: {d['user']}")
        lines.append(f"  Scan: {'PASS' if d['scan_passed'] else 'FAIL'} "
                    f"({d['violations_critical']} CRITICAL, {d['violations_high']} HIGH)")
        lines.append(f"  Health: {'PASS' if d['health_check_passed'] else 'FAIL'}")
        if d["error_message"]:
            lines.append(f"  Error: {d['error_message']}")
        lines.append(f"  Duration: {d['duration_ms']}ms")
        lines.append("")

    return "\n".join(lines)


def _handle_reenable(args: dict) -> str:
    """Re-enable a disabled lesson."""
    _ensure_memory()
    from memory.db import get_connection

    lesson_id = args["lesson_id"]

    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE lesson_confidence
            SET disabled = 0,
                disabled_reason = NULL,
                disabled_at = NULL
            WHERE lesson_id = ?
        """, (lesson_id,))
        conn.commit()

        if cursor.rowcount == 0:
            return f"⚠ Lesson {lesson_id} not found in confidence table"

        return f"✓ Re-enabled {lesson_id}"
    finally:
        conn.close()


def _handle_detect_anomalies(args: dict) -> str:
    """Detect anomalies in recent violations and suggest new patterns."""
    _ensure_memory()
    from learning.loop import detect_and_suggest_anomalies

    lookback_days = int(args.get("lookback_days", 7))

    try:
        suggestion_ids = detect_and_suggest_anomalies(lookback_days=lookback_days)

        if not suggestion_ids:
            return f"No anomalies detected in last {lookback_days} days."

        lines = [
            f"Anomaly Detection: Last {lookback_days} days",
            f"Detected {len(suggestion_ids)} novel patterns",
            "",
            "Suggested lessons created (pending review):",
        ]

        # Get suggestion details
        from memory.db import get_connection
        conn = get_connection()
        try:
            cursor = conn.cursor()

            for sid in suggestion_ids[:10]:  # Show first 10
                cursor.execute("""
                    SELECT pattern, category, severity, example_file
                    FROM suggested_lessons
                    WHERE id = ?
                """, (sid,))
                row = cursor.fetchone()
                if row:
                    pattern, category, severity, example = row
                    lines.append(f"  [{severity}] {category}: {pattern[:60]}")
                    lines.append(f"    Example: {example}")

            if len(suggestion_ids) > 10:
                lines.append(f"  ... +{len(suggestion_ids) - 10} more")
        finally:
            conn.close()

        lines.append("")
        lines.append("Review with: kiwi_review_suggestions()")

        return "\n".join(lines)

    except Exception as e:
        return f"ERROR: Anomaly detection failed: {e}"


def _handle_trends(args: dict) -> str:
    """
    View violation trends over time and detect regressions.

    Args:
        path: Project path or name
        days: Lookback period in days (default: 30)

    Returns:
        Violation trend analysis and regression detection between last 2 scans

    Example:
        kiwi_trends(path="wezone-plugins", days=30)
    """
    _ensure_memory()
    from memory.trends import violation_trend, regression_check, project_summary

    path = _resolve_path(args["path"])
    days = int(args.get("days", 30))

    summary = project_summary(path)
    trend = violation_trend(path, days)
    regressions = regression_check(path)

    lines = [f"Kiwi Trends: {path}", f"Total scans: {summary['total_scans']} | Fixes: {summary['total_fixes']} | Dismissed: {summary['total_dismissed']}", ""]

    if summary.get("last_scan"):
        ls = summary["last_scan"]
        lines.append(f"Last scan: {ls['date']}")
        lines.append(f"  CRITICAL: {ls['critical']} | HIGH: {ls['high']} | Total: {ls['total']}")
        lines.append("")

    if regressions:
        lines.append("⚠ REGRESSIONS DETECTED:")
        for r in regressions:
            lines.append(f"  {r['message']}")
        lines.append("")

    if trend:
        lines.append(f"Daily trend (last {days} days):")
        for t in trend:
            lines.append(f"  {t['date']}: {t['critical']} CRIT | {t['high']} HIGH | {t['total']} total ({t['scans']} scans)")
    elif summary['total_scans'] == 0:
        lines.append("No scan history yet. Run kiwi_scan or kiwi_agent first.")

    return "\n".join(lines)


def _handle_confidence(args: dict) -> str:
    """
    View confidence scores for lessons.

    Lessons with high false positive rates are auto-demoted in severity.

    Args:
        lesson_id: Specific lesson ID (optional, shows overview if omitted)
        min_fps: Min false positives to display (default: 3, only used without lesson_id)

    Returns:
        Confidence scores, FP rates, and auto-disable status

    Example:
        kiwi_confidence(lesson_id="LES-020")
    """
    _ensure_memory()
    from memory.confidence import get_confidence, get_noisy_lessons, get_all_confidence

    lesson_id = args.get("lesson_id")

    if lesson_id:
        data = get_confidence(lesson_id)
        lines = [
            f"Confidence: {lesson_id}",
            f"  Score: {data.get('confidence', 1.0):.3f}",
            f"  Hits: {data.get('total_hits', 0)} (TP: {data.get('true_positive_count', 0)}, FP: {data.get('false_positive_count', 0)})",
            f"  Fixes: {data.get('fix_success_count', 0)} success, {data.get('fix_failure_count', 0)} failed",
            f"  Effective severity: {data.get('effective_severity', 'N/A')}",
        ]
        return "\n".join(lines)

    min_fps = int(args.get("min_fps", 3))
    noisy = get_noisy_lessons(min_fps)

    if not noisy:
        all_conf = get_all_confidence()
        if not all_conf:
            return "No confidence data yet. Violations are tracked automatically during scans."
        lines = [f"Lesson Confidence Overview ({len(all_conf)} tracked):", ""]
        for c in all_conf[:20]:
            lines.append(f"  {c['lesson_id']:10s} conf={c['confidence']:.2f} hits={c['total_hits']} TP={c['true_positive_count']} FP={c['false_positive_count']} fix={c['fix_success_count']}/{c['fix_success_count']+c['fix_failure_count']}")
        return "\n".join(lines)

    lines = [f"Noisy Lessons (≥{min_fps} false positives):", ""]
    for c in noisy:
        lines.append(f"  {c['lesson_id']:10s} conf={c['confidence']:.2f} hits={c['total_hits']} FP={c['false_positive_count']} eff_sev={c.get('effective_severity', '?')}")
    return "\n".join(lines)


def _handle_context(args: dict) -> str:
    """
    Inject Kiwi knowledge before coding: rules, anti-patterns, code snippets.

    MANDATORY before Write/Edit on .php/.css/.js/.ts/.tsx/.jsx files.
    Helps code correctly from the start, reduces bugs.

    Args:
        task: Task description (e.g., 'loyalty plugin', 'checkout page')
        scope_type: plugin or theme (default: plugin)
        platform: wp or nextjs (default: wp)
        files: File types to create (e.g., ['Plugin.php', 'admin.js'])
        target_file: Path to file being edited (enables smart filtering)
        compact: true = minimal output (id+title only), saves ~70% tokens

    Returns:
        Relevant rules, anti-patterns, and code snippets for the task

    Example:
        kiwi_context(task="checkout page", scope_type="theme", compact=true)
    """
    _ensure_scanner()
    from agent.context import build_context, format_context

    ctx = build_context(
        task=args.get("task", ""),
        scope_type=args.get("scope_type", "plugin"),
        platform=args.get("platform", "wp"),
        files=args.get("files"),
        compact=args.get("compact", False),
        target_file=args.get("target_file", ""),
    )
    return format_context(ctx)


def _handle_check(args: dict) -> str:
    """
    Instant single/multi-file scan after edit. 0 API token.

    Returns PASS/BLOCK + violations. Use after Write/Edit or to verify fix.

    Args:
        file: Single file path
        files: Multiple file paths (batch verify)
        severity: Filter by severity (CRITICAL, HIGH, ALL)
        platform: Filter by platform (wp, nextjs)
        compact: true = hide clean files (default: true)

    Returns:
        PASS or BLOCK with violation details

    Example:
        kiwi_check(file="src/Plugin.php", severity="CRITICAL")
    """
    _ensure_scanner()
    from agent.guardrail import check_file, format_result

    file_arg = args.get("file", "")
    files_arg = args.get("files", [])

    if files_arg:
        all_files = files_arg
    elif file_arg:
        all_files = [file_arg]
    else:
        return "ERROR: Provide 'file' or 'files' parameter."

    platform = args.get("platform")
    severity = args.get("severity", "CRITICAL")
    compact = args.get("compact", True)

    results = []
    total_c = 0
    total_h = 0
    for fp in all_files:
        result = check_file(file_path=fp, platform=platform, severity=severity)
        total_c += result.get("critical", 0)
        total_h += result.get("high", 0)
        formatted = format_result(result)
        if formatted:
            results.append(formatted)
        elif not compact:
            results.append(f"PASS: {fp}")

    if not results:
        return f"PASS: {len(all_files)} file(s) clean — 0 violations"

    summary = f"Checked {len(all_files)} file(s): {total_c} CRITICAL, {total_h} HIGH"
    return summary + "\n" + "\n".join(results)


def _handle_deploy(args: dict) -> str:
    """Handle kiwi_deploy tool — token-optimized deployment with Slack notifications."""
    import time
    sys.path.insert(0, str(KIWI_DIR))

    # Import notifications
    try:
        from deploy.notifications import (
            NotificationConfig,
            notify_deployment_start,
            notify_deployment_success,
            notify_deployment_failure,
            notify_scan_blocked,
        )
        notifications_enabled = True
    except ImportError:
        notifications_enabled = False
    from deploy.executor import DeployExecutor
    from deploy.state import get_cache, should_rescan, log_deploy
    from memory.db import log_deployment

    path = _resolve_path(args["path"])
    deploy_type = args["type"]
    target = args.get("target", "staging")
    mode = args.get("mode", "verify")
    skip_scan = args.get("skip_scan", False)
    rollback_on_fail = args.get("rollback_on_fail", True)
    remote_path = args.get("remote_path")

    executor = DeployExecutor(path, deploy_type, target)
    if remote_path:
        executor.remote_path = remote_path

    # Initialize notification config
    notif_config = NotificationConfig() if notifications_enabled else None
    project_name = Path(path).name

    # Step 1: Check git status
    git_commit = executor.get_git_commit()
    git_clean = executor.check_git_clean()
    if not git_clean and mode == "execute":
        return "ERROR: Uncommitted changes detected. Commit or stash before deploying."

    lines = [f"Deploy: {path} ({deploy_type} → {target})"]
    lines.append(f"Git commit: {git_commit[:7]}")

    # Step 2: Check cache — skip scan if code unchanged
    if deploy_type == "demo_html":
        lines.append("Skipping Kiwi scan (demo_html type — no code to scan)")
    else:
        cache = get_cache(path)
        if skip_scan and cache and cache["last_git_commit"] == git_commit:
            scan_result = cache.get("last_scan_result", {})
            lines.append(f"Using cached scan result (commit {git_commit[:7]})")
        else:
            # Run Kiwi scan
            if should_rescan(path, git_commit):
                scan_result = executor.run_kiwi_scan(severity="CRITICAL")
                lines.append(f"Kiwi scan: {scan_result.get('critical', 0)} CRITICAL, {scan_result.get('high', 0)} HIGH")
                if scan_result.get("critical", 0) > 0 and mode == "execute":
                    # Notify scan blocked
                    if notif_config:
                        notify_scan_blocked(
                            notif_config,
                            project_name,
                            scan_result.get('total', 0),
                            scan_result.get('critical', 0),
                        )
                    return "\n".join(lines) + f"\n\nBLOCKED: {scan_result['critical']} CRITICAL violations. Fix before deploying."
            else:
                lines.append(f"Code unchanged since last deploy — skipping scan")

    # Step 3: Build deploy plan
    plan = executor.build_plan()
    if "error" in plan:
        return "\n".join(lines) + f"\n\nERROR: {plan['error']}"

    lines.append(f"\nDeploy plan ({mode}):")
    for step in plan["steps"]:
        cmd_preview = step["command"][:80] + ("..." if len(step["command"]) > 80 else "")
        lines.append(f"  {step['name']}: {cmd_preview}")

    if mode == "dry-run":
        return "\n".join(lines)

    # Step 4: Execute deploy
    if mode == "execute":
        # Notify deployment start
        if notif_config:
            notify_deployment_start(notif_config, project_name, deploy_type, target, git_commit)

        lines.append("\nExecuting deployment...")
        start_time = time.time()
        result = executor.execute(plan)
        duration_ms = int((time.time() - start_time) * 1000)

        if result["success"]:
            log_deploy(path, deploy_type, target, git_commit, True, duration_ms)

            # Log to deployment history database
            scan_result = locals().get('scan_result', {})
            health = result.get("health_status", {})
            log_deployment(
                path=path,
                deploy_type=deploy_type,
                target=target,
                user=None,  # TODO: Get from auth context
                success=True,
                rollback=False,
                scan_passed=scan_result.get('critical', 0) == 0,
                violations_critical=scan_result.get('critical', 0),
                violations_high=scan_result.get('high', 0),
                health_check_passed=health.get('healthy', True),
                error_message=None,
                duration_ms=duration_ms
            )

            # Notify deployment success
            if notif_config:
                notify_deployment_success(
                    notif_config,
                    project_name,
                    deploy_type,
                    target,
                    git_commit,
                    duration_ms / 1000.0,
                    violations_fixed=0,
                )

            lines.append(f"\n✅ Deploy successful ({duration_ms}ms)")
            health = result.get("health_status", {})
            if health.get("checks"):
                lines.append(f"Health checks: {sum(1 for c in health['checks'] if c['healthy'])}/{len(health['checks'])} passed")
        else:
            error_pattern = result.get("error_pattern")
            log_deploy(path, deploy_type, target, git_commit, False, duration_ms, error_pattern)

            # Log to deployment history database
            scan_result = locals().get('scan_result', {})
            health = result.get("health_status", {})
            log_deployment(
                path=path,
                deploy_type=deploy_type,
                target=target,
                user=None,  # TODO: Get from auth context
                success=False,
                rollback=rollback_on_fail,
                scan_passed=scan_result.get('critical', 0) == 0,
                violations_critical=scan_result.get('critical', 0),
                violations_high=scan_result.get('high', 0),
                health_check_passed=health.get('healthy', False),
                error_message=result.get('error', 'Unknown error')[:500],  # Truncate to 500 chars
                duration_ms=duration_ms
            )

            # Notify deployment failure
            if notif_config:
                notify_deployment_failure(
                    notif_config,
                    project_name,
                    deploy_type,
                    target,
                    git_commit,
                    result.get('error', 'Unknown error'),
                    violations_count=scan_result.get('critical', 0) if 'scan_result' in locals() else 0,
                )

            lines.append(f"\n❌ Deploy failed: {result.get('error', 'Unknown error')}")
            if result.get("fix_suggestion"):
                lines.append(f"\nSuggested fix:\n{result['fix_suggestion']}")
            if rollback_on_fail:
                lines.append("\nRolling back...")
                rollback_result = executor.rollback()
                lines.append(f"Rollback: {rollback_result.get('status', 'unknown')}")

    return "\n".join(lines)


def _handle_mine_patterns(args: dict) -> str:
    """Mine recurring patterns from scan history."""
    _ensure_scanner()
    from learning.miner import mine_patterns

    min_occ = int(args.get("min_occurrences", 5))
    threshold = float(args.get("similarity_threshold", 0.8))
    days = int(args.get("lookback_days", 30))
    path = args.get("path")

    patterns = mine_patterns(min_occ, threshold, days, path)

    if not patterns:
        return "No recurring patterns found."

    lines = [f"Pattern Mining: {len(patterns)} patterns found\n"]
    for i, p in enumerate(patterns, 1):
        lines.append(f"{i}. [{p.severity}] {p.category}")
        lines.append(f"   Pattern: {p.pattern}")
        lines.append(f"   Occurrences: {p.occurrence_count}")
        lines.append(f"   Confidence: {p.confidence:.2f}")
        lines.append(f"   Example: {p.example_file}:{p.example_line}")
        lines.append("")

    return "\n".join(lines)


def _handle_mine_global(args: dict) -> str:
    """Mine patterns across all projects."""
    _ensure_scanner()
    from learning.global_miner import mine_patterns_global, get_global_mining_report

    action = args.get("action", "mine")

    if action == "report":
        days = int(args.get("lookback_days", 30))
        report = get_global_mining_report(days)

        lines = [
            f"Global Mining Report ({days} days)",
            f"Total violations: {report['total_violations']}",
            f"Unique projects: {report['unique_projects']}",
            f"Cross-project potential: {report['cross_project_potential']} patterns",
            "",
            "By Platform:",
        ]
        for platform, count in report['platforms'].items():
            lines.append(f"  {platform}: {count}")

        lines.append("\nTop Projects:")
        sorted_projects = sorted(report['projects'].items(), key=lambda x: x[1], reverse=True)
        for project, count in sorted_projects[:10]:
            lines.append(f"  {project}: {count}")

        return "\n".join(lines)

    else:
        min_occ = int(args.get("min_occurrences", 5))
        threshold = float(args.get("similarity_threshold", 0.8))
        days = int(args.get("lookback_days", 30))
        min_projects = int(args.get("min_projects", 2))

        patterns = mine_patterns_global(min_occ, threshold, days, min_projects)

        if not patterns:
            return f"No cross-project patterns found (min {min_projects} projects)"

        lines = [f"Global Pattern Mining: {len(patterns)} cross-project patterns\n"]
        for i, p in enumerate(patterns, 1):
            universal = " [UNIVERSAL]" if p.is_universal else ""
            lines.append(f"{i}. [{p.severity}] {p.category}{universal}")
            lines.append(f"   Pattern: {p.pattern}")
            lines.append(f"   Projects: {p.project_count}")
            lines.append(f"   Occurrences: {p.occurrence_count}")
            lines.append(f"   Confidence: {p.confidence:.2f}")
            lines.append("")

        return "\n".join(lines)


def _handle_learn_from_folder(args: dict) -> str:
    """Learn patterns from arbitrary folder and create lessons."""
    _ensure_scanner()
    from agent.learn import learn_from_folder

    path = _resolve_path(args["path"])
    min_occ = int(args.get("min_occurrences", 3))
    auto_approve = args.get("auto_approve", False)
    categories = args.get("categories")

    result = learn_from_folder(path, min_occ, auto_approve, categories)

    if "error" in result:
        return result["error"]

    lines = [f"Kiwi Learn from Folder: {path}\n"]
    lines.append(f"Scanned: {result['scanned_files']} PHP files")
    lines.append(f"Patterns found: {result['patterns_found']}")
    lines.append(f"Suggestions: {len(result['suggestions'])}\n")

    if not result['suggestions']:
        return "\n".join(lines) + "\nNo patterns met the min_occurrences threshold."

    for i, sug in enumerate(result['suggestions'], 1):
        lines.append(f"{i}. [{sug['severity']}] {sug['title']}")
        lines.append(f"   Category: {sug['category']}")
        lines.append(f"   Occurrences: {sug['occurrences']} times in {len(sug['files'])} files")
        lines.append(f"   Pattern: {sug['pattern']}")
        lines.append(f"   Why: {sug['why']}")
        lines.append("")

    if auto_approve and "created_lessons" in result:
        lines.append(f"\nAuto-created {len(result['created_lessons'])} lessons:")
        for lesson in result['created_lessons']:
            lines.append(f"  - {lesson['lesson_id']}: {lesson['file']}")

    return "\n".join(lines)


def _handle_review_suggestions(args: dict) -> str:
    """Review suggested lessons."""
    _ensure_scanner()
    from memory.db import get_suggested_lessons

    status = args.get("status", "pending")
    suggestions = get_suggested_lessons(status)

    if not suggestions:
        return f"No {status} suggestions found."

    lines = [f"Suggested Lessons ({status}): {len(suggestions)}\n"]
    for s in suggestions:
        lines.append(f"ID: {s['id']}")
        lines.append(f"  [{s['severity']}] {s['category']}")
        lines.append(f"  Pattern: {s['pattern']}")
        lines.append(f"  Example: {s['example_file']}:{s['example_line']}")
        lines.append("")

    return "\n".join(lines)


def _handle_approve_suggestion(args: dict) -> str:
    """Approve and generate lesson from suggestion."""
    _ensure_scanner()
    from learning.generator import generate_lesson

    suggestion_id = args["suggestion_id"]
    severity = args.get("severity")
    category = args.get("category")

    lesson_id = generate_lesson(suggestion_id, severity, category)

    if lesson_id:
        return f"✅ Lesson created: {lesson_id}\nRun rebuild_index.py to update README."
    else:
        return f"❌ Failed to generate lesson from suggestion {suggestion_id}"


def _handle_reject_suggestion(args: dict) -> str:
    """Reject suggested lesson."""
    _ensure_scanner()
    from memory.db import update_suggested_lesson_status

    suggestion_id = args["suggestion_id"]
    reason = args["reason"]

    update_suggested_lesson_status(suggestion_id, "rejected")

    return f"Suggestion {suggestion_id} rejected: {reason}"


def _handle_dedup(args: dict) -> str:
    """Find and merge duplicate lessons."""
    _ensure_scanner()
    from learning.dedup import find_duplicate_lessons, merge_lessons, get_dedup_report

    threshold = float(args.get("threshold", 0.9))
    dry_run = args.get("dry_run", False)

    if dry_run:
        report = get_dedup_report(threshold)

        if report['clusters_found'] == 0:
            return f"No duplicate lessons found (threshold: {threshold})"

        lines = [
            f"Found {report['clusters_found']} duplicate clusters ({report['total_duplicates']} lessons to merge)",
            f"Similarity threshold: {threshold}",
            ""
        ]

        for i, cluster in enumerate(report['clusters'], 1):
            lines.append(f"Cluster {i} (similarity: {cluster['similarity']:.2f}):")
            for lesson_id, title in zip(cluster['lesson_ids'], cluster['titles']):
                lines.append(f"  - {lesson_id}: {title}")
            lines.append("")

        return "\n".join(lines)

    else:
        clusters = find_duplicate_lessons(threshold)

        if not clusters:
            return f"No duplicate lessons found (threshold: {threshold})"

        merged_count = 0
        results = []

        for cluster in clusters:
            merged = merge_lessons(cluster, dry_run=False)
            if merged:
                merged_count += 1
                results.append(f"Merged {len(cluster)} lessons into {merged['lesson_id']}")

        return f"Merged {merged_count} clusters\n" + "\n".join(results)


def _handle_agent_spawn(args: dict) -> str:
    """Spawn specialized agent for parallel execution."""
    from memory import coordination as coord

    agent_type = args["agent_type"]
    path = _resolve_path(args["path"])
    mode = args.get("mode", "review")
    severity = args.get("severity", "CRITICAL")
    max_fixes = int(args.get("max_fixes", 5))

    if not os.path.isdir(path):
        return f"ERROR: Directory not found: {path}"

    run_id = coord.create_agent_run(
        path=path,
        mode=mode,
        agent_type=agent_type,
        parent_run_id=None
    )

    return f"Agent spawned: {agent_type}\nRun ID: {run_id}\nPath: {path}\nMode: {mode}\nSeverity: {severity}\n\nUse kiwi_agent_sync([{run_id}]) to wait for completion."


def _handle_agent_sync(args: dict) -> str:
    """Wait for spawned agents to complete and collect results."""
    from memory import coordination as coord
    import time

    agent_ids = args["agent_ids"]

    lines = [f"Waiting for {len(agent_ids)} agents to complete..."]

    max_wait = 300
    start = time.time()

    while time.time() - start < max_wait:
        all_done = True
        for run_id in agent_ids:
            run = coord.get_agent_run(run_id)
            if not run:
                lines.append(f"  Agent {run_id}: NOT FOUND")
                continue

            if run["status"] in ("pending", "running", "checkpoint_waiting"):
                all_done = False
            else:
                lines.append(f"  Agent {run_id} ({run['agent_type']}): {run['status']}")

        if all_done:
            break

        time.sleep(2)

    if not all_done:
        lines.append(f"\nTimeout after {max_wait}s. Some agents still running.")
    else:
        lines.append("\nAll agents completed.")

    return "\n".join(lines)


def _handle_agent_consensus(args: dict) -> str:
    """Get consensus verdict from multiple agents on a specific violation."""
    from memory import coordination as coord

    lesson_id = args["lesson_id"]
    file = args["file"]
    line = args.get("line")

    consensus = coord.calculate_consensus(lesson_id, file, line)

    lines = [
        f"Consensus for {lesson_id} in {file}" + (f":{line}" if line else ""),
        f"Verdict: {consensus['consensus']}",
        f"Confidence: {consensus['confidence']}",
        f"Agent count: {consensus['agent_count']}",
        f"Needs human review: {consensus['needs_human']}",
        ""
    ]

    if consensus.get("verdicts"):
        lines.append("Verdicts breakdown:")
        for verdict, data in consensus["verdicts"].items():
            lines.append(f"  {verdict}: {data['count']} agents (confidence: {data['confidence_sum']:.2f})")

    return "\n".join(lines)


def _handle_agent_consensus(args: dict) -> str:
    """Get consensus verdict from multiple agents on a specific violation."""
    from memory import coordination as coord

    lesson_id = args["lesson_id"]
    file = args["file"]
    line = args.get("line")

    consensus = coord.calculate_consensus(lesson_id, file, line)

    lines = [
        f"Consensus for {lesson_id} in {file}" + (f":{line}" if line else ""),
        f"Verdict: {consensus['consensus']}",
        f"Confidence: {consensus['confidence']}",
        f"Agent count: {consensus['agent_count']}",
        f"Needs human review: {consensus['needs_human']}",
        ""
    ]

    if consensus.get("verdicts"):
        lines.append("Verdicts breakdown:")
        for verdict, data in consensus["verdicts"].items():
            lines.append(f"  {verdict}: {data['count']} agents (confidence: {data['confidence_sum']:.2f})")

    return "\n".join(lines)


def _handle_plan(args: dict) -> str:
    """Generate execution plan with task dependencies."""
    _ensure_scanner()
    from scanner.cli import scan_theme
    from planner.htn import TaskPlanner
    from planner.scheduler import TaskScheduler

    path = _resolve_path(args["path"])
    severity = args.get("severity", "CRITICAL")
    max_fixes = int(args.get("max_fixes", 10))

    if not os.path.isdir(path):
        return f"ERROR: Directory not found: {path}"

    report = scan_theme(path, severity_filter=severity)

    if not report.violations:
        return "No violations found. Nothing to plan."

    violations = [
        {
            "lesson_id": v.lesson_id,
            "file": v.file,
            "line": v.line,
            "severity": v.severity,
            "category": v.category,
            "description": v.description,
        }
        for v in report.violations
    ]

    planner = TaskPlanner(path)
    plan = planner.plan(violations, max_fixes=max_fixes)

    scheduler = TaskScheduler(plan.tasks, plan.dependency_graph)
    stages = scheduler.schedule()
    stages = scheduler.reorder_for_risk(stages)
    critical_path = scheduler.get_critical_path(stages)

    lines = [
        f"Execution Plan: {path}",
        f"Total tasks: {len(plan.tasks)} (from {len(violations)} violations)",
        f"Estimated duration: {plan.estimated_duration_minutes} minutes",
        f"Parallel stages: {len(stages)}",
        ""
    ]

    lines.append("Top Priority Tasks:")
    for i, task in enumerate(plan.tasks[:5], 1):
        lines.append(f"  {i}. {task.lesson_id} — {task.file}:{task.line}")
        lines.append(f"     Priority: {task.priority:.2f} | Effort: {task.effort} | Risk: {task.risk}")

    if len(plan.tasks) > 5:
        lines.append(f"  ... +{len(plan.tasks) - 5} more tasks")

    lines.append("")
    lines.append("Execution Stages (tasks in same stage can run in parallel):")
    for stage in stages[:3]:
        lines.append(f"  Stage {stage.stage_number + 1}: {len(stage.task_ids)} tasks (~{stage.estimated_duration_minutes}min)")
        for tid in stage.task_ids[:3]:
            task = next(t for t in plan.tasks if t.task_id == tid)
            lines.append(f"    - {task.lesson_id} ({task.file})")
        if len(stage.task_ids) > 3:
            lines.append(f"    ... +{len(stage.task_ids) - 3} more")

    if len(stages) > 3:
        lines.append(f"  ... +{len(stages) - 3} more stages")

    lines.append("")

    if critical_path:
        lines.append(f"Critical Path ({len(critical_path)} tasks):")
        for tid in critical_path[:5]:
            task = next((t for t in plan.tasks if t.task_id == tid), None)
            if task:
                lines.append(f"  → {task.lesson_id} ({task.file})")
        if len(critical_path) > 5:
            lines.append(f"  ... +{len(critical_path) - 5} more")

    return "\n".join(lines)


def _handle_plan(args: dict) -> str:
    """Generate execution plan with task dependencies."""
    _ensure_scanner()
    from scanner.cli import scan_theme
    from planner.htn import TaskPlanner
    from planner.scheduler import TaskScheduler

    path = _resolve_path(args["path"])
    severity = args.get("severity", "CRITICAL")
    max_fixes = int(args.get("max_fixes", 10))

    if not os.path.isdir(path):
        return f"ERROR: Directory not found: {path}"

    report = scan_theme(path, severity_filter=severity)

    if not report.violations:
        return "No violations found. Nothing to plan."

    violations = [
        {
            "lesson_id": v.lesson_id,
            "file": v.file,
            "line": v.line,
            "severity": v.severity,
            "category": v.category,
            "description": v.description,
        }
        for v in report.violations
    ]

    planner = TaskPlanner(path)
    plan = planner.plan(violations, max_fixes=max_fixes)

    scheduler = TaskScheduler(plan.tasks, plan.dependency_graph)
    stages = scheduler.schedule()
    stages = scheduler.reorder_for_risk(stages)
    critical_path = scheduler.get_critical_path(stages)

    lines = [
        f"Execution Plan: {path}",
        f"Total tasks: {len(plan.tasks)} (from {len(violations)} violations)",
        f"Estimated duration: {plan.estimated_duration_minutes} minutes",
        f"Parallel stages: {len(stages)}",
        ""
    ]

    lines.append("Top Priority Tasks:")
    for i, task in enumerate(plan.tasks[:5], 1):
        lines.append(f"  {i}. {task.lesson_id} — {task.file}:{task.line}")
        lines.append(f"     Priority: {task.priority:.2f} | Effort: {task.effort} | Risk: {task.risk}")

    if len(plan.tasks) > 5:
        lines.append(f"  ... +{len(plan.tasks) - 5} more tasks")

    lines.append("")
    lines.append("Execution Stages (tasks in same stage can run in parallel):")
    for stage in stages[:3]:
        lines.append(f"  Stage {stage.stage_number + 1}: {len(stage.task_ids)} tasks (~{stage.estimated_duration_minutes}min)")
        for tid in stage.task_ids[:3]:
            task = next(t for t in plan.tasks if t.task_id == tid)
            lines.append(f"    - {task.lesson_id} ({task.file})")
        if len(stage.task_ids) > 3:
            lines.append(f"    ... +{len(stage.task_ids) - 3} more")

    if len(stages) > 3:
        lines.append(f"  ... +{len(stages) - 3} more stages")

    lines.append("")

    if critical_path:
        lines.append(f"Critical Path ({len(critical_path)} tasks):")
        for tid in critical_path[:5]:
            task = next((t for t in plan.tasks if t.task_id == tid), None)
            if task:
                lines.append(f"  → {task.lesson_id} ({task.file})")
        if len(critical_path) > 5:
            lines.append(f"  ... +{len(critical_path) - 5} more")

    return "\n".join(lines)


def _handle_explain(args: dict) -> str:
    """Explain a violation with alternatives and risk analysis."""
    from web.explainability import explain_violation

    lesson_id = args["lesson_id"]
    file = args["file"]
    line = args["line"]
    match_text = args.get("match_text", "")

    explanation = explain_violation(lesson_id, file, line, match_text)

    if "error" in explanation:
        return f"ERROR: {explanation['error']}"

    lines = [
        f"# {explanation['lesson_id']} — {explanation['title']}",
        f"[{explanation['severity']}] [{explanation['category']}]",
        f"Location: {explanation['file']}:{explanation['line']}",
        "",
        "## Why This Is a Problem",
        explanation['why'],
        "",
    ]

    if explanation.get('alternatives'):
        lines.append("## Alternative Approaches")
        for i, alt in enumerate(explanation['alternatives'], 1):
            lines.append(f"{i}. **{alt['approach']}**")
            lines.append(f"   {alt['description']}")
            lines.append(f"   Tradeoffs: {alt['tradeoffs']}")
        lines.append("")

    lines.append("## Regression Risk")
    risk = explanation['risk']
    lines.append(f"Level: {risk['level']} (probability: {risk['probability']:.0%})")
    lines.append(f"Impact: {risk['impact']}")
    lines.append(f"{risk['explanation']}")
    lines.append("")

    lines.append("## Fix Suggestion")
    fix = explanation['fix_suggestion']
    lines.append(f"Type: {fix['type']}")
    lines.append(f"{fix['description']}")
    for step in fix['steps']:
        lines.append(f"  - {step}")

    return "\n".join(lines)


def _handle_checkpoint(args: dict) -> str:
    """Create or resolve a checkpoint."""
    from web.checkpoint import create_checkpoint, resolve_checkpoint, get_pending_checkpoints

    action = args.get("action", "list")

    if action == "create":
        agent_run_id = args["agent_run_id"]
        message = args["message"]
        options = args["options"]

        checkpoint = create_checkpoint(agent_run_id, message, options)

        return f"Checkpoint created: {checkpoint.checkpoint_id}\nMessage: {message}\nOptions: {', '.join(opt['label'] for opt in options)}"

    elif action == "resolve":
        checkpoint_id = args["checkpoint_id"]
        decision = args["decision"]
        comment = args.get("comment")

        success = resolve_checkpoint(checkpoint_id, decision, comment)

        if success:
            return f"Checkpoint {checkpoint_id} resolved with decision: {decision}"
        else:
            return f"ERROR: Checkpoint {checkpoint_id} not found"

    else:  # list
        agent_run_id = args.get("agent_run_id")
        checkpoints = get_pending_checkpoints(agent_run_id)

        if not checkpoints:
            return "No pending checkpoints"

        lines = [f"Pending Checkpoints: {len(checkpoints)}\n"]
        for cp in checkpoints:
            lines.append(f"ID: {cp.checkpoint_id}")
            lines.append(f"Agent Run: {cp.agent_run_id}")
            lines.append(f"Message: {cp.message}")
            lines.append(f"Options: {', '.join(opt['label'] for opt in cp.options)}")
            lines.append("")

        return "\n".join(lines)


def _handle_session_save(args: dict) -> str:
    """Save current agent session for later resume."""
    from session import SessionManager, SessionStateBuilder, generate_session_id

    path = _resolve_path(args["path"])
    mode = args.get("mode", "review")
    state_data = args.get("state", {})

    session_id = args.get("session_id") or generate_session_id(path, mode)

    manager = SessionManager()
    session_file = manager.save_session(
        session_id=session_id,
        state=state_data,
        metadata={
            "path": path,
            "mode": mode,
            "severity": args.get("severity", "CRITICAL")
        }
    )

    return f"Session saved: {session_id}\nFile: {session_file}\n\nUse kiwi_session_resume(session_id='{session_id}') to resume."


def _handle_session_resume(args: dict) -> str:
    """Resume saved agent session."""
    from session import SessionManager

    session_id = args["session_id"]

    manager = SessionManager()
    session_data = manager.resume_session(session_id)

    if not session_data:
        return f"ERROR: Session not found: {session_id}\n\nUse kiwi_session_list to see available sessions."

    lines = [
        f"Session resumed: {session_id}",
        f"Original saved: {session_data['original_saved_at']}",
        f"Resumed at: {session_data['resumed_at']}",
        "",
        "Metadata:",
        f"  Path: {session_data['metadata'].get('path')}",
        f"  Mode: {session_data['metadata'].get('mode')}",
        f"  Severity: {session_data['metadata'].get('severity')}",
        "",
        "State:",
        f"  Iteration: {session_data['state'].get('iteration', 0)}",
        f"  Violations: {len(session_data['state'].get('violations', []))}",
        f"  Fixes applied: {session_data['state'].get('fixes_applied', 0)}",
        f"  Tokens used: {session_data['state'].get('tokens_used', 0)}",
    ]

    return "\n".join(lines)


def _handle_user_login(args: dict) -> str:
    """Handle user login and return user info."""
    from auth import RBACManager

    username = args["username"]

    manager = RBACManager()

    # In real implementation, would verify credentials
    # For now, just lookup user by username
    import sqlite3
    conn = sqlite3.connect(manager.db_path)
    try:
        cursor = conn.cursor()

        cursor.execute(
            "SELECT id, username, email, role, team_id, active FROM users WHERE username = ?",
            (username,)
        )

        row = cursor.fetchone()

        if not row:
            return f"ERROR: User not found: {username}\n\nUse kiwi_user_create to create a new user."

        user_id, username, email, role, team_id, active = row

        if not active:
            return f"ERROR: User account is inactive: {username}"

        lines = [
            f"User logged in: {username}",
            f"  ID: {user_id}",
            f"  Email: {email}",
            f"  Role: {role}",
            f"  Team ID: {team_id or 'None'}",
            f"  Active: {bool(active)}",
        ]

        return "\n".join(lines)
    finally:
        conn.close()


def _handle_team_preferences(args: dict) -> str:
    """Get or set team preferences."""
    from auth import RBACManager
    import json

    team_id = args["team_id"]
    action = args.get("action", "get")

    manager = RBACManager()

    import sqlite3
    conn = sqlite3.connect(manager.db_path)
    try:
        cursor = conn.cursor()

        if action == "get":
            cursor.execute(
                "SELECT name, preferences FROM teams WHERE id = ?",
                (team_id,)
            )

            row = cursor.fetchone()

            if not row:
                return f"ERROR: Team not found: {team_id}"

            name, prefs_json = row
            prefs = json.loads(prefs_json)

            lines = [f"Team preferences: {name}"]
            for key, value in prefs.items():
                lines.append(f"  {key}: {value}")

            return "\n".join(lines)

        elif action == "set":
            key = args.get("key")
            value = args.get("value")

            if not key:
                return "ERROR: key parameter required for action=set"

            # Get current preferences
            cursor.execute(
                "SELECT preferences FROM teams WHERE id = ?",
                (team_id,)
            )

            row = cursor.fetchone()
            if not row:
                return f"ERROR: Team not found: {team_id}"

            prefs = json.loads(row[0])
            prefs[key] = value

            # Update preferences
            cursor.execute(
                "UPDATE teams SET preferences = ? WHERE id = ?",
                (json.dumps(prefs), team_id)
            )

            conn.commit()

            return f"Team preference updated: {key} = {value}"

        else:
            return f"ERROR: Invalid action: {action}. Use 'get' or 'set'."
    finally:
        conn.close()


def _handle_session_list(args: dict) -> str:
    """List all saved sessions."""
    from session import SessionManager

    manager = SessionManager()
    sessions = manager.list_sessions()

    if not sessions:
        return "No saved sessions found."

    lines = ["Saved sessions:"]
    for s in sessions:
        meta = s.get('metadata', {})
        lines.append(f"\n{s['session_id']}")
        lines.append(f"  Saved: {s['saved_at']}")
        lines.append(f"  Path: {meta.get('path', 'N/A')}")
        lines.append(f"  Mode: {meta.get('mode', 'N/A')}")

    return "\n".join(lines)


def _handle_impact(args: dict) -> str:
    """Handle kiwi_impact tool — impact analysis for regression defense."""
    _ensure_scanner()
    from scanner.impact import ImpactAnalyzer
    from scanner.cli import scan_theme

    file_path = args["file"]
    auto_scan = args.get("auto_scan", False)
    severity = args.get("severity", "CRITICAL")

    if not os.path.isfile(file_path):
        return f"ERROR: File not found: {file_path}"

    # Detect project root
    project_root = os.path.dirname(os.path.abspath(file_path))
    while project_root != os.path.dirname(project_root):
        if os.path.isdir(os.path.join(project_root, ".git")):
            break
        project_root = os.path.dirname(project_root)

    analyzer = ImpactAnalyzer(project_root)
    report = analyzer.analyze_fix_impact(file_path, auto_scan)

    lines = [
        f"📊 IMPACT ANALYSIS: {os.path.basename(file_path)}",
        f"Symbols changed: {', '.join(report.symbols_changed) if report.symbols_changed else 'none detected'}",
        ""
    ]

    if not report.affected_files:
        lines.append("✅ No affected files detected — impact likely minimal")
        return "\n".join(lines)

    # Group by risk
    high_risk = [f for f in report.affected_files if f.risk == "HIGH"]
    medium_risk = [f for f in report.affected_files if f.risk == "MEDIUM"]
    low_risk = [f for f in report.affected_files if f.risk == "LOW"]

    if high_risk:
        lines.append(f"🔴 HIGH RISK ({len(high_risk)} files)")
        for af in high_risk[:5]:
            rel_path = os.path.relpath(af.path, project_root)
            lines.append(f"  - {rel_path}")
            lines.append(f"    {af.reason}")
            if af.line_numbers:
                line_preview = ', '.join(str(ln) for ln in sorted(af.line_numbers)[:5])
                lines.append(f"    Lines: {line_preview}")
        lines.append("")

    if medium_risk:
        lines.append(f"🟡 MEDIUM RISK ({len(medium_risk)} files)")
        for af in medium_risk[:5]:
            rel_path = os.path.relpath(af.path, project_root)
            lines.append(f"  - {rel_path}")
            lines.append(f"    {af.reason}")
        lines.append("")

    if low_risk:
        lines.append(f"🟢 LOW RISK ({len(low_risk)} files)")
        for af in low_risk[:3]:
            rel_path = os.path.relpath(af.path, project_root)
            lines.append(f"  - {rel_path}: {af.reason}")
        lines.append("")

    lines.append(f"💡 SUGGESTIONS")
    for i, suggestion in enumerate(report.suggestions, 1):
        lines.append(f"  {i}. {suggestion}")

    # Auto-scan if requested
    if auto_scan and (high_risk or medium_risk):
        lines.append("")
        lines.append(f"[auto_scan=True] Running scans (severity={severity})...")

        for af in high_risk + medium_risk:
            try:
                scan_report = scan_theme(af.path, severity_filter=severity, skip_empty_scope=True)
                rel_path = os.path.relpath(af.path, project_root)

                if scan_report.critical_count > 0:
                    lines.append(f"  ⛔ {rel_path} — BLOCK ({scan_report.critical_count} CRITICAL)")
                    for v in scan_report.violations[:3]:
                        lines.append(f"     L{v.line}: {v.lesson_id} {v.title}")
                elif scan_report.high_count > 0:
                    lines.append(f"  ⚠ {rel_path} — {scan_report.high_count} HIGH")
                else:
                    lines.append(f"  ✅ {rel_path} — PASS")
            except Exception as e:
                lines.append(f"  ❌ {os.path.relpath(af.path, project_root)} — scan failed: {e}")

    return "\n".join(lines)


def _handle_learn_session(args: dict) -> str:
    """
    Trigger Kiwi learning from session logs. Extracts patterns Claude used.

    Args:
        session_id: Specific session to learn from (optional, learns all unprocessed if omitted)

    Returns:
        Learning results: patterns extracted, styles learned, bindings recorded
    """
    try:
        from agent.reasoning.learner import learn_from_session, learn_all_unprocessed

        session_id = args.get("session_id")
        if session_id:
            result = learn_from_session(session_id)
            return json.dumps(result, indent=2, ensure_ascii=False)
        else:
            results = learn_all_unprocessed()
            if not results:
                return "No unprocessed sessions found."
            lines = [f"Processed {len(results)} session(s):"]
            for r in results:
                lines.append(f"  {r['session_id']}: {r.get('status', '?')} "
                             f"(ctx:{r.get('context_patterns', 0)}, "
                             f"style:{r.get('style_updates', 0)}, "
                             f"bind:{r.get('bindings', 0)})")
            return "\n".join(lines)
    except Exception as e:
        return f"ERROR: Learning failed: {e}"


def _handle_scan_learn(args: dict) -> str:
    """
    Scan file and auto-detect patterns for new lessons.

    Args:
        file: Single file path
        severity: Filter by severity (default: ALL)

    Returns:
        Scan report + suggested lessons

    Example:
        kiwi_scan_learn(file="themes/sfvn/functions.php", severity="CRITICAL")
    """
    _ensure_scanner()
    from learning.single_file import extract_patterns_from_file

    file_path = args["file"]
    severity = args.get("severity", "ALL")

    if not os.path.isfile(file_path):
        return f"ERROR: File not found: {file_path}"

    # Extract patterns directly (no scan needed)
    try:
        suggestions = extract_patterns_from_file(file_path, min_confidence=0.7)
    except Exception as e:
        return f"ERROR: Pattern extraction failed: {e}"

    # Format output
    lines = [
        f"File: {Path(file_path).name}",
        f"Patterns detected: {len(suggestions)}",
        ""
    ]

    if suggestions:
        lines.append("Suggested Lessons:")
        for i, sug in enumerate(suggestions, 1):
            lines.append(f"{i}. {Path(sug.example_file).name} (confidence: {sug.confidence:.2f})")
            lines.append(f"   Category: {sug.category} | Severity: {sug.severity}")
            lines.append(f"   Pattern: {sug.pattern[:80]}..." if len(sug.pattern) > 80 else f"   Pattern: {sug.pattern}")
            lines.append(f"   Example: {sug.example_file}:{sug.example_line}")
            lines.append("")
        lines.append("Review: kiwi_review_suggestions()")
        lines.append("Approve: kiwi_approve_suggestion(id)")
    else:
        lines.append("No new patterns detected.")

    return "\n".join(lines)


def _handle_init(args: dict) -> str:
    """Onboard a project: stack detect → mine → review → seed scan → learn → anchor + hook."""
    _ensure_scanner()
    from agent.init_pipeline import run_init, format_init_report

    path = _resolve_path(args["path"])
    if not os.path.isdir(path):
        return f"ERROR: Directory not found: {path}"

    report = run_init(
        project_path=path,
        write_anchor=args.get("write_anchor", True),
        write_cursor=args.get("write_cursor", False),
        write_windsurf=args.get("write_windsurf", False),
        assume_yes=True,
    )
    return format_init_report(report)


# --- MCP Protocol ---

TOOL_DEFS = [
    {
        "name": "kiwi_init",
        "description": "Onboard a project: detect stack → mine lessons → review → seed scan → learn session → write Kiwi gate anchor + register PreToolUse hook. Idempotent. Run once per new project to warm db_scores/conventions so kiwi_context ranks by project signal, not bare severity.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "Project path hoặc name"},
                "write_anchor": {"type": "boolean", "default": True, "description": "Write Kiwi gate block into CLAUDE.md/AGENTS.md"},
                "write_cursor": {"type": "boolean", "default": False, "description": "Also write .cursor/rules/kiwi.mdc"},
                "write_windsurf": {"type": "boolean", "default": False, "description": "Also write .windsurfrules"},
            },
            "required": ["path"],
        },
    },
    {
        "name": "kiwi_scan",
        "description": "Scan project/theme cho bug patterns. Trả violations grouped by severity. Dùng path hoặc project name (wezone-plugins, webstore-vn).",
        "inputSchema": {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "Path hoặc project name"},
                "severity": {"type": "string", "enum": ["CRITICAL", "HIGH", "SUGGEST", "ALL"], "default": "ALL"},
                "platform": {"type": "string", "enum": ["wp", "nextjs"]},
                "scope": {"type": "string", "enum": ["theme", "plugin"]},
                "diff_only": {"type": "boolean", "default": False},
                "max_per_lesson": {"type": "integer", "default": 5},
            },
            "required": ["path"],
        },
    },
    {
        "name": "kiwi_query",
        "description": "Search Kiwi knowledge base theo keyword, category, severity. Tìm lessons liên quan.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "keyword": {"type": "string", "description": "Keyword (ví dụ: IDOR, XSS, mobile-first)"},
                "category": {"type": "string"},
                "severity": {"type": "string", "enum": ["CRITICAL", "HIGH", "SUGGEST", "INFO"]},
                "platform": {"type": "string", "enum": ["wp", "nextjs"]},
                "limit": {"type": "integer", "default": 10},
            },
        },
    },
    {
        "name": "kiwi_lesson",
        "description": "Đọc full lesson: Bad/Good/Why/Grep. Dùng khi cần hiểu chi tiết pattern.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "id": {"type": "string", "description": "Lesson ID (LES-016, FEA-025)"},
            },
            "required": ["id"],
        },
    },
    {
        "name": "kiwi_add",
        "description": "Thêm lesson mới. Tạo file, update _meta.json, rebuild README.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "category": {"type": "string"},
                "severity": {"type": "string", "enum": ["CRITICAL", "HIGH", "SUGGEST"]},
                "title": {"type": "string"},
                "scan_type": {"type": "string", "enum": ["presence", "absence", "cross-check", "bom-check"], "default": "presence"},
                "pattern": {"type": "string"},
                "scope": {"type": "string", "default": "**/*.php"},
                "tags": {"type": "array", "items": {"type": "string"}, "default": ["theme"]},
                "bad_code": {"type": "string"},
                "good_code": {"type": "string"},
                "why": {"type": "string"},
                "platform": {"type": "string", "enum": ["wp", "nextjs", "both"], "default": "wp"},
            },
            "required": ["category", "severity", "title", "pattern"],
        },
    },
    {
        "name": "kiwi_stats",
        "description": "Thống kê knowledge base: severity, category, check type.",
        "inputSchema": {"type": "object", "properties": {}},
    },
    {
        "name": "kiwi_learning_health",
        "description": "Health snapshot of Kiwi active-learning system. Returns sessions, bindings, styles, suggestions, fail counters, themes learned, top bindings. Read-only — safe to call any time. Status: healthy | degraded | stalled | disabled.",
        "inputSchema": {"type": "object", "properties": {}},
    },
    {
        "name": "kiwi_fix",
        "description": "Fix suggestion hoặc auto-fix violation. Không có file → trả Good example. Có file → preview diff. Có file+apply=true → apply fix.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "lesson_id": {"type": "string", "description": "Lesson ID"},
                "file": {"type": "string", "description": "Path file chứa violation (cần cho auto-fix)"},
                "line": {"type": "integer", "description": "Line number of violation"},
                "apply": {"type": "boolean", "default": False, "description": "true = apply fix, false = preview diff only"},
            },
            "required": ["lesson_id"],
        },
    },
    {
        "name": "kiwi_template",
        "description": "Query template library (hero, header, footer, product-card, ...). Code mẫu đã kiểm chứng.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "section": {"type": "string", "description": "Section type (hero, header, footer, ...)"},
                "tag": {"type": "string"},
                "keyword": {"type": "string"},
                "detail": {"type": "boolean", "default": False, "description": "true = full code"},
            },
        },
    },
    {
        "name": "kiwi_agent",
        "description": "Run Kiwi Agent: autonomous scan → analyze → fix → verify loop. Modes: review (read-only report), interactive (ask before fix), auto (fix all + verify).",
        "inputSchema": {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "Project path hoặc name"},
                "mode": {"type": "string", "enum": ["review", "interactive", "auto"], "default": "review"},
                "severity": {"type": "string", "enum": ["CRITICAL", "HIGH", "SUGGEST", "ALL"], "default": "CRITICAL"},
                "max_fixes": {"type": "integer", "default": 10},
            },
            "required": ["path"],
        },
    },
    {
        "name": "kiwi_dismiss",
        "description": "Mark violation as false positive. Sẽ không hiện lại trong scan tương lai. Scope: file (chỉ file này), project, global.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "lesson_id": {"type": "string", "description": "Lesson ID"},
                "file": {"type": "string", "description": "File path chứa violation"},
                "reason": {"type": "string", "description": "Tại sao đây là false positive"},
                "scope": {"type": "string", "enum": ["file", "project", "global"], "default": "file"},
            },
            "required": ["lesson_id", "file", "reason"],
        },
    },
    {
        "name": "kiwi_reenable",
        "description": "Re-enable a disabled lesson. Lesson sẽ được bật lại trong scan tương lai.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "lesson_id": {"type": "string", "description": "Lesson ID to re-enable"},
            },
            "required": ["lesson_id"],
        },
    },
    {
        "name": "kiwi_detect_anomalies",
        "description": "Detect anomalies in recent violations and suggest new patterns. Phát hiện patterns mới chưa có trong lessons.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "lookback_days": {"type": "integer", "default": 7, "description": "Number of days to look back for violations"},
            },
        },
    },
    {
        "name": "kiwi_trends",
        "description": "Xem trend violations theo thời gian. Phát hiện regression giữa 2 scan gần nhất.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "Project path hoặc name"},
                "days": {"type": "integer", "default": 30},
            },
            "required": ["path"],
        },
    },
    {
        "name": "kiwi_confidence",
        "description": "Xem confidence score các lessons. Lessons noisy (nhiều false positive) tự động bị demote severity.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "lesson_id": {"type": "string", "description": "Specific lesson ID, hoặc bỏ trống để xem overview"},
                "min_fps": {"type": "integer", "default": 3, "description": "Min false positives để hiện (chỉ dùng khi không có lesson_id)"},
            },
        },
    },
    {
        "name": "kiwi_context",
        "description": "DÙNG TRƯỚC KHI CODE. Inject Kiwi knowledge: rules bắt buộc, anti-patterns, code snippets, templates. Giúp code đúng từ đầu, giảm bugs.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "task": {"type": "string", "description": "Mô tả task (e.g. 'loyalty plugin', 'checkout page', 'flash sale')"},
                "scope_type": {"type": "string", "enum": ["plugin", "theme"], "default": "plugin"},
                "platform": {"type": "string", "enum": ["wp", "nextjs"], "default": "wp"},
                "files": {"type": "array", "items": {"type": "string"}, "description": "File types sẽ tạo (e.g. ['Plugin.php', 'admin.js'])"},
                "compact": {"type": "boolean", "default": False, "description": "true = minimal output (id+title only, no code blocks). Saves ~70% tokens."},
                "target_file": {"type": "string", "description": "Path to file being edited — enables smart rule filtering by content signals. Only returns rules relevant to code patterns found in this file."},
            },
        },
    },
    {
        "name": "kiwi_check",
        "description": "Instant single/multi-file scan sau edit. 0 API token. Trả PASS/BLOCK + violations. Dùng sau Write/Edit hoặc để verify fix.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "file": {"type": "string", "description": "Single file path"},
                "files": {"type": "array", "items": {"type": "string"}, "description": "Multiple file paths (batch verify)"},
                "platform": {"type": "string", "enum": ["wp", "nextjs"]},
                "severity": {"type": "string", "enum": ["CRITICAL", "HIGH", "ALL"], "default": "CRITICAL"},
                "compact": {"type": "boolean", "default": True, "description": "true = hide clean files"},
            },
        },
    },
    {
        "name": "kiwi_deploy",
        "description": "Deploy theme/plugin/app to VPS with pre-checks, health verification, and rollback capability. Caches git state to skip redundant scans. Saves 65-75% tokens vs manual deployment.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "Project path or name"},
                "type": {"type": "string", "enum": ["wp_theme", "wp_plugin", "nextjs", "demo_html"], "description": "Deployment type"},
                "target": {"type": "string", "enum": ["staging", "production"], "default": "staging"},
                "mode": {"type": "string", "enum": ["dry-run", "verify", "execute"], "default": "verify", "description": "dry-run = show commands only, verify = pre-checks + show plan, execute = full deploy"},
                "skip_scan": {"type": "boolean", "default": False, "description": "Skip Kiwi scan (use cached result if available)"},
                "rollback_on_fail": {"type": "boolean", "default": True, "description": "Auto-rollback if health checks fail"},
                "remote_path": {"type": "string", "description": "Remote path for demo_html deployment (optional, auto-detected if not provided)"}
            },
            "required": ["path", "type"]
        },
    },
    {
        "name": "kiwi_deploy_history",
        "description": "Query deployment history. Track timestamp, user, target, success/failure, rollback events.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "Filter by project path (optional)"},
                "target": {"type": "string", "enum": ["staging", "production"], "description": "Filter by target environment (optional)"},
                "limit": {"type": "integer", "default": 50, "description": "Max number of deployments to return"}
            }
        },
    },
    {
        "name": "kiwi_impact",
        "description": "Phân tích impact của fix để phòng vệ regression. Tìm files bị ảnh hưởng (callers, importers) và suggest scan. Dùng sau khi fix bug.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "file": {"type": "string", "description": "File vừa fix"},
                "auto_scan": {"type": "boolean", "default": False, "description": "True = tự động scan affected files"},
                "severity": {"type": "string", "enum": ["CRITICAL", "HIGH", "ALL"], "default": "CRITICAL", "description": "Severity level cho auto scan"}
            },
            "required": ["file"]
        },
    },
    {
        "name": "kiwi_mine_patterns",
        "description": "Mine recurring patterns from scan history. Phát hiện patterns lặp lại để tạo lessons mới.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "min_occurrences": {"type": "integer", "default": 5},
                "similarity_threshold": {"type": "number", "default": 0.8},
                "lookback_days": {"type": "integer", "default": 30},
                "path": {"type": "string", "description": "Project path (optional)"}
            },
        },
    },
    {
        "name": "kiwi_learn_from_folder",
        "description": "Scan arbitrary folder → auto-detect bug patterns → create lessons. 10 built-in detectors: hardcoded credentials, SQL injection, XSS, missing nonce, file inclusion, hardcoded URLs, missing error handling, deprecated functions, inefficient loops, missing sanitization.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "Folder to scan and learn from"},
                "min_occurrences": {"type": "integer", "default": 3, "description": "Minimum pattern occurrences to suggest lesson"},
                "auto_approve": {"type": "boolean", "default": False, "description": "If True, auto-create lessons; if False, return suggestions only"},
                "categories": {"type": "array", "items": {"type": "string"}, "description": "Optional: focus on specific categories (security, performance, etc.)"}
            },
            "required": ["path"]
        },
    },
    {
        "name": "kiwi_scan_learn",
        "description": "Scan single file and auto-detect patterns for new lessons. Returns scan report + suggested lessons. Use for code review, pre-commit hooks, or immediate feedback on a single file.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "file": {"type": "string", "description": "File path to scan"},
                "severity": {"type": "string", "enum": ["CRITICAL", "HIGH", "ALL"], "default": "ALL", "description": "Filter violations by severity"}
            },
            "required": ["file"]
        },
    },
    {
        "name": "kiwi_learn_session",
        "description": "Trigger Kiwi learning from Claude session logs. Extracts patterns (styles, bindings, context) that Claude used while coding themes. Run after coding sessions to make Kiwi smarter for next time. 0 LLM token.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "session_id": {"type": "string", "description": "Specific session ID to learn from. Omit to learn from all unprocessed sessions."}
            }
        },
    },
    {
        "name": "kiwi_review_suggestions",
        "description": "Review suggested lessons pending approval. List patterns đã mine để user approve.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "status": {"type": "string", "enum": ["pending", "approved", "rejected"], "default": "pending"}
            }
        },
    },
    {
        "name": "kiwi_approve_suggestion",
        "description": "Approve suggested lesson và generate lesson file. Tạo lesson từ pattern đã mine.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "suggestion_id": {"type": "integer"},
                "severity": {"type": "string", "enum": ["CRITICAL", "HIGH", "SUGGEST"], "description": "Override severity (optional)"},
                "category": {"type": "string", "description": "Override category (optional)"}
            },
            "required": ["suggestion_id"]
        },
    },
    {
        "name": "kiwi_reject_suggestion",
        "description": "Reject suggested lesson. Mark pattern as not useful.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "suggestion_id": {"type": "integer"},
                "reason": {"type": "string"}
            },
            "required": ["suggestion_id", "reason"]
        },
    },
    {
        "name": "kiwi_agent_spawn",
        "description": "Spawn specialized agent (security, performance, architecture, compliance) for parallel execution.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "agent_type": {"type": "string", "enum": ["security", "performance", "architecture", "compliance"], "description": "Agent type to spawn"},
                "path": {"type": "string", "description": "Project path"},
                "mode": {"type": "string", "enum": ["review", "interactive", "auto"], "default": "review"},
                "severity": {"type": "string", "enum": ["CRITICAL", "HIGH", "ALL"], "default": "CRITICAL"},
                "max_fixes": {"type": "integer", "default": 5}
            },
            "required": ["agent_type", "path"]
        },
    },
    {
        "name": "kiwi_agent_sync",
        "description": "Wait for spawned agents to complete and collect results.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "agent_ids": {"type": "array", "items": {"type": "integer"}, "description": "Agent run IDs to wait for"}
            },
            "required": ["agent_ids"]
        },
    },
    {
        "name": "kiwi_agent_consensus",
        "description": "Get consensus verdict from multiple agents on a specific violation.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "lesson_id": {"type": "string", "description": "Lesson ID"},
                "file": {"type": "string", "description": "File path"},
                "line": {"type": "integer", "description": "Line number (optional)"}
            },
            "required": ["lesson_id", "file"]
        },
    },
    {
        "name": "kiwi_session_save",
        "description": "Save current agent session for later resume. Persist session state to disk.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "Project path"},
                "mode": {"type": "string", "enum": ["review", "interactive", "auto"], "default": "review"},
                "severity": {"type": "string", "enum": ["CRITICAL", "HIGH", "ALL"], "default": "CRITICAL"},
                "session_id": {"type": "string", "description": "Optional session ID (auto-generated if not provided)"},
                "state": {"type": "object", "description": "Session state to save (iteration, violations, history, fixes_applied, tokens_used)"}
            },
            "required": ["path", "state"]
        },
    },
    {
        "name": "kiwi_session_resume",
        "description": "Resume saved agent session. Load session state from disk and continue execution.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "session_id": {"type": "string", "description": "Session ID to resume"}
            },
            "required": ["session_id"]
        },
    },
    {
        "name": "kiwi_session_list",
        "description": "List all saved sessions. Show available sessions that can be resumed.",
        "inputSchema": {
            "type": "object",
            "properties": {}
        },
    },
    {
        "name": "kiwi_user_login",
        "description": "User login and authentication. Returns user info and permissions.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "username": {"type": "string", "description": "Username"}
            },
            "required": ["username"]
        },
    },
    {
        "name": "kiwi_team_preferences",
        "description": "Get or set team preferences. Manage shared team settings.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "team_id": {"type": "integer", "description": "Team ID"},
                "action": {"type": "string", "enum": ["get", "set"], "default": "get"},
                "key": {"type": "string", "description": "Preference key (required for action=set)"},
                "value": {"description": "Preference value (required for action=set)"}
            },
            "required": ["team_id"]
        },
    },
    {
        "name": "kiwi_generate_theme",
        "description": "Generate WordPress theme with G0 (Foundation) and G1 (Pages). G0: 16 files (config, tokens, Tailwind, WP bootstrap). G1: 11 files (3 page templates + 8 template-parts). 0 CRITICAL violations guaranteed. Auto-suggests colors/fonts from knowledge base if industry provided.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "theme_name": {"type": "string", "description": "Theme name (e.g., 'My Shop')"},
                "input_spec": {
                    "type": "object",
                    "description": "Theme configuration",
                    "properties": {
                        "shop_name": {"type": "string"},
                        "primary_color": {"type": "string", "description": "Hex color (e.g., '#3b82f6')"},
                        "secondary_color": {"type": "string", "description": "Hex color (e.g., '#8b5cf6')"},
                        "font_family": {"type": "string", "description": "Font stack (e.g., 'Inter, sans-serif')"}
                    },
                    "required": ["shop_name", "primary_color", "secondary_color", "font_family"]
                },
                "industry": {
                    "type": "string",
                    "enum": ["beauty", "tech", "fashion", "food", "furniture", "pharma", "mom-baby", "pet", "b2b", "luxury", "unknown"],
                    "description": "Optional: Target industry for auto-suggestions from knowledge base"
                },
                "phases": {
                    "type": "array",
                    "items": {"type": "string", "enum": ["G0", "G1"]},
                    "default": ["G0", "G1"],
                    "description": "Phases to generate (default: ['G0', 'G1'])"
                },
                "dry_run": {"type": "boolean", "default": False, "description": "Preview without writing files"}
            },
            "required": ["theme_name", "input_spec"]
        },
    },
    {
        "name": "kiwi_generate_from_demo",
        "description": "Generate WordPress theme from demo HTML + DESIGN.md + screenshot. Extract design tokens, detect components, convert to PHP templates. Modes: tokens-only (config files), foundation (config + templates), full (config + G0 + G1).",
        "inputSchema": {
            "type": "object",
            "properties": {
                "demo_path": {"type": "string", "description": "Path to demo folder (contains code.html, DESIGN.md, screen.png)"},
                "theme_name": {"type": "string", "description": "Target theme name (e.g., 'sfvn-institutional')"},
                "mode": {
                    "type": "string",
                    "enum": ["tokens-only", "foundation", "full"],
                    "default": "tokens-only",
                    "description": "Generation mode: tokens-only (config only), foundation (config + templates), full (config + G0 + G1)"
                },
                "confidence_threshold": {
                    "type": "number",
                    "default": 0.7,
                    "description": "Min confidence to auto-apply components (0.0-1.0)"
                },
                "industry": {
                    "type": "string",
                    "enum": ["beauty", "tech", "fashion", "food", "furniture", "pharma", "mom-baby", "pet", "b2b", "luxury", "unknown"],
                    "description": "Target industry for auto-populating knowledge base after generation"
                }
            },
            "required": ["demo_path", "theme_name"]
        },
    },
    {
        "name": "kiwi_feedback",
        "description": "Provide feedback on UI generator output. Collect user acceptance/rejection and corrections to improve pattern detection accuracy. Data feeds into ML classifier retraining.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "gen_id": {"type": "string", "description": "Generation ID from kiwi_generate_from_demo output"},
                "accepted": {"type": "boolean", "description": "True if generation was acceptable, False if needs corrections"},
                "corrections": {"type": "string", "description": "Optional: describe what was wrong or what needed manual fixes"},
                "component_feedback": {
                    "type": "array",
                    "description": "Optional: per-component feedback for fine-grained learning",
                    "items": {
                        "type": "object",
                        "properties": {
                            "component_type": {"type": "string"},
                            "accepted": {"type": "boolean"},
                            "correction": {"type": "string"}
                        },
                        "required": ["component_type", "accepted"]
                    }
                }
            },
            "required": ["gen_id", "accepted"]
        },
    },
    {
        "name": "kiwi_feedback_stats",
        "description": "View UI generator feedback statistics. Shows overall acceptance rate, per-component accuracy, and learning progress.",
        "inputSchema": {
            "type": "object",
            "properties": {},
        },
    },
    {
        "name": "kiwi_mine_ui_patterns",
        "description": "Mine recurring UI component patterns from feedback history. Finds patterns with 3+ occurrences and suggests new Kiwi Templates.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "lookback_days": {"type": "integer", "default": 30, "description": "How far back to look for patterns"},
                "min_occurrences": {"type": "integer", "default": 3, "description": "Minimum pattern occurrences to suggest"}
            },
        },
    },
    {
        "name": "kiwi_confidence_analysis",
        "description": "Analyze component detection accuracy and recommend optimal confidence thresholds. Uses precision/recall/F1 metrics.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "component_type": {"type": "string", "description": "Optional: analyze specific component type, or omit for all components"}
            },
        },
    },
    {
        "name": "kiwi_retrain_classifier",
        "description": "Manually trigger ML classifier retraining with labeled feedback data. Auto-triggers every 10 generations, but can be run manually anytime.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "force": {"type": "boolean", "default": False, "description": "Force retrain even if not at 10-generation threshold"}
            },
        },
    },
    {
        "name": "kiwi_generation_quality",
        "description": "Get generation quality metrics: quality score, fix count, violations at gen, trend (improving/degrading/stable). Tracks how well generated files hold up after post-edit fixes.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "theme_slug": {"type": "string", "description": "Filter by theme slug (optional — omit for all themes)"}
            },
        },
    },
    {
        "name": "kiwi_suggest_base",
        "description": "Suggest best base theme for new project based on learned knowledge. Query theme_knowledge.db by industry, rank by quality + industry match. Fallback to DNA defaults when no data.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "industry": {
                    "type": "string",
                    "enum": ["beauty", "tech", "fashion", "food", "furniture", "pharma", "mom-baby", "pet", "b2b", "luxury", "unknown"],
                    "description": "Target industry"
                },
                "description": {"type": "string", "description": "Brief project description (optional)"}
            },
            "required": ["industry"]
        },
    },
    {
        "name": "kiwi_reason",
        "description": "Context Assembly + Trust Score. Nhận task description + theme path → trả structured brief (files_needed, spec, lessons, bindings, style_patterns) + trust score (0-1) + recommendation (trust/verify_partial/re_research). 0 LLM token, ~50ms. Dùng TRƯỚC khi code để biết cần đọc gì, verify gì.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "task": {"type": "string", "description": "Task description (e.g. 'Tạo trang checkout', 'Fix CSS responsive header')"},
                "theme_path": {"type": "string", "description": "Theme path relative to project root or absolute (e.g. 'themes/sfvn')"},
            },
            "required": ["task", "theme_path"]
        },
    },
    {
        "name": "kiwi_propose_template_patch",
        "description": "Propose auto-patches for Jinja2 templates based on recurring fix patterns in generation history. Analyzes templates with fix_count >= 3 and returns patch candidates with confidence scores. Does NOT apply patches — use kiwi_apply_template_patch to apply.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "template_path": {"type": "string", "description": "Specific template path to analyze (e.g. 'foundation/header.php.j2'). Omit to scan all templates with fix history."},
            },
        },
    },
    {
        "name": "kiwi_apply_template_patch",
        "description": "Apply a proposed template patch through the staging pipeline. Generates a test theme, runs Kiwi scan, and only commits if 0 CRITICAL violations. Auto-reverts if quality score drops > 5%. Rate limit: 1 patch per template per day.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "template_path": {"type": "string", "description": "Template path to patch (same as used in propose)"},
                "dry_run": {"type": "boolean", "default": True, "description": "true = validate only, don't write (default). false = apply + commit."},
            },
            "required": ["template_path"],
        },
    },
]

def _handle_generate_theme(args: dict) -> str:
    """
    Generate WordPress theme with G0 (Foundation) and G1 (Pages).

    Args:
        theme_name: Theme name (e.g., 'My Shop')
        input_spec: Dict with shop_name, primary_color, secondary_color, font_family, etc.
        industry: Optional industry for auto-suggestions from knowledge base
        phases: List of phases to generate (default: ['G0', 'G1'])
        dry_run: Preview without writing files (default: False)

    Returns:
        Generation report with files created and violations

    Example:
        kiwi_generate_theme(
            theme_name="My Shop",
            input_spec={
                "shop_name": "My Shop",
                "primary_color": "#3b82f6",
                "secondary_color": "#8b5cf6",
                "font_family": "Inter, sans-serif"
            },
            industry="tech",
            phases=["G0", "G1"]
        )
    """
    sys.path.insert(0, str(KIWI_DIR))
    from generator.pipelines import NewThemePipeline

    theme_name = args.get("theme_name", "")
    input_spec = args.get("input_spec", {})
    industry = args.get("industry")
    phases = args.get("phases", ["G0", "G1"])
    dry_run = args.get("dry_run", False)

    if not theme_name:
        return "ERROR: theme_name is required"

    if not input_spec:
        return "ERROR: input_spec is required"

    # Auto-suggest from knowledge base if industry provided
    suggestions_note = ""
    base_theme_used = None
    if industry:
        suggestion_result = _handle_suggest_base({"industry": industry})
        try:
            suggestions = json.loads(suggestion_result)
            suggestions_note = f"\n[Knowledge Base Suggestions for {industry}]\n"
            suggestions_note += f"  Base theme: {suggestions.get('base_theme', 'None')}\n"
            suggestions_note += f"  Match score: {suggestions.get('match_score', 0)}\n"
            suggestions_note += f"  Reasoning: {suggestions.get('reasoning', 'N/A')}\n"

            base_theme_used = suggestions.get("base_theme")

            # Apply suggestions if user didn't provide colors/fonts
            if not input_spec.get("primary_color") and suggestions.get("suggested_colors"):
                input_spec["primary_color"] = suggestions["suggested_colors"].get("primary", "#105dad")
            if not input_spec.get("secondary_color") and suggestions.get("suggested_colors"):
                input_spec["secondary_color"] = suggestions["suggested_colors"].get("secondary", "#1e40af")
            if not input_spec.get("font_family") and suggestions.get("suggested_fonts"):
                input_spec["font_family"] = suggestions["suggested_fonts"].get("primary", "Inter, sans-serif")
        except (json.JSONDecodeError, KeyError):
            pass

    # Required fields
    required = ["shop_name", "primary_color", "secondary_color", "font_family"]
    missing = [f for f in required if f not in input_spec]
    if missing:
        return f"ERROR: Missing required fields in input_spec: {', '.join(missing)}"

    try:
        pipeline = NewThemePipeline(dry_run=dry_run, auto_fix=True)
        result = pipeline.run(
            theme_name=theme_name,
            input_spec=input_spec,
            phases=phases,
            industry=industry,
        )

        formatted_report = _format_pipeline_result(result)

        # Auto-populate knowledge base after successful generation
        if not dry_run and report.success and industry:
            try:
                import uuid
                import sqlite3 as _sqlite3
                sys.path.insert(0, str(KIWI_DIR / "tools"))
                from migrate_themes import ThemeMigrator

                theme_slug = theme_name.lower().replace(" ", "-")
                theme_path = Path(os.getcwd()) / "themes" / theme_slug

                migrator = ThemeMigrator()
                result = migrator.migrate_theme(theme_path, industry, dry_run=False)

                # Increment generation_count on base theme if one was used
                if base_theme_used:
                    migrator.conn.execute("""
                        UPDATE themes
                        SET generation_count = generation_count + 1,
                            last_used_at = CURRENT_TIMESTAMP,
                            updated_at = CURRENT_TIMESTAMP
                        WHERE theme_name = ?
                    """, (base_theme_used,))
                    migrator.conn.commit()

                # Record generation in history for feedback linkage
                gen_id = f"gen_{uuid.uuid4().hex[:12]}"
                migrator.conn.execute("""
                    INSERT INTO generation_history (gen_id, theme_name, base_theme, industry)
                    VALUES (?, ?, ?, ?)
                """, (gen_id, theme_slug, base_theme_used, industry))
                migrator.conn.commit()
                migrator.close()

                kb_note = f"\n\n[Knowledge Base] Theme '{theme_slug}' saved (quality: {result['quality_score']}/100)"
                kb_note += f"\n[Knowledge Base] Generation ID: {gen_id}"
                if base_theme_used:
                    kb_note += f"\n[Knowledge Base] Base theme '{base_theme_used}' usage count incremented"
                formatted_report += kb_note
            except Exception as kb_error:
                formatted_report += f"\n\n[Knowledge Base] Warning: Could not save profile: {kb_error}"

        # Prepend suggestions note if available
        if suggestions_note:
            formatted_report = suggestions_note + "\n" + formatted_report

        return formatted_report

    except Exception as e:
        return f"ERROR: Generation failed: {e}"


def _format_pipeline_result(result) -> str:
    """Format PipelineResult into human-readable report."""
    lines = []
    status = "SUCCESS" if result.success else "FAILED"
    lines.append(f"[Generation {status}] Theme: {result.theme_slug}")
    lines.append(f"  Files created: {len(result.files_created)}")
    if result.files_failed:
        lines.append(f"  Files failed: {len(result.files_failed)}")
        for f in result.files_failed[:5]:
            lines.append(f"    - {f.get('file', 'unknown')}: {f.get('template', '')}")
    lines.append(f"  Duration: {result.duration_seconds:.1f}s")
    if result.error:
        lines.append(f"  Error: {result.error}")
    return "\n".join(lines)


def _handle_generate_from_demo(args: dict) -> str:
    """
    Generate WordPress theme from demo HTML + DESIGN.md + screenshot.

    Args:
        demo_path: Path to demo folder (contains code.html, DESIGN.md, screen.png)
        theme_name: Target theme name (e.g., 'sfvn-institutional')
        mode: Generation mode (default: 'tokens-only')
        confidence_threshold: Min confidence to auto-apply components (default: 0.7)

    Returns:
        Generation report with files created, components detected, violations
    """
    sys.path.insert(0, str(KIWI_DIR))
    from generator.pipelines import CloneThemePipeline

    demo_path = args.get("demo_path", "")
    theme_name = args.get("theme_name", "")
    mode = args.get("mode", "tokens-only")
    confidence_threshold = float(args.get("confidence_threshold", 0.7))
    industry = args.get("industry", "unknown")

    if not demo_path:
        return "ERROR: demo_path is required"

    if not theme_name:
        return "ERROR: theme_name is required"

    if mode not in ["tokens-only", "foundation", "full"]:
        return f"ERROR: Invalid mode '{mode}'. Must be: tokens-only, foundation, or full"

    try:
        pipeline = CloneThemePipeline(dry_run=False, auto_fix=True)
        result = pipeline.run(
            demo_path=demo_path,
            theme_name=theme_name,
            mode=mode,
            confidence_threshold=confidence_threshold,
        )
        formatted_report = _format_pipeline_result(result)

        # Auto-populate knowledge base after successful generation
        if result.success and mode != "tokens-only":
            try:
                sys.path.insert(0, str(KIWI_DIR / "tools"))
                from migrate_themes import ThemeMigrator

                theme_slug = theme_name.lower().replace(" ", "-")
                theme_path = Path(os.getcwd()) / "themes" / theme_slug
                industry = args.get("industry", "unknown")

                if theme_path.exists():
                    migrator = ThemeMigrator()
                    result = migrator.migrate_theme(theme_path, industry, dry_run=False)
                    migrator.close()
                    formatted_report += f"\n\n[Knowledge Base] Theme '{theme_slug}' saved (quality: {result['quality_score']}/100)"
            except Exception as kb_error:
                formatted_report += f"\n\n[Knowledge Base] Warning: Could not save profile: {kb_error}"

        return formatted_report

    except Exception as e:
        import traceback
        return f"ERROR: Generation failed: {e}\n{traceback.format_exc()}"


def _handle_feedback(args: dict) -> str:
    """
    Provide feedback on UI generator output.

    Args:
        gen_id: Generation ID from kiwi_generate_from_demo
        accepted: True if acceptable, False if needs corrections
        corrections: Optional description of issues
        component_feedback: Optional per-component feedback

    Returns:
        Confirmation message with updated stats
    """
    sys.path.insert(0, str(KIWI_DIR))
    from memory.db import update_generator_feedback, get_generator_feedback, get_pattern_stats

    gen_id = args.get("gen_id", "")
    accepted = args.get("accepted")
    corrections = args.get("corrections", "")
    component_feedback = args.get("component_feedback", [])

    if not gen_id:
        return "ERROR: gen_id is required"

    if accepted is None:
        return "ERROR: accepted (True/False) is required"

    # Check if generation exists in UI feedback DB
    existing = get_generator_feedback(gen_id=gen_id)

    # Also check generation_history table (from kiwi_generate_theme)
    import sqlite3 as _sqlite3
    kb_db_path = KIWI_DIR / "memory" / "theme_knowledge.db"
    theme_name_from_history = None
    quality_delta = 0

    if kb_db_path.exists():
        try:
            _conn = _sqlite3.connect(kb_db_path)
            row = _conn.execute(
                "SELECT theme_name FROM generation_history WHERE gen_id = ?", (gen_id,)
            ).fetchone()
            if row:
                theme_name_from_history = row[0]

            if theme_name_from_history:
                quality_delta = 5 if accepted else -3
                _conn.execute("""
                    UPDATE themes
                    SET quality_score = MAX(0, MIN(100, quality_score + ?)),
                        updated_at = CURRENT_TIMESTAMP
                    WHERE theme_name = ?
                """, (quality_delta, theme_name_from_history))
                _conn.execute("""
                    UPDATE generation_history
                    SET accepted = ?, quality_delta = ?
                    WHERE gen_id = ?
                """, (1 if accepted else 0, quality_delta, gen_id))
                _conn.commit()
            _conn.close()
        except Exception:
            pass

    if not existing and not theme_name_from_history:
        return f"ERROR: Generation ID '{gen_id}' not found. Use gen_id from kiwi_generate_from_demo or kiwi_generate_theme output."

    # Update UI feedback DB if record exists there
    if existing:
        update_generator_feedback(gen_id, accepted, corrections)

        if component_feedback:
            from memory.db import get_connection, _now
            conn = get_connection()
            for comp in component_feedback:
                conn.execute("""
                    UPDATE component_patterns
                    SET user_accepted = ?, correction = ?
                    WHERE gen_id = ? AND component_type = ?
                """, (comp["accepted"], comp.get("correction", ""), gen_id, comp["component_type"]))
            conn.commit()
            conn.close()

    # Get updated stats
    stats = get_pattern_stats()
    overall = stats["overall"]

    lines = [
        f"Feedback recorded for generation {gen_id}",
        f"",
        f"Status: {'✓ ACCEPTED' if accepted else '✗ REJECTED'}",
    ]

    if corrections:
        lines.append(f"Corrections: {corrections}")

    if theme_name_from_history:
        lines.append(f"")
        lines.append(f"Quality Score Update:")
        lines.append(f"  Theme: {theme_name_from_history}")
        lines.append(f"  Delta: {'+' if quality_delta >= 0 else ''}{quality_delta} points")

    if component_feedback:
        lines.append(f"")
        lines.append(f"Component feedback: {len(component_feedback)} components updated")

    lines.append(f"")
    lines.append(f"Overall Stats:")
    lines.append(f"  Total generations with feedback: {overall.get('total_generations', 0)}")
    lines.append(f"  Accepted: {overall.get('accepted_count', 0)}")
    lines.append(f"  Rejected: {overall.get('rejected_count', 0)}")

    if overall.get('total_generations', 0) > 0:
        acceptance_rate = (overall.get('accepted_count', 0) / overall['total_generations']) * 100
        lines.append(f"  Acceptance rate: {acceptance_rate:.1f}%")

    lines.append(f"")
    lines.append(f"Use kiwi_feedback_stats for detailed per-component accuracy.")

    return "\n".join(lines)


def _handle_feedback_stats(args: dict) -> str:
    """
    View UI generator feedback statistics.

    Returns:
        Detailed stats on acceptance rates and component accuracy
    """
    sys.path.insert(0, str(KIWI_DIR))
    from memory.db import get_pattern_stats

    stats = get_pattern_stats()
    overall = stats["overall"]
    per_component = stats["per_component"]

    lines = [
        f"Kiwi UI Generator V2 — Feedback Statistics",
        f"",
        f"Overall Performance:",
        f"  Total generations: {overall.get('total_generations', 0)}",
        f"  Accepted: {overall.get('accepted_count', 0)}",
        f"  Rejected: {overall.get('rejected_count', 0)}",
    ]

    if overall.get('total_generations', 0) > 0:
        acceptance_rate = (overall.get('accepted_count', 0) / overall['total_generations']) * 100
        lines.append(f"  Acceptance rate: {acceptance_rate:.1f}%")
        lines.append(f"  Avg components detected: {overall.get('avg_detected', 0):.1f}")
        lines.append(f"  Avg components applied: {overall.get('avg_applied', 0):.1f}")

    if per_component:
        lines.append(f"")
        lines.append(f"Per-Component Accuracy:")
        lines.append(f"")
        lines.append(f"{'Component':<20} {'Detected':<10} {'Auto-Applied':<15} {'Accepted':<10} {'Accuracy':<10} {'Avg Conf':<10}")
        lines.append(f"{'-'*20} {'-'*10} {'-'*15} {'-'*10} {'-'*10} {'-'*10}")

        for comp in per_component:
            comp_type = comp["component_type"]
            total = comp["total_detected"]
            auto_applied = comp["auto_applied_count"]
            accepted = comp["accepted_count"]
            accuracy = (accepted / total * 100) if total > 0 else 0
            avg_conf = comp["avg_confidence"]

            lines.append(f"{comp_type:<20} {total:<10} {auto_applied:<15} {accepted:<10} {accuracy:<10.1f}% {avg_conf:<10.2f}")

    lines.append(f"")
    lines.append(f"Learning Progress:")
    lines.append(f"  Target: 200+ labeled examples for ML retraining")
    lines.append(f"  Current: {overall.get('total_generations', 0)} generations")

    if overall.get('total_generations', 0) >= 200:
        lines.append(f"  Status: ✓ Ready for ML classifier retraining")
    else:
        remaining = 200 - overall.get('total_generations', 0)
        lines.append(f"  Status: Need {remaining} more generations")

    return "\n".join(lines)


def _handle_mine_ui_patterns(args: dict) -> str:
    """
    Mine recurring UI component patterns from feedback history.

    Args:
        lookback_days: How far back to look (default: 30)
        min_occurrences: Minimum occurrences to suggest (default: 3)

    Returns:
        Pattern mining report with suggestions
    """
    sys.path.insert(0, str(KIWI_DIR))
    from generator.learning import PatternMiner, format_pattern_report

    lookback_days = int(args.get("lookback_days", 30))
    min_occurrences = int(args.get("min_occurrences", 3))

    try:
        miner = PatternMiner(min_occurrences=min_occurrences)
        patterns = miner.mine_patterns(lookback_days=lookback_days)
        return format_pattern_report(patterns)

    except Exception as e:
        import traceback
        return f"ERROR: Pattern mining failed: {e}\n{traceback.format_exc()}"


def _handle_confidence_analysis(args: dict) -> str:
    """
    Analyze component detection accuracy and recommend thresholds.

    Args:
        component_type: Optional specific component to analyze

    Returns:
        Confidence analysis report with recommended thresholds
    """
    sys.path.insert(0, str(KIWI_DIR))
    from generator.learning import format_confidence_report

    component_type = args.get("component_type")

    try:
        return format_confidence_report(component_type)

    except Exception as e:
        import traceback
        return f"ERROR: Confidence analysis failed: {e}\n{traceback.format_exc()}"


def _handle_generation_quality(args: dict) -> str:
    """Return generation quality metrics for a theme or all themes."""
    sys.path.insert(0, str(KIWI_DIR))
    from memory.db import get_generation_quality, get_high_risk_sections

    theme_slug = args.get("theme_slug")

    try:
        metrics = get_generation_quality(theme_slug=theme_slug)
        high_risk = get_high_risk_sections(theme_slug=theme_slug, top_n=5)

        lines = ["## Generation Quality Report"]
        if theme_slug:
            lines.append(f"Theme: {theme_slug}")
        else:
            lines.append("Scope: all themes")
        lines.append("")
        lines.append(f"Quality score : {metrics['quality_score']:.1%}")
        lines.append(f"Total files   : {metrics['total_files']}")
        lines.append(f"Total fixes   : {metrics['fix_count']}")
        lines.append(f"Violations    : {metrics['violations_at_gen']}")
        lines.append(f"Trend         : {metrics['trend']}")

        if high_risk:
            lines.append("")
            lines.append("### High-risk sections (most post-gen fixes)")
            for r in high_risk:
                lines.append(
                    f"  {r['template_used']}: {r['total_fixes']} fixes, "
                    f"avg quality {r['avg_quality']:.1%} ({r['gen_count']} gens)"
                )

        return "\n".join(lines)

    except Exception as e:
        import traceback
        return f"ERROR: {e}\n{traceback.format_exc()}"


def _handle_retrain_classifier(args: dict) -> str:
    """
    Manually trigger ML classifier retraining.

    Args:
        force: Force retrain even if not at threshold

    Returns:
        Retrain report with model performance metrics
    """
    sys.path.insert(0, str(KIWI_DIR))
    from generator.ml_retrain import MLRetrainer, format_retrain_report

    force = args.get("force", False)

    try:
        retrainer = MLRetrainer()

        if not force:
            should, reason = retrainer.should_retrain()
            if not should:
                return f"ML Classifier Retrain — Skipped\n\n{reason}\n\nUse force=true to retrain anyway."

        report = retrainer.run_retrain()
        return format_retrain_report(report)

    except Exception as e:
        import traceback
        return f"ERROR: Retrain failed: {e}\n{traceback.format_exc()}"


def _handle_suggest_base(args: dict) -> str:
    """
    Suggest best base theme for new project based on learned knowledge.

    Args:
        industry: Target industry (beauty, tech, fashion, food, furniture, pharma, mom-baby, pet, b2b, luxury)
        description: Brief project description (optional)

    Returns:
        JSON with suggested base theme, match score, quality score, design tokens, components, reasoning

    Example:
        kiwi_suggest_base(industry="beauty", description="Luxury skincare shop")
    """
    import json
    import sqlite3

    industry = args.get("industry", "unknown")
    description = args.get("description", "")

    db_path = KIWI_DIR / "memory" / "theme_knowledge.db"

    if not db_path.exists():
        return json.dumps({
            "error": "Knowledge base not initialized. Run theme analyzers first.",
            "base_theme": None
        }, indent=2)

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # Auto-demote stale themes: -1/day for themes unused in 30+ days
    cursor.execute("""
        UPDATE themes
        SET quality_score = MAX(0, quality_score - CAST(
                (julianday('now') - julianday(COALESCE(last_used_at, updated_at))) - 30
            AS INTEGER)),
            updated_at = CURRENT_TIMESTAMP
        WHERE (julianday('now') - julianday(COALESCE(last_used_at, updated_at))) > 30
          AND quality_score > 0
    """)
    conn.commit()

    # First try exact industry match
    cursor.execute("""
        SELECT theme_name, industry, quality_score, tokens,
               components, layout, generation_count
        FROM themes
        WHERE industry = ?
        ORDER BY quality_score DESC, generation_count ASC
        LIMIT 5
    """, (industry,))

    themes = cursor.fetchall()

    # Check if golden_patterns table exists (Phase 2 feature)
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='golden_patterns'")
    has_golden_patterns = cursor.fetchone() is not None

    if has_golden_patterns:
        cursor.execute("SELECT COUNT(*) FROM golden_patterns WHERE auto_apply = 1")
        golden_count = cursor.fetchone()[0]
    else:
        golden_count = 0

    cursor.execute("""
        SELECT AVG(quality_score), COUNT(*)
        FROM themes
        WHERE industry = ?
    """, (industry,))
    industry_stats = cursor.fetchone()
    avg_quality = industry_stats[0] or 0
    theme_count = industry_stats[1]

    conn.close()

    # If no exact match, fallback to DNA defaults
    if not themes or theme_count == 0:
        return json.dumps({
            "base_theme": None,
            "match_score": 0.0,
            "quality_score": 0,
            "suggested_colors": _get_default_colors_for_industry(industry),
            "suggested_fonts": _get_default_fonts_for_industry(industry),
            "suggested_components": {},
            "golden_patterns_available": golden_count,
            "reasoning": f"No {industry} themes in knowledge base yet. Using industry DNA defaults.",
            "recommendation": "Generate first theme for this industry to populate knowledge base"
        }, indent=2)

    best = themes[0]
    theme_slug, theme_industry, quality, tokens_json, components_json, layout, gen_count = best

    tokens = json.loads(tokens_json) if tokens_json else {}
    components = json.loads(components_json) if components_json else {}

    if theme_industry == industry:
        match_score = 1.0
    elif theme_industry == "unknown":
        match_score = 0.3
    else:
        match_score = 0.5

    quality_factor = quality / 100.0
    final_score = match_score * 0.7 + quality_factor * 0.3

    reasoning_parts = []
    if theme_industry == industry:
        reasoning_parts.append(f"Perfect industry match ({industry})")
    else:
        reasoning_parts.append(f"Cross-industry match ({theme_industry} → {industry})")

    reasoning_parts.append(f"quality score {quality:.0f}/100")

    if gen_count > 0:
        reasoning_parts.append(f"proven base ({gen_count} generations)")

    reasoning = ", ".join(reasoning_parts)

    alternatives = []
    for alt in themes[1:3]:
        alt_slug, alt_industry, alt_quality = alt[0], alt[1], alt[2]
        alternatives.append({
            "theme_slug": alt_slug,
            "industry": alt_industry,
            "quality_score": alt_quality,
            "match_score": 1.0 if alt_industry == industry else 0.5
        })

    result = {
        "base_theme": theme_slug,
        "match_score": round(final_score, 2),
        "quality_score": quality,
        "suggested_colors": tokens.get("colors", {}),
        "suggested_fonts": tokens.get("fonts", {}),
        "suggested_components": components,
        "layout_recipe": layout,
        "golden_patterns_available": golden_count,
        "reasoning": reasoning,
        "industry_stats": {
            "avg_quality": round(avg_quality, 1),
            "theme_count": theme_count
        },
        "alternatives": alternatives
    }

    return json.dumps(result, indent=2)


def _get_default_colors_for_industry(industry: str) -> dict:
    """Get default color palette for industry from DNA profiles"""
    defaults = {
        "beauty": {"primary": "#F4E4E4", "secondary": "#E8E0F0", "accent": "#B76E79"},
        "fashion": {"primary": "#1a1a1a", "secondary": "#8b7355", "accent": "#d4af37"},
        "tech": {"primary": "#105dad", "secondary": "#1e40af", "accent": "#3b82f6"},
        "food": {"primary": "#2d5016", "secondary": "#65a30d", "accent": "#84cc16"},
        "furniture": {"primary": "#78350f", "secondary": "#92400e", "accent": "#d97706"},
    }
    return defaults.get(industry, {"primary": "#105dad", "secondary": "#1e40af", "accent": "#3b82f6"})


def _get_default_fonts_for_industry(industry: str) -> dict:
    """Get default font stack for industry from DNA profiles"""
    defaults = {
        "beauty": {"primary": "Playfair Display, serif", "body": "DM Sans, sans-serif"},
        "fashion": {"primary": "Montserrat, sans-serif", "body": "Inter, sans-serif"},
        "tech": {"primary": "Inter, sans-serif", "body": "Inter, sans-serif"},
        "food": {"primary": "Merriweather, serif", "body": "Open Sans, sans-serif"},
        "furniture": {"primary": "Lora, serif", "body": "Nunito, sans-serif"},
    }
    return defaults.get(industry, {"primary": "Inter, sans-serif", "body": "Inter, sans-serif"})


def _handle_reason(args: dict) -> str:
    from agent.reasoning import kiwi_reason
    import json as _json
    task = args.get("task", "")
    theme_path = args.get("theme_path", "")
    if not task or not theme_path:
        return "Error: task and theme_path are required"
    output = kiwi_reason(task, theme_path)
    return _json.dumps({
        "trust_score": round(output.trust_score, 3),
        "recommendation": output.recommendation,
        "verify_hint": output.verify_hint,
        "trust_breakdown": {k: round(v, 2) for k, v in output.trust_breakdown.items()},
        "content": output.content,
    }, ensure_ascii=False, indent=2)


def _handle_metrics(args: dict) -> str:
    import json as _json
    weeks = args.get("weeks", 8)
    fmt = args.get("format", "summary")

    if fmt == "alert":
        from agent.reasoning.alerts import check_stagnation
        alert = check_stagnation()
        return _json.dumps(alert or {'status': 'ok', 'message': 'Kiwi is improving normally'}, indent=2)

    from agent.reasoning.dashboard import generate_dashboard
    from agent.reasoning.alerts import check_stagnation
    dashboard = generate_dashboard(weeks)

    if fmt == "summary":
        return _json.dumps({
            'intelligence_score': dashboard['intelligence_score'],
            'latest_week': dashboard['weekly_trends'][-1] if dashboard['weekly_trends'] else None,
            'autonomy': dashboard['autonomy_progression'],
            'stagnation': check_stagnation(),
        }, indent=2)

    return _json.dumps(dashboard, indent=2)


def _handle_propose_template_patch(args: dict) -> str:
    """Propose auto-patches for templates based on recurring fix patterns."""
    sys.path.insert(0, str(KIWI_DIR))
    from generator.learning.improver import TemplateImprover

    template_path = args.get("template_path")

    try:
        imp = TemplateImprover()

        if template_path:
            patch = imp.propose_patch(template_path)
            if not patch:
                return f"No patch warranted for '{template_path}' (insufficient fix history or rate-limited)."
            patches = [patch]
        else:
            patches = imp.propose_all()
            if not patches:
                return "No patch candidates found. Templates need >= 3 cumulative fixes to qualify."

        lines = [f"## Template Patch Proposals ({len(patches)} candidate(s))", ""]
        for i, p in enumerate(patches, 1):
            lines.append(f"### {i}. {Path(p['template_path']).name}")
            lines.append(f"- Template : {p['template_key']}")
            lines.append(f"- Confidence: {p['confidence']:.1%}")
            lines.append(f"- Summary  : {p['pattern_summary']}")
            if p.get("annotations"):
                lines.append("- Annotations:")
                for ann in p["annotations"]:
                    lines.append(f"    line {ann['line']}: {ann['suggestion']}")
            lines.append("")
            lines.append("```diff")
            lines.append(p["diff"][:800])
            lines.append("```")
            lines.append("")

        lines.append("To apply: `kiwi_apply_template_patch(template_path=..., dry_run=False)`")
        return "\n".join(lines)

    except Exception as e:
        import traceback
        return f"ERROR: {e}\n{traceback.format_exc()}"


def _handle_apply_template_patch(args: dict) -> str:
    """Apply a template patch through the staging pipeline."""
    sys.path.insert(0, str(KIWI_DIR))
    from generator.learning.improver import TemplateImprover

    template_path = args.get("template_path")
    dry_run = args.get("dry_run", True)

    if not template_path:
        return "ERROR: template_path is required."

    try:
        imp = TemplateImprover()
        patch = imp.propose_patch(template_path)

        if not patch:
            return f"No patch candidate for '{template_path}' (insufficient fix history or rate-limited)."

        passed = imp.apply_patch(patch, dry_run=dry_run)

        if dry_run:
            status = "PASSED" if passed else "FAILED"
            return (
                f"Staging {status} for '{template_path}'.\n"
                f"Pattern: {patch['pattern_summary']}\n"
                f"Confidence: {patch['confidence']:.1%}\n"
                + ("Run with dry_run=False to apply." if passed else "Fix violations before applying.")
            )
        else:
            if passed:
                return (
                    f"Patch applied and committed for '{template_path}'.\n"
                    f"Pattern: {patch['pattern_summary']}\n"
                    f"Confidence: {patch['confidence']:.1%}"
                )
            else:
                return (
                    f"Patch REJECTED for '{template_path}' — staging failed or quality regression detected.\n"
                    f"Check logs above for details."
                )

    except Exception as e:
        import traceback
        return f"ERROR: {e}\n{traceback.format_exc()}"


def _handle_tier(args: dict) -> str:
    """View or manage Kiwi tier status."""
    sys.path.insert(0, str(KIWI_DIR))
    from core.tier_manager import get_tier_manager
    from core.tier_config import TIER_LIMITS
    from core.upgrade_prompts import format_tier_status

    mgr = get_tier_manager()
    action = args.get("action", "status")

    if action == "activate":
        key = args.get("key", "")
        tier = args.get("tier", "starter")
        result = mgr.activate_license(key, tier)
        if result["success"]:
            return f"License activated: {result['tier'].upper()} tier"
        return f"Activation failed: {result['error']}"

    tier = mgr.get_current_tier()
    counts = mgr.get_usage_counts()
    return format_tier_status(tier.name, counts, tier.limits)


def _handle_dashboard(args: dict) -> str:
    """View usage stats and cost savings."""
    sys.path.insert(0, str(KIWI_DIR))
    from tracking.dashboard import dashboard
    period = args.get("period", "week")
    detail = args.get("detail", False)
    return dashboard(period=period, detail=detail)


# --- Usage tracking integration ---

_tracker = None


def _get_tracker():
    global _tracker
    if _tracker is None:
        try:
            sys.path.insert(0, str(KIWI_DIR))
            from tracking.usage_tracker import get_tracker
            _tracker = get_tracker()
        except Exception:
            _tracker = None
    return _tracker


def _track_call(tool_name: str, args: dict, latency_ms: int, success: bool):
    tracker = _get_tracker()
    if tracker is None:
        return
    op = tool_name.replace("kiwi_", "")
    target = args.get("path") or args.get("file") or args.get("files", [None])[0] if isinstance(args.get("files"), list) else args.get("path") or args.get("file")
    files_processed = 1
    if "files" in args and isinstance(args["files"], list):
        files_processed = len(args["files"])
    try:
        tracker.record(
            operation=op,
            target_path=target,
            latency_ms=latency_ms,
            files_processed=files_processed,
            success=success,
        )
    except Exception:
        pass


HANDLERS = {
    "kiwi_init": _handle_init,
    "kiwi_scan": _handle_scan,
    "kiwi_query": _handle_query,
    "kiwi_lesson": _handle_lesson,
    "kiwi_add": _handle_add,
    "kiwi_stats": _handle_stats,
    "kiwi_learning_health": _handle_learning_health,
    "kiwi_fix": _handle_fix,
    "kiwi_template": _handle_template,
    "kiwi_agent": _handle_agent,
    "kiwi_dismiss": _handle_dismiss,
    "kiwi_reenable": _handle_reenable,
    "kiwi_detect_anomalies": _handle_detect_anomalies,
    "kiwi_trends": _handle_trends,
    "kiwi_confidence": _handle_confidence,
    "kiwi_context": _handle_context,
    "kiwi_check": _handle_check,
    "kiwi_deploy": _handle_deploy,
    "kiwi_deploy_history": _handle_deploy_history,
    "kiwi_impact": _handle_impact,
    "kiwi_scan_learn": _handle_scan_learn,
    "kiwi_learn_session": _handle_learn_session,
    "kiwi_mine_patterns": _handle_mine_patterns,
    "kiwi_learn_from_folder": _handle_learn_from_folder,
    "kiwi_review_suggestions": _handle_review_suggestions,
    "kiwi_approve_suggestion": _handle_approve_suggestion,
    "kiwi_reject_suggestion": _handle_reject_suggestion,
    "kiwi_agent_spawn": _handle_agent_spawn,
    "kiwi_agent_sync": _handle_agent_sync,
    "kiwi_agent_consensus": _handle_agent_consensus,
    "kiwi_session_save": _handle_session_save,
    "kiwi_session_resume": _handle_session_resume,
    "kiwi_session_list": _handle_session_list,
    "kiwi_user_login": _handle_user_login,
    "kiwi_team_preferences": _handle_team_preferences,
    "kiwi_generate_theme": _handle_generate_theme,
    "kiwi_generate_from_demo": _handle_generate_from_demo,
    "kiwi_feedback": _handle_feedback,
    "kiwi_feedback_stats": _handle_feedback_stats,
    "kiwi_mine_ui_patterns": _handle_mine_ui_patterns,
    "kiwi_confidence_analysis": _handle_confidence_analysis,
    "kiwi_retrain_classifier": _handle_retrain_classifier,
    "kiwi_suggest_base": _handle_suggest_base,
    "kiwi_reason": _handle_reason,
    "kiwi_metrics": _handle_metrics,
    "kiwi_generation_quality": _handle_generation_quality,
    "kiwi_propose_template_patch": _handle_propose_template_patch,
    "kiwi_apply_template_patch": _handle_apply_template_patch,
    "kiwi_dashboard": _handle_dashboard,
    "kiwi_tier": _handle_tier,
}


def _check_tier_gate(tool_name: str):
    """Returns message string if blocked, None if allowed."""
    try:
        sys.path.insert(0, str(KIWI_DIR))
        from core.gating import gate_tool
        result = gate_tool(tool_name)
        if not result.allowed:
            return f"GATED: {result.message}"
    except Exception:
        pass
    return None


def handle_request(req: dict) -> dict:
    method = req.get("method", "")
    req_id = req.get("id")

    if method == "initialize":
        return {
            "jsonrpc": "2.0", "id": req_id,
            "result": {
                "protocolVersion": "2024-11-05",
                "capabilities": {"tools": {}},
                "serverInfo": {"name": "kiwi", "version": "1.0.0"},
            },
        }

    if method == "notifications/initialized":
        return None

    if method == "tools/list":
        return {"jsonrpc": "2.0", "id": req_id, "result": {"tools": TOOL_DEFS}}

    if method == "tools/call":
        tool = req.get("params", {}).get("name", "")
        args = req.get("params", {}).get("arguments", {})
        handler = HANDLERS.get(tool)
        if not handler:
            return {"jsonrpc": "2.0", "id": req_id,
                    "error": {"code": -32602, "message": f"Unknown tool: {tool}"}}
        try:
            gate_result = _check_tier_gate(tool)
            if gate_result:
                return {"jsonrpc": "2.0", "id": req_id,
                        "result": {"content": [{"type": "text", "text": gate_result}]}}
            import time as _time
            _t0 = _time.time()
            text = handler(args)
            _latency = int((_time.time() - _t0) * 1000)
            _track_call(tool, args, _latency, True)
            return {"jsonrpc": "2.0", "id": req_id,
                    "result": {"content": [{"type": "text", "text": text}]}}
        except Exception as e:
            _track_call(tool, args, 0, False)
            return {"jsonrpc": "2.0", "id": req_id,
                    "error": {"code": -32000, "message": str(e)}}

    # Fallback: support direct method calls (e.g., kiwi_scan instead of tools/call)
    # This allows VSCode extension to call methods directly without MCP protocol wrapper
    handler = HANDLERS.get(method)
    if handler:
        try:
            args = req.get("params", {})
            result = handler(args)
            # Return simple result format for direct calls (not MCP content wrapper)
            return {"jsonrpc": "2.0", "id": req_id, "result": result}
        except Exception as e:
            return {"jsonrpc": "2.0", "id": req_id,
                    "error": {"code": -32000, "message": str(e)}}

    return {"jsonrpc": "2.0", "id": req_id,
            "error": {"code": -32601, "message": f"Method not found: {method}"}}


def main():
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            req = json.loads(line)
            resp = handle_request(req)
        except Exception as e:
            resp = {"jsonrpc": "2.0", "id": None,
                    "error": {"code": -32700, "message": f"Parse error: {e}"}}
        if resp is not None:
            print(json.dumps(resp, ensure_ascii=False), flush=True)


if __name__ == "__main__":
    main()