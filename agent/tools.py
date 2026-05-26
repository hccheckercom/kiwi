"""Tool definitions for Kiwi Agent — wraps scanner, fixer, file ops."""

import json
import os
import subprocess
import sys
import time
from pathlib import Path

KIWI_DIR = Path(__file__).parent.parent
_scanner_ready = False
_memory_ready = False


def _ensure_scanner():
    global _scanner_ready
    if _scanner_ready:
        return
    sys.path.insert(0, str(KIWI_DIR))
    _scanner_ready = True


def _ensure_memory():
    global _memory_ready
    if _memory_ready:
        return
    _ensure_scanner()
    from memory.db import init_db
    init_db()
    _memory_ready = True


TOOLS = [
    {
        "name": "kiwi_scan",
        "description": "Scan project for bug pattern violations. Returns grouped violations by severity.",
        "input_schema": {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "Project path to scan"},
                "severity": {"type": "string", "enum": ["CRITICAL", "HIGH", "SUGGEST", "ALL"], "default": "ALL"},
                "platform": {"type": "string", "enum": ["wp", "nextjs"]},
                "diff_only": {"type": "boolean", "default": False},
            },
            "required": ["path"],
        },
    },
    {
        "name": "kiwi_fix",
        "description": "Preview or apply auto-fix for a violation. Without apply=true, returns diff preview only.",
        "input_schema": {
            "type": "object",
            "properties": {
                "lesson_id": {"type": "string", "description": "Lesson ID (e.g. LES-392)"},
                "file": {"type": "string", "description": "Path to file with violation"},
                "line": {"type": "integer", "description": "Line number of violation"},
                "apply": {"type": "boolean", "default": False, "description": "true = apply fix, false = dry-run preview"},
            },
            "required": ["lesson_id"],
        },
    },
    {
        "name": "kiwi_lesson",
        "description": "Read full lesson content: Bad/Good code examples, Why explanation, fix details.",
        "input_schema": {
            "type": "object",
            "properties": {
                "id": {"type": "string", "description": "Lesson ID"},
            },
            "required": ["id"],
        },
    },
    {
        "name": "read_file",
        "description": "Read file content with optional line range.",
        "input_schema": {
            "type": "object",
            "properties": {
                "path": {"type": "string"},
                "start_line": {"type": "integer", "description": "1-based start line"},
                "end_line": {"type": "integer", "description": "1-based end line"},
            },
            "required": ["path"],
        },
    },
    {
        "name": "edit_file",
        "description": "Replace exact text in a file. old_text must match exactly.",
        "input_schema": {
            "type": "object",
            "properties": {
                "path": {"type": "string"},
                "old_text": {"type": "string"},
                "new_text": {"type": "string"},
            },
            "required": ["path", "old_text", "new_text"],
        },
    },
    {
        "name": "git_stash",
        "description": "Git stash save/pop for safety backup before batch fixes.",
        "input_schema": {
            "type": "object",
            "properties": {
                "action": {"type": "string", "enum": ["save", "pop"]},
                "message": {"type": "string", "default": "kiwi-agent-backup"},
            },
            "required": ["action"],
        },
    },
    {
        "name": "kiwi_impact",
        "description": "Analyze impact of a fix to find affected files and prevent regressions. Run after applying a fix.",
        "input_schema": {
            "type": "object",
            "properties": {
                "file": {"type": "string", "description": "File that was just fixed"},
                "auto_scan": {"type": "boolean", "default": False, "description": "Auto-scan affected files for regressions"},
            },
            "required": ["file"],
        },
    },
]


def execute_tool(name: str, args: dict, state) -> str:
    try:
        if name == "kiwi_scan":
            return _exec_scan(args, state)
        elif name == "kiwi_fix":
            return _exec_fix(args, state)
        elif name == "kiwi_lesson":
            return _exec_lesson(args)
        elif name == "read_file":
            return _exec_read(args)
        elif name == "edit_file":
            return _exec_edit(args, state)
        elif name == "git_stash":
            return _exec_stash(args, state)
        elif name == "kiwi_impact":
            return _exec_impact(args, state)
        else:
            return f"Unknown tool: {name}"
    except Exception as e:
        return f"Tool error ({name}): {e}"


