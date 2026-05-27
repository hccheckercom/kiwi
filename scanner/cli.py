#!/usr/bin/env python3
"""Kiwi Scanner v3 — CLI entry point."""

import argparse
import json
import os
import re
import subprocess
import sys
from pathlib import Path

from .models import Report
from .loader import load_patterns
from .resolver import resolve_scope, rewrite_scope_for_theme
from .checkers import get_checker
from .reporters import get_reporter


_META_PATH = Path(__file__).parent.parent / "_meta.json"


def get_changed_files(theme_path: str) -> list:
    """Get files changed in git working tree."""
    try:
        result = subprocess.run(
            ["git", "diff", "--name-only", "HEAD"],
            capture_output=True, text=True, cwd=theme_path, timeout=30,
        )
        staged = subprocess.run(
            ["git", "diff", "--name-only", "--cached"],
            capture_output=True, text=True, cwd=theme_path, timeout=30,
        )
        untracked = subprocess.run(
            ["git", "ls-files", "--others", "--exclude-standard"],
            capture_output=True, text=True, cwd=theme_path, timeout=30,
        )
        all_files = set()
        for output in [result.stdout, staged.stdout, untracked.stdout]:
            for f in output.splitlines():
                if f.strip():
                    full = os.path.join(theme_path, f.strip())
                    if os.path.isfile(full):
                        all_files.add(full)
        return list(all_files)
    except (OSError, subprocess.SubprocessError):
        return []


def get_fix_for_lesson(lesson_id: str, lessons_dir: str = None) -> str:
    """Extract the Good section from a lesson file as a suggested fix."""
    from .loader import get_lesson_path

    if lessons_dir is None:
        lessons_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "lessons")

    path = get_lesson_path(lesson_id, lessons_dir)
    if not path:
        return ""

    try:
        content = Path(path).read_text(encoding="utf-8")
    except (OSError, IOError):
        return ""

    good_match = re.search(r"## Good\s*\n```\w*\n(.*?)```", content, re.DOTALL)
    if good_match:
        code = good_match.group(1).strip()
        if code and "TODO" not in code:
            return code
    return ""


def _find_theme_root(path: str) -> str:
    """Walk subdirectories to find the actual theme root (has style.css or functions.php).

    Returns the theme root path if found, otherwise returns the original path.
    Searches up to 2 levels deep.
    """
    p = Path(path)
    if (p / "style.css").is_file() or (p / "functions.php").is_file():
        return path

    for child in sorted(p.iterdir()):
        if not child.is_dir() or child.name.startswith(".") or child.name.startswith("_"):
            continue
        if (child / "style.css").is_file() or (child / "functions.php").is_file():
            return str(child)
        for grandchild in sorted(child.iterdir()):
            if not grandchild.is_dir() or grandchild.name.startswith(".") or grandchild.name.startswith("_"):
                continue
            if (grandchild / "style.css").is_file() or (grandchild / "functions.php").is_file():
                return str(grandchild)

    return path


def _detect_project_type(path: str) -> str:
    """Detect project type from directory structure.

    Returns: 'monorepo', 'themes_folder', 'theme', 'plugin', or 'unknown'.
    """
    p = Path(path)
    has_packages = (p / "packages").is_dir()
    has_themes = (p / "themes").is_dir()
    has_shared = (p / "shared").is_dir()

    if has_packages or (has_themes and has_shared):
        return "monorepo"

    if (p / "style.css").is_file() or (p / "functions.php").is_file():
        return "theme"

    if any(p.glob("*.php")):
        return "plugin"

    if (p / "pyproject.toml").is_file() or (p / "requirements.txt").is_file() or (p / "setup.py").is_file():
        return "python"

    # Detect a flat folder of themes (e.g. D:\projects\wezone\themes)
    # Check up to 2 levels deep for style.css or functions.php
    def _has_theme_child(directory: Path, depth: int = 2) -> bool:
        if depth == 0:
            return False
        for d in directory.iterdir():
            if not d.is_dir() or d.name.startswith(".") or d.name.startswith("_"):
                continue
            if (d / "style.css").is_file() or (d / "functions.php").is_file():
                return True
            if depth > 1 and _has_theme_child(d, depth - 1):
                return True
        return False

    if _has_theme_child(p):
        return "themes_folder"

    return "unknown"


