"""Generic scan engine — language-agnostic scan loop.

Delegates checker selection to plugins. Handles:
- Pattern loading (parameterized lessons_dir)
- File scope resolution (configurable excludes)
- Severity filtering
- Diff-only mode
- Cache integration
- False positive dismissal
"""

import os
import sys
from pathlib import Path

_KIWI_DIR = Path(__file__).parent.parent.parent
if str(_KIWI_DIR) not in sys.path:
    sys.path.insert(0, str(_KIWI_DIR))

from scanner.models import Report, Violation
from scanner.loader import load_patterns
from scanner.resolver import resolve_scope, rewrite_scope_for_theme


def scan(path: str,
         plugin=None,
         severity_filter: str = "ALL",
         diff_only: bool = False,
         lessons_dir: str = None,
         platform: str = None,
         scope_type: str = None,
         skip_root_patterns: bool = False,
         rewrite_scopes: bool = False,
         max_per_lesson: int = 0,
         progress_callback=None) -> Report:
    """Run scan using plugin's checkers against a project path.

    Args:
        path: Absolute path to scan target
        plugin: KiwiPlugin instance (provides checkers, excludes)
        severity_filter: CRITICAL, HIGH, SUGGEST, or ALL
        diff_only: Only scan git-modified files
        lessons_dir: Override lessons directory
        platform: Filter lessons by platform
        scope_type: Filter lessons by scope (theme, plugin)
        skip_root_patterns: Skip monorepo-level patterns
        rewrite_scopes: Rewrite scopes for single-theme scan
        max_per_lesson: Cap violations per lesson (0=unlimited)
        progress_callback: fn(processed, total, violations_count)

    Returns:
        Report with violations
    """
    report = Report(theme_path=path)
    path = os.path.abspath(path)

    if lessons_dir is None and plugin:
        lessons_dir = plugin.get_lessons_path()

    patterns = load_patterns(lessons_dir, platform=platform, scope_type=scope_type)
    changed_files = _get_changed_files(path) if diff_only else None

    if plugin:
        checkers = plugin.get_checkers()
    else:
        from scanner.checkers import REGISTRY
        checkers = REGISTRY

    total_patterns = len(patterns)
    patterns_processed = 0

    for pattern_def in patterns:
        if skip_root_patterns and _is_root_level_pattern(pattern_def):
            continue
        if pattern_def.get("severity") == "INFO" and severity_filter != "INFO":
            continue
        if severity_filter != "ALL" and pattern_def["severity"] != severity_filter:
            continue

        report.patterns_checked += 1
        patterns_processed += 1

        if progress_callback and patterns_processed % 10 == 0:
            progress_callback(patterns_processed, total_patterns, len(report.violations))

        scope = pattern_def.get("scope", "**/*")
        exclude = pattern_def.get("exclude")
        if rewrite_scopes:
            scope = rewrite_scope_for_theme(scope)
            if exclude:
                exclude = rewrite_scope_for_theme(exclude)

        files = resolve_scope(path, scope, exclude)
        if not files:
            continue

        if diff_only and changed_files is not None:
            files = [f for f in files if f in changed_files]
            if not files:
                continue

        report.files_scanned += len(files)
        ptype = pattern_def.get("type", "presence")
        checker = checkers.get(ptype)

        if checker:
            violations = checker.check(pattern_def, files, path)
            report.violations.extend(violations)

            if ptype == "ast" and hasattr(checker, "warnings"):
                report.warnings.extend(checker.warnings)
                report.ast_skipped_files += len(checker.warnings)
                checker.warnings = []

    # Filter dismissed false positives
    try:
        from memory.db import is_dismissed
        report.violations = [
            v for v in report.violations
            if not is_dismissed(v.lesson_id, v.file)
        ]
    except Exception:
        pass

    if max_per_lesson > 0:
        report = report.cap_per_lesson(max_per_lesson)

    return report


def scan_multi(root_path: str,
               sub_projects: list,
               plugin=None,
               severity_filter: str = "ALL",
               diff_only: bool = False,
               platform: str = None) -> Report:
    """Scan multiple sub-projects (monorepo or themes folder).

    Args:
        root_path: Monorepo root
        sub_projects: List of (path, scope_type, label) tuples
        plugin: KiwiPlugin instance
        severity_filter: Filter level
        diff_only: Only scan changed files
        platform: Platform filter

    Returns:
        Merged Report
    """
    root_path = os.path.abspath(root_path)
    merged = Report(theme_path=root_path)
    sub_reports = []

    # Root-level patterns
    root_report = scan(
        root_path, plugin=plugin,
        severity_filter=severity_filter, diff_only=diff_only,
        platform=platform, skip_root_patterns=False,
    )
    # Only keep root-level violations
    root_violations = []
    patterns = load_patterns(
        plugin.get_lessons_path() if plugin else None,
        platform=platform
    )
    root_pattern_ids = {p["id"] for p in patterns if _is_root_level_pattern(p)}
    for v in root_report.violations:
        if v.lesson_id in root_pattern_ids:
            root_violations.append(v)
    merged.violations.extend(root_violations)
    merged.files_scanned += root_report.files_scanned

    # Per-sub-project scan
    for sub_path, scope_type, label in sub_projects:
        sub = scan(
            sub_path, plugin=plugin,
            severity_filter=severity_filter, diff_only=diff_only,
            platform=platform, scope_type=scope_type,
            skip_root_patterns=True, rewrite_scopes=True,
        )
        for v in sub.violations:
            v.file = f"{label}/{v.file}" if not v.file.startswith("[") else f"[{label}] {v.file}"

        merged.patterns_checked = max(merged.patterns_checked, sub.patterns_checked)
        merged.files_scanned += sub.files_scanned
        merged.violations.extend(sub.violations)
        sub_reports.append((label, scope_type, sub))

    merged._sub_reports = sub_reports
    return merged


def _is_root_level_pattern(pattern_def: dict) -> bool:
    scope = pattern_def.get("scope", "")
    parts = [s.strip() for s in scope.replace("|", "\n").splitlines() if s.strip()]
    root_prefixes = ("packages/", "shared/", "themes/", "mu-plugins/")
    return all(any(p.startswith(prefix) for prefix in root_prefixes) for p in parts) and bool(parts)


def _get_changed_files(path: str) -> list:
    import subprocess
    try:
        result = subprocess.run(
            ["git", "diff", "--name-only", "HEAD"],
            capture_output=True, text=True, cwd=path, timeout=30,
        )
        staged = subprocess.run(
            ["git", "diff", "--name-only", "--cached"],
            capture_output=True, text=True, cwd=path, timeout=30,
        )
        untracked = subprocess.run(
            ["git", "ls-files", "--others", "--exclude-standard"],
            capture_output=True, text=True, cwd=path, timeout=30,
        )
        all_files = set()
        for output in [result.stdout, staged.stdout, untracked.stdout]:
            for f in output.splitlines():
                if f.strip():
                    full = os.path.join(path, f.strip())
                    if os.path.isfile(full):
                        all_files.add(full)
        return list(all_files)
    except (OSError, subprocess.SubprocessError):
        return []