def _exec_scan(args: dict, state) -> str:
    _ensure_scanner()
    _ensure_memory()
    from scanner.cli import scan_theme, scan_monorepo, _detect_project_type, _find_theme_root
    from memory.db import is_dismissed, log_scan
    from memory.confidence import update_hit

    path = os.path.abspath(args["path"])
    if not os.path.isdir(path):
        return f"ERROR: Directory not found: {path}"

    severity = args.get("severity", "ALL")
    platform = args.get("platform")
    diff_only = args.get("diff_only", False)

    project_type = _detect_project_type(path)
    if project_type not in ("monorepo", "themes_folder"):
        path = _find_theme_root(path)

    start_time = time.time()

    if project_type == "monorepo":
        report = scan_monorepo(path, severity_filter=severity, diff_only=diff_only, platform=platform)
    else:
        effective_scope = project_type if project_type in ("theme", "plugin") else None
        skip_empty = project_type in ("unknown", "plugin")
        report = scan_theme(
            path, severity_filter=severity, diff_only=diff_only,
            platform=platform, scope_type=effective_scope,
            skip_empty_scope=skip_empty,
            rewrite_scopes=(project_type == "theme"),
        )

    duration_ms = int((time.time() - start_time) * 1000)

    report = report.cap_per_lesson(5)

    filtered = []
    for v in report.violations:
        if is_dismissed(v.lesson_id, v.file, v.line):
            continue
        filtered.append(v)
        update_hit(v.lesson_id, is_true_positive=True)
    report.violations = filtered

    log_scan(
        path=path, platform=platform, severity=severity, mode=state.mode,
        violations_total=len(report.violations),
        violations_critical=report.critical_count,
        violations_high=report.high_count,
        violations_suggest=report.suggest_count,
        patterns_checked=report.patterns_checked,
        files_scanned=report.files_scanned,
        duration_ms=duration_ms,
        agent_iterations=state.scan_count,
    )

    state.violations_found = len(report.violations)
    state.violations_remaining = len(report.violations)

    grouped = report.grouped()
    lines = [
        f"Scan: {path}",
        f"Patterns: {report.patterns_checked} | Files: {report.files_scanned}",
        f"CRITICAL: {report.critical_count} | HIGH: {report.high_count} | SUGGEST: {report.suggest_count}",
        "",
    ]

    for sev in ["CRITICAL", "HIGH", "SUGGEST"]:
        sev_lessons = {lid: vs for lid, vs in grouped.items() if vs[0].severity == sev}
        if not sev_lessons:
            continue
        lines.append(f"{sev} ({sum(len(v) for v in sev_lessons.values())}):")
        for lid, vs in sorted(sev_lessons.items()):
            lines.append(f"  {lid} [{vs[0].category}] {vs[0].description} ({len(vs)} hits)")
            for v in vs[:3]:
                lines.append(f"    {v.file}:{v.line}  {v.match_text[:80]}")
            if len(vs) > 3:
                lines.append(f"    ... +{len(vs)-3} more")
        lines.append("")

    if not report.violations:
        lines.append("No violations found.")

    state.log("scan", f"{len(report.violations)} violations ({report.critical_count} CRITICAL)")
    return "\n".join(lines)