def _discover_sub_projects(root: str) -> list:
    """Discover scannable sub-projects in a monorepo or themes_folder.

    Returns list of (path, scope_type, label) tuples.
    """
    root_path = Path(root)
    projects = []

    packages_dir = root_path / "packages"
    if packages_dir.is_dir():
        for pkg in sorted(packages_dir.iterdir()):
            if not pkg.is_dir():
                continue
            if pkg.name.startswith(".disabled-"):
                continue
            if pkg.name.startswith("_"):
                continue
            projects.append((str(pkg), "plugin", f"packages/{pkg.name}"))

    shared_dir = root_path / "shared"
    if shared_dir.is_dir():
        projects.append((str(shared_dir), "plugin", "shared"))

    themes_dir = root_path / "themes"
    if themes_dir.is_dir():
        for theme in sorted(themes_dir.iterdir()):
            if not theme.is_dir():
                continue
            if theme.name.startswith(".") or theme.name.startswith("_") or theme.name.startswith("00-"):
                continue
            projects.append((str(theme), "theme", f"themes/{theme.name}"))

    mu_dir = root_path / "mu-plugins"
    if mu_dir.is_dir():
        projects.append((str(mu_dir), "plugin", "mu-plugins"))

    return projects


def _discover_themes_in_folder(root: str) -> list:
    """Discover all theme sub-directories in a flat themes folder (up to 2 levels deep).

    Returns list of (path, scope_type, label) tuples.
    """
    root_path = Path(root)
    projects = []
    for d in sorted(root_path.iterdir()):
        if not d.is_dir() or d.name.startswith(".") or d.name.startswith("_"):
            continue
        if (d / "style.css").is_file() or (d / "functions.php").is_file():
            projects.append((str(d), "theme", d.name))
        else:
            # Check one level deeper (e.g. themes/furniture-homelife/wezone-haven/)
            for sub in sorted(d.iterdir()):
                if not sub.is_dir() or sub.name.startswith(".") or sub.name.startswith("_"):
                    continue
                if (sub / "style.css").is_file() or (sub / "functions.php").is_file():
                    projects.append((str(sub), "theme", f"{d.name}/{sub.name}"))
    return projects