def _exec_fix(args: dict, state) -> str:
    _ensure_scanner()
    _ensure_memory()
    from scanner.cli import get_fix_for_lesson
    from scanner.fixer import apply_fix
    from scanner.models import Violation
    from memory.db import log_fix
    from memory.confidence import record_fix_outcome

    lesson_id = args["lesson_id"]
    file_path = args.get("file")
    line = int(args.get("line", 0))
    do_apply = args.get("apply", False)

    lessons_dir = str(KIWI_DIR / "lessons")

    fm, body = _load_lesson(lesson_id)
    if fm is None:
        return f"Lesson {lesson_id} not found."

    fix_config = fm.get("fix")

    if fix_config and file_path:
        violation = Violation(
            lesson_id=lesson_id,
            severity=fm.get("severity", "HIGH"),
            category=fm.get("category", ""),
            description=fm.get("title", ""),
            file=file_path,
            line=line,
        )
        result = apply_fix(violation, fix_config, dry_run=not do_apply)

        if result.success:
            action = "Applied" if do_apply else "Preview"
            if do_apply:
                state.fixes_applied += 1
                state.violations_remaining = max(0, state.violations_remaining - 1)
                state.log("fix", f"{lesson_id} in {file_path}:{line}")
                log_fix(lesson_id, file_path, result.fix_type, diff_preview=result.diff)
                record_fix_outcome(lesson_id, success=True)
            return f"{action} fix for {lesson_id} ({result.fix_type}):\n```diff\n{result.diff}```"
        elif result.error:
            state.fixes_failed += 1
            state.log("fix_failed", f"{lesson_id}: {result.error}")
            record_fix_outcome(lesson_id, success=False)
            good = get_fix_for_lesson(lesson_id, lessons_dir)
            msg = f"Auto-fix failed: {result.error}"
            if good:
                msg += f"\n\nFallback — Good example:\n```\n{good}\n```"
            return msg

    lines = [f"Fix info for {lesson_id}: {fm.get('title', '')}"]
    if fix_config:
        lines.append(f"Auto-fix type: {fix_config.get('type', '')}")
        if fix_config.get("type") == "llm":
            lines.append(f"LLM prompt: {fix_config.get('prompt', '')}")
        else:
            lines.append("Pass file + line + apply=true to apply.")

    good = get_fix_for_lesson(lesson_id, lessons_dir)
    if good:
        lines.append(f"\nGood example:\n```\n{good}\n```")
    return "\n".join(lines)


def _exec_lesson(args: dict) -> str:
    import re as re_mod
    lesson_id = args["id"]
    fm, body = _load_lesson(lesson_id)
    if fm is None:
        return f"Lesson {lesson_id} not found."

    lines = [
        f"# {lesson_id} [{fm.get('severity','')}] [{fm.get('category','')}]",
        f"**{fm.get('title', '')}**", "",
    ]
    scan = fm.get("scan", {})
    if scan:
        lines.append(f"Type: {scan.get('type','')} | Pattern: `{scan.get('pattern','')}`")
        lines.append(f"Scope: `{scan.get('scope','')}`")
        lines.append("")
    fix = fm.get("fix", {})
    if fix:
        lines.append(f"Fix: type={fix.get('type','')} search=`{fix.get('search','')}`")
        lines.append("")
    lines.append(body or "")
    return "\n".join(lines)


def _exec_read(args: dict) -> str:
    fp = Path(args["path"])
    if not fp.is_file():
        return f"File not found: {fp}"

    try:
        content = fp.read_text(encoding="utf-8")
    except Exception as e:
        return f"Read error: {e}"

    file_lines = content.splitlines()
    start = int(args.get("start_line", 1))
    end = int(args.get("end_line", len(file_lines)))
    start = max(1, start)
    end = min(len(file_lines), end)

    result = []
    for i in range(start - 1, end):
        result.append(f"{i+1:4d} | {file_lines[i]}")
    return "\n".join(result)


def _exec_edit(args: dict, state) -> str:
    fp = Path(args["path"])
    if not fp.is_file():
        return f"File not found: {fp}"

    old_text = args["old_text"]
    new_text = args["new_text"]

    try:
        content = fp.read_text(encoding="utf-8")
    except Exception as e:
        return f"Read error: {e}"

    if old_text not in content:
        return f"old_text not found in {fp}. Make sure it matches exactly (whitespace matters)."

    count = content.count(old_text)
    if count > 1:
        return f"old_text found {count} times — ambiguous. Provide more context to make it unique."

    new_content = content.replace(old_text, new_text, 1)
    fp.write_text(new_content, encoding="utf-8")

    state.fixes_applied += 1
    state.violations_remaining = max(0, state.violations_remaining - 1)
    state.log("edit", f"{fp}")
    return f"Edited {fp} — replaced {len(old_text)} chars with {len(new_text)} chars."