def scan_theme(theme_path: str, severity_filter: str = "ALL",
               diff_only: bool = False, lessons_dir: str = None,
               platform: str = None, scope_type: str = None,
               skip_root_patterns: bool = False,
               rewrite_scopes: bool = False,
               skip_empty_scope: bool = False,
               use_cache: bool = False,
               use_semgrep: bool = False,
               progress_callback=None) -> Report:
    """Run all patterns against theme."""
    report = Report(theme_path=theme_path)
    theme_path = os.path.abspath(theme_path)

    patterns = load_patterns(lessons_dir, platform=platform, scope_type=scope_type)
    changed_files = get_changed_files(theme_path) if diff_only else None

    # Initialize cache if enabled
    git_commit = None
    patterns_version = None
    cache_available = False
    cache_is_empty = True
    if use_cache:
        try:
            from . import cache as cache_module
            cache_module.init_cache_db()
            git_commit = cache_module._get_git_commit_hash(theme_path)
            patterns_version = cache_module._get_patterns_version(lessons_dir)
            cache_is_empty = cache_module.is_cache_empty()
            cache_available = True
        except (ImportError, Exception):
            cache_available = False

    total_patterns = len(patterns)
    print(f"Scanning {os.path.basename(theme_path)}...", flush=True)
    print(f"Checking {total_patterns} patterns...", flush=True)

    # Collect ALL unique files across ALL patterns BEFORE scanning
    all_unique_files = set()
    if cache_available and not cache_is_empty:
        for pattern_def in patterns:
            if skip_root_patterns and _is_root_level_pattern(pattern_def):
                continue
            if pattern_def.get("severity") == "INFO" and severity_filter != "INFO":
                continue
            if severity_filter != "ALL" and pattern_def["severity"] != severity_filter:
                continue

            scope = pattern_def.get("scope", "**/*")
            exclude = pattern_def.get("exclude")
            if rewrite_scopes:
                scope = rewrite_scope_for_theme(scope)
                if exclude:
                    exclude = rewrite_scope_for_theme(exclude)
            files = resolve_scope(theme_path, scope, exclude)

            if diff_only and changed_files is not None:
                files = [f for f in files if f in changed_files]

            all_unique_files.update(files)

    # Single batch query for ALL files at once (O(1) query)
    all_files_cache = {}
    if cache_available and not cache_is_empty and all_unique_files:
        from . import cache as cache_module
        print(f"Loading cache for {len(all_unique_files)} files...", flush=True)
        all_files_cache = cache_module.get_cached_violations_batch(
            list(all_unique_files),
            patterns_version,
            git_commit  # Pass git commit for fast-path optimization
        )
        cache_hits = sum(1 for v in all_files_cache.values() if v is not None)
        print(f"Cache: {cache_hits} hits, {len(all_unique_files) - cache_hits} misses", flush=True)

    # Track violations to cache after scan
    files_to_cache = {}  # file_path -> list of violations

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

        # Progress output every 10 patterns
        if patterns_processed % 10 == 0:
            print(f"  [{patterns_processed}/{total_patterns}] Checked {patterns_processed} patterns, {len(report.violations)} violations found", flush=True)
            if progress_callback:
                progress_callback(patterns_processed, total_patterns, len(report.violations))
        scope = pattern_def.get("scope", "**/*")
        exclude = pattern_def.get("exclude")
        if rewrite_scopes:
            scope = rewrite_scope_for_theme(scope)
            if exclude:
                exclude = rewrite_scope_for_theme(exclude)
        files = resolve_scope(theme_path, scope, exclude)

        if not files and skip_empty_scope:
            continue

        if diff_only and changed_files is not None:
            files = [f for f in files if f in changed_files]
            if not files:
                continue

        report.files_scanned += len(files)
        ptype = pattern_def.get("type", "presence")
        checker = get_checker(ptype, use_semgrep=use_semgrep)

        if checker:
            # Use pre-loaded cache (already queried once at start)
            if cache_available and not cache_is_empty and all_files_cache:
                from .models import Violation

                cached_violations = []
                files_to_scan = []

                for file_path in files:
                    cached = all_files_cache.get(file_path)

                    if cached is not None:
                        # Cache hit - use cached violations
                        for v_dict in cached:
                            cached_violations.append(Violation(
                                lesson_id=v_dict["lesson_id"],
                                severity=v_dict["severity"],
                                category=v_dict["category"],
                                description=v_dict["description"],
                                file=v_dict["file"],
                                line=v_dict["line"],
                                match_text=v_dict.get("match_text", ""),
                            ))
                    else:
                        # Cache miss - need to scan
                        files_to_scan.append(file_path)

                # Scan uncached files
                if files_to_scan:
                    new_violations = checker.check(pattern_def, files_to_scan, theme_path)

                    # Track violations for batch caching
                    for v in new_violations:
                        file_key = v.file if os.path.isabs(v.file) else os.path.join(theme_path, v.file)
                        if file_key not in files_to_cache:
                            files_to_cache[file_key] = []
                        files_to_cache[file_key].append(v)

                    report.violations.extend(new_violations)

                # Add cached violations
                report.violations.extend(cached_violations)
            else:
                # No cache - scan all files
                report.violations.extend(checker.check(pattern_def, files, theme_path))

            # Collect AST warnings if this is an AST checker
            if ptype == "ast" and hasattr(checker, 'warnings'):
                report.warnings.extend(checker.warnings)
                report.ast_skipped_files += len(checker.warnings)
                checker.warnings = []  # Reset for next pattern

    # Batch cache write AFTER all patterns scanned
    if cache_available and files_to_cache:
        from . import cache as cache_module
        cache_module.cache_violations_batch(files_to_cache, git_commit, patterns_version)

    return report


def _is_root_level_pattern(pattern_def: dict) -> bool:
    """Check if a pattern's scope references monorepo-level paths."""
    scope = pattern_def.get("scope", "")
    # Multi-scope: check each part
    parts = [s.strip() for s in scope.replace("|", "\n").splitlines() if s.strip()]
    root_prefixes = ("packages/", "shared/", "themes/", "mu-plugins/")
    return all(any(p.startswith(prefix) for prefix in root_prefixes) for p in parts) and bool(parts)


def scan_monorepo(root_path: str, severity_filter: str = "ALL",
                  diff_only: bool = False, lessons_dir: str = None,
                  platform: str = None, use_semgrep: bool = False) -> Report:
    """Scan a monorepo by scanning each sub-project independently.

    Root-level patterns (scope starts with packages/, shared/) are run
    against the full monorepo root. Per-package patterns are run against
    each sub-project with appropriate scope_type filtering.
    """
    root_path = os.path.abspath(root_path)
    projects = _discover_sub_projects(root_path)

    merged = Report(theme_path=root_path)
    sub_reports = []

    # Pass 1: Root-level patterns (scope references packages/*, shared/*, etc.)
    root_report = _scan_root_level(root_path, severity_filter, diff_only, lessons_dir, platform, use_semgrep)
    merged.files_scanned += root_report.files_scanned
    merged.violations.extend(root_report.violations)

    # Pass 2: Per-package scan with scope_type filtering
    for sub_path, scope_type, label in projects:
        sub = scan_theme(
            sub_path,
            severity_filter=severity_filter,
            diff_only=diff_only,
            lessons_dir=lessons_dir,
            platform=platform,
            scope_type=scope_type,
            skip_root_patterns=True,
            use_semgrep=use_semgrep,
        )
        # Prefix violation paths with sub-project label
        for v in sub.violations:
            v.file = f"{label}/{v.file}" if not v.file.startswith("[") else f"[{label}] {v.file}"

        merged.patterns_checked = max(merged.patterns_checked, sub.patterns_checked)
        merged.files_scanned += sub.files_scanned
        merged.violations.extend(sub.violations)
        sub_reports.append((label, scope_type, sub))

    merged._sub_reports = sub_reports
    return merged


def _scan_root_level(root_path: str, severity_filter: str, diff_only: bool,
                     lessons_dir: str, platform: str, use_semgrep: bool = False) -> Report:
    """Run only root-level patterns against the full monorepo."""
    report = Report(theme_path=root_path)
    patterns = load_patterns(lessons_dir, platform=platform)
    changed_files = get_changed_files(root_path) if diff_only else None

    for pattern_def in patterns:
        if not _is_root_level_pattern(pattern_def):
            continue
        if pattern_def.get("severity") == "INFO" and severity_filter != "INFO":
            continue
        if severity_filter != "ALL" and pattern_def["severity"] != severity_filter:
            continue

        report.patterns_checked += 1
        files = resolve_scope(root_path, pattern_def.get("scope", "**/*"),
                              pattern_def.get("exclude"))

        if diff_only and changed_files is not None:
            files = [f for f in files if f in changed_files]
            if not files:
                continue

        report.files_scanned += len(files)
        ptype = pattern_def.get("type", "presence")
        checker = get_checker(ptype, use_semgrep=use_semgrep)

        if checker:
            report.violations.extend(checker.check(pattern_def, files, root_path))

    return report


def _resolve_project_path(project_name: str):
    """Resolve project name from _meta.json."""
    if not _META_PATH.exists():
        return None
    try:
        meta = json.loads(_META_PATH.read_text(encoding="utf-8"))
        projects = meta.get("projects", {})
        return projects.get(project_name)
    except (json.JSONDecodeError, OSError):
        return None


def _lint_lessons(lessons_dir=None):
    """Validate all lesson configs, print warnings, exit with error count."""
    from .loader import _parse_frontmatter, _validate_pattern
    if lessons_dir is None:
        lessons_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "lessons")
    lessons_path = Path(lessons_dir)
    total, errors = 0, 0
    for md_file in sorted(lessons_path.rglob("*.md")):
        if md_file.name == "README.md":
            continue
        try:
            content = md_file.read_text(encoding="utf-8")
        except (OSError, IOError):
            continue
        fm = _parse_frontmatter(content)
        if not fm or "scan" not in fm:
            continue
        scan = fm["scan"]
        if not isinstance(scan, dict):
            continue
        total += 1
        warnings = _validate_pattern(fm, scan, str(md_file))
        for w in warnings:
            print(f"  ERROR: {w}")
            errors += 1
    status = "PASS" if errors == 0 else "FAIL"
    print(f"\nLint: {total} lessons checked, {errors} errors — {status}")