def _exec_stash(args: dict, state) -> str:
    action = args["action"]
    cwd = state.path

    if action == "save":
        msg = args.get("message", "kiwi-agent-backup")
        result = subprocess.run(
            ["git", "stash", "push", "-m", msg],
            capture_output=True, text=True, cwd=cwd, timeout=30,
        )
        if result.returncode == 0:
            state.stashed = True
            state.log("stash_save", msg)
            return f"Stashed: {result.stdout.strip()}"
        return f"Stash failed: {result.stderr.strip()}"

    elif action == "pop":
        result = subprocess.run(
            ["git", "stash", "pop"],
            capture_output=True, text=True, cwd=cwd, timeout=30,
        )
        if result.returncode == 0:
            state.stashed = False
            state.log("stash_pop", "")
            return f"Popped: {result.stdout.strip()}"
        return f"Pop failed: {result.stderr.strip()}"

    return f"Unknown stash action: {action}"


def _exec_impact(args: dict, state) -> str:
    """Execute impact analysis on a fixed file."""
    _ensure_scanner()
    from scanner.impact import ImpactAnalyzer
    from scanner.cli import scan_theme

    file_path = args["file"]
    auto_scan = args.get("auto_scan", False)

    if not os.path.isfile(file_path):
        return f"ERROR: File not found: {file_path}"

    # Detect project root
    project_root = os.path.dirname(os.path.abspath(file_path))
    while project_root != os.path.dirname(project_root):
        if os.path.isdir(os.path.join(project_root, ".git")):
            break
        project_root = os.path.dirname(project_root)

    analyzer = ImpactAnalyzer(project_root)
    report = analyzer.analyze_fix_impact(file_path)

    lines = [
        f"📊 IMPACT ANALYSIS: {os.path.basename(file_path)}",
        f"Symbols changed: {', '.join(report.symbols_changed) if report.symbols_changed else 'none detected'}",
        ""
    ]

    if not report.affected_files:
        lines.append("✅ No affected files detected — impact likely minimal")
        state.log("impact", f"{os.path.basename(file_path)}: no affected files")
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

    lines.append("💡 SUGGESTIONS")
    for i, suggestion in enumerate(report.suggestions, 1):
        lines.append(f"  {i}. {suggestion}")

    # Log impact
    state.log("impact", f"{os.path.basename(file_path)}: {len(report.affected_files)} affected, risk={report.risk_level}")

    # Auto-scan if requested
    if auto_scan and (high_risk or medium_risk):
        lines.append("")
        lines.append("[auto_scan=True] Running scans on affected files...")

        regressions_found = 0
        for af in high_risk + medium_risk:
            try:
                scan_report = scan_theme(af.path, severity_filter="CRITICAL", skip_empty_scope=True)
                rel_path = os.path.relpath(af.path, project_root)

                if scan_report.critical_count > 0:
                    lines.append(f"  ⛔ {rel_path} — BLOCK ({scan_report.critical_count} CRITICAL)")
                    for v in scan_report.violations[:3]:
                        lines.append(f"     L{v.line}: {v.lesson_id} {v.title}")
                    regressions_found += scan_report.critical_count
                elif scan_report.high_count > 0:
                    lines.append(f"  ⚠ {rel_path} — {scan_report.high_count} HIGH")
                else:
                    lines.append(f"  ✅ {rel_path} — PASS")
            except Exception as e:
                lines.append(f"  ❌ {os.path.relpath(af.path, project_root)} — scan failed: {e}")

        if regressions_found > 0:
            state.regressions_detected += regressions_found
            state.log("regression", f"{regressions_found} violations in affected files")

    return "\n".join(lines)


def _load_lesson(lesson_id: str) -> tuple:
    _ensure_scanner()
    from scanner.loader import get_lesson_frontmatter
    return get_lesson_frontmatter(lesson_id, str(KIWI_DIR / "lessons"))