def main():
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

    parser = argparse.ArgumentParser(description="Kiwi Smart Scanner v2")
    parser.add_argument("--theme", help="Path to theme/plugin directory")
    parser.add_argument("--project", help="Project name from _meta.json or path to monorepo root")
    parser.add_argument("--severity", default="ALL", choices=["CRITICAL", "HIGH", "SUGGEST", "ALL"])
    parser.add_argument("--json", action="store_true", dest="json_mode", help="JSON output")
    parser.add_argument("--diff-only", action="store_true", help="Only scan git-changed files")
    parser.add_argument("--fix", action="store_true", help="Show suggested fix from lesson Good section")
    parser.add_argument("--lessons", default=None, help="Path to lessons/ directory (auto-detected)")
    parser.add_argument("--platform", default=None, choices=["wp", "nextjs", "python"], help="Filter lessons by platform (wp, nextjs, or python)")
    parser.add_argument("--scope", default=None, choices=["theme", "plugin"], help="Filter lessons by scope_type (theme or plugin)")
    parser.add_argument("--max-per-lesson", type=int, default=0, help="Cap violations per lesson (0=unlimited)")
    parser.add_argument("--group", action="store_true", help="Group output by lesson ID")
    parser.add_argument("--compact", action="store_true", help="Hide lessons with 0 file matches (reduce noise)")
    parser.add_argument("--quiet", action="store_true", help="Minimal output: only summary line")
    parser.add_argument("--lint", action="store_true", help="Validate all lesson configs and exit")
    parser.add_argument("--impact", help="Analyze impact of fix on this file (finds affected files)")
    parser.add_argument("--auto-scan", action="store_true", help="Auto-scan affected files (use with --impact)")
    parser.add_argument("--learn", action="store_true", help="Auto-detect patterns and suggest lessons")
    parser.add_argument("--strict", action="store_true", help="Exit with code 1 if AST warnings present (for CI/CD)")
    parser.add_argument("--use-semgrep", action="store_true", help="Use Semgrep for AST-based pattern matching (experimental)")
    parser.add_argument("--use-regex", action="store_true", help="Force regex-based matching (disable Semgrep)")

    args = parser.parse_args()

    if args.lint:
        _lint_lessons(args.lessons)
        sys.exit(0)

    # Handle --impact mode
    if args.impact:
        from .impact import ImpactAnalyzer

        if not os.path.isfile(args.impact):
            print(f"ERROR: File not found: {args.impact}", file=sys.stderr)
            sys.exit(2)

        # Detect project root
        project_root = os.path.dirname(os.path.abspath(args.impact))
        while project_root != os.path.dirname(project_root):
            if os.path.isdir(os.path.join(project_root, ".git")):
                break
            project_root = os.path.dirname(project_root)

        analyzer = ImpactAnalyzer(project_root)
        report = analyzer.analyze_fix_impact(args.impact)

        print(f"📊 IMPACT ANALYSIS: {os.path.basename(args.impact)}")
        print(f"Symbols changed: {', '.join(report.symbols_changed) if report.symbols_changed else 'none detected'}")
        print()

        if not report.affected_files:
            print("✅ No affected files detected — impact likely minimal")
            sys.exit(0)

        # Group by risk
        high_risk = [f for f in report.affected_files if f.risk == "HIGH"]
        medium_risk = [f for f in report.affected_files if f.risk == "MEDIUM"]
        low_risk = [f for f in report.affected_files if f.risk == "LOW"]

        if high_risk:
            print(f"🔴 HIGH RISK ({len(high_risk)} files)")
            for af in high_risk[:5]:
                rel_path = os.path.relpath(af.path, project_root)
                print(f"  - {rel_path}")
                print(f"    {af.reason}")
                if af.line_numbers:
                    line_preview = ', '.join(str(ln) for ln in sorted(af.line_numbers)[:5])
                    print(f"    Lines: {line_preview}")
            print()

        if medium_risk:
            print(f"🟡 MEDIUM RISK ({len(medium_risk)} files)")
            for af in medium_risk[:5]:
                rel_path = os.path.relpath(af.path, project_root)
                print(f"  - {rel_path}")
                print(f"    {af.reason}")
            print()

        if low_risk:
            print(f"🟢 LOW RISK ({len(low_risk)} files)")
            for af in low_risk[:3]:
                rel_path = os.path.relpath(af.path, project_root)
                print(f"  - {rel_path}: {af.reason}")
            print()

        print("💡 SUGGESTIONS")
        for i, suggestion in enumerate(report.suggestions, 1):
            print(f"  {i}. {suggestion}")

        # Auto-scan if requested
        if args.auto_scan and (high_risk or medium_risk):
            print()
            print(f"[auto_scan] Running scans (severity={args.severity})...")
            use_semgrep = args.use_semgrep and not args.use_regex

            for af in high_risk + medium_risk:
                try:
                    scan_report = scan_theme(af.path, severity_filter=args.severity, skip_empty_scope=True, use_semgrep=use_semgrep)
                    rel_path = os.path.relpath(af.path, project_root)

                    if scan_report.critical_count > 0:
                        print(f"  ⛔ {rel_path} — BLOCK ({scan_report.critical_count} CRITICAL)")
                        for v in scan_report.violations[:3]:
                            print(f"     L{v.line}: {v.lesson_id} {v.title}")
                    elif scan_report.high_count > 0:
                        print(f"  ⚠ {rel_path} — {scan_report.high_count} HIGH")
                    else:
                        print(f"  ✅ {rel_path} — PASS")
                except Exception as e:
                    print(f"  ❌ {os.path.relpath(af.path, project_root)} — scan failed: {e}")

        sys.exit(0)

    target_path = args.theme
    is_monorepo = False

    if args.project:
        if os.path.isdir(args.project):
            target_path = args.project
        else:
            resolved = _resolve_project_path(args.project)
            if resolved and os.path.isdir(resolved):
                target_path = resolved
            else:
                print(f"ERROR: Project '{args.project}' not found", file=sys.stderr)
                sys.exit(2)

    if not target_path:
        print("ERROR: Specify --theme <path> or --project <name>", file=sys.stderr)
        sys.exit(2)

    if not os.path.isdir(target_path):
        print(f"ERROR: Directory not found: {target_path}", file=sys.stderr)
        sys.exit(2)

    # Auto-resolve to theme root if user passed a wrapper folder
    resolved_root = _find_theme_root(target_path)
    if resolved_root != target_path:
        print(f"  Auto-resolved theme root: {os.path.relpath(resolved_root, target_path)}", file=sys.stderr)
        target_path = resolved_root

    project_type = _detect_project_type(target_path)
    if project_type == "monorepo" and not args.scope:
        is_monorepo = True

    # Auto-detect scope_type from project_type when not explicitly set
    effective_scope = args.scope
    if not effective_scope and project_type in ("theme", "plugin"):
        effective_scope = project_type

    if project_type == "themes_folder" and not args.scope:
        themes = _discover_themes_in_folder(target_path)
        if not themes:
            print("ERROR: No themes found in folder (no style.css or functions.php)", file=sys.stderr)
            sys.exit(2)
        merged = Report(theme_path=target_path)
        sub_reports = []
        use_semgrep = args.use_semgrep and not args.use_regex
        for sub_path, scope_type, label in themes:
            sub = scan_theme(
                sub_path,
                severity_filter=args.severity,
                diff_only=args.diff_only,
                lessons_dir=args.lessons,
                platform=args.platform,
                scope_type=scope_type,
                skip_root_patterns=True,
                rewrite_scopes=True,
                use_semgrep=use_semgrep,
            )
            for v in sub.violations:
                v.file = f"{label}/{v.file}" if not v.file.startswith("[") else f"[{label}] {v.file}"
            merged.patterns_checked = max(merged.patterns_checked, sub.patterns_checked)
            merged.files_scanned += sub.files_scanned
            merged.violations.extend(sub.violations)
            sub_reports.append((label, scope_type, sub))
        merged._sub_reports = sub_reports
        report = merged
    elif is_monorepo:
        use_semgrep = args.use_semgrep and not args.use_regex
        report = scan_monorepo(
            target_path,
            severity_filter=args.severity,
            diff_only=args.diff_only,
            lessons_dir=args.lessons,
            platform=args.platform,
            use_semgrep=use_semgrep,
        )
    else:
        # Enable skip_empty_scope for plugin/unknown — these are often subfolders
        # where absence patterns (scope resolves to 0 files) are false positives.
        # Only themes need strict absence checks (missing templates = real bugs).
        # --compact flag also enables skip_empty_scope.
        should_skip_empty = project_type in ("unknown", "plugin") or args.compact

        # Determine use_semgrep flag
        use_semgrep = args.use_semgrep and not args.use_regex

        report = scan_theme(
            target_path,
            severity_filter=args.severity,
            diff_only=args.diff_only,
            lessons_dir=args.lessons,
            platform=args.platform,
            scope_type=effective_scope,
            skip_empty_scope=should_skip_empty,
            rewrite_scopes=(project_type == "theme"),
            use_semgrep=use_semgrep,
        )

    # Apply --max-per-lesson cap
    if args.max_per_lesson > 0:
        report = report.cap_per_lesson(args.max_per_lesson)

    if args.fix and report.violations:
        lessons_dir = args.lessons or os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "lessons"
        )
        seen_ids = set()
        lines = []
        lines.append("=" * 60)
        lines.append("  KIWI — Suggested Fixes")
        lines.append("=" * 60)
        for v in report.violations:
            if v.lesson_id in seen_ids:
                continue
            fix = get_fix_for_lesson(v.lesson_id, lessons_dir)
            if fix:
                seen_ids.add(v.lesson_id)
                lines.append(f"\n[{v.lesson_id}] {v.description}")
                lines.append(f"  File: {v.file}:{v.line}")
                lines.append(f"  Fix:")
                for fix_line in fix.split("\n"):
                    lines.append(f"    {fix_line}")
        if seen_ids:
            lines.append("\n" + "=" * 60)
            print("\n".join(lines))
        else:
            print("No fixes available for detected violations.")
    elif args.quiet:
        c, h, s = report.critical_count, report.high_count, report.suggest_count
        total = len(report.violations)
        print(f"KIWI: {total} violations ({c} CRITICAL, {h} HIGH, {s} SUGGEST) | {report.files_scanned} files | {report.patterns_checked} patterns")
        if report.critical_count > 0:
            for v in report.violations:
                if v.severity == "CRITICAL":
                    loc = f"{v.file}:{v.line}" if v.line else v.file
                    print(f"  [{v.lesson_id}] {loc} — {v.description}")
    else:
        reporter = get_reporter("json" if args.json_mode else "text")
        output = reporter.format(report, grouped=args.group)
        print(output)

    # Handle --learn mode
    if args.learn and report.violations:
        try:
            # Add kiwi root to path for learning module import
            kiwi_root = Path(__file__).parent.parent
            if str(kiwi_root) not in sys.path:
                sys.path.insert(0, str(kiwi_root))

            # Import after path is set
            import learning.single_file as single_file_module
            extract_patterns_from_file = single_file_module.extract_patterns_from_file

            # Group violations by file
            files_with_violations = {}
            for v in report.violations:
                if v.file not in files_with_violations:
                    files_with_violations[v.file] = []
                files_with_violations[v.file].append({
                    'lesson_id': v.lesson_id,
                    'line': v.line,
                    'match_text': v.match_text,
                    'severity': v.severity
                })

            # Extract patterns from each file
            all_suggestions = []
            for file_path, violations in files_with_violations.items():
                # Convert relative path to absolute
                abs_path = file_path if os.path.isabs(file_path) else os.path.join(target_path, file_path)
                if os.path.isfile(abs_path):
                    suggestions = extract_patterns_from_file(abs_path, violations)
                    all_suggestions.extend(suggestions)

            # Print suggestions
            if all_suggestions:
                print("\n" + "="*60)
                print("  KIWI — Suggested Lessons")
                print("="*60)
                for i, sug in enumerate(all_suggestions, 1):
                    print(f"\n[{i}] {Path(sug.example_file).name} (confidence: {sug.confidence:.2f})")
                    print(f"  Category: {sug.category} | Severity: {sug.severity}")
                    print(f"  Pattern: {sug.pattern[:80]}..." if len(sug.pattern) > 80 else f"  Pattern: {sug.pattern}")
                    print(f"  Example: {sug.example_file}:{sug.example_line}")
                print("\nReview: kiwi_review_suggestions()")
                print("Approve: kiwi_approve_suggestion(id)")
        except Exception as e:
            print(f"\nWarning: Learning mode failed: {e}", file=sys.stderr)

    # Exit with code 1 if CRITICAL violations found, or if --strict mode and AST warnings present
    exit_code = 1 if report.critical_count > 0 or (args.strict and report.warnings) else 0
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
