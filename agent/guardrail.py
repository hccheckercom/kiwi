"""Real-time guardrail — instant single-file scan after each edit."""

import os
import re
import sys
from pathlib import Path

KIWI_DIR = Path(__file__).parent.parent

_patterns_cache = {}
_ext_index = {}  # key: ".php" -> list of pattern defs that match this extension


def check_file(
    file_path: str,
    platform: str = None,
    severity: str = "CRITICAL",
) -> dict:
    """Instant scan of a single file against Kiwi patterns.

    Returns:
        Dict with pass/fail status and violations list.
        Zero API tokens — pure local regex matching.
    """
    file_path = os.path.abspath(file_path)
    if not os.path.isfile(file_path):
        return {"pass": True, "file": file_path, "violations": [], "error": "File not found"}

    ext = Path(file_path).suffix.lower()
    if ext not in (".php", ".css", ".js", ".jsx", ".tsx", ".ts", ".json"):
        return {"pass": True, "file": file_path, "violations": [], "skipped": True}

    if not platform:
        platform = _detect_platform(file_path)

    patterns = _get_patterns_for_ext(platform, severity, ext)
    violations = []

    try:
        content = Path(file_path).read_text(encoding="utf-8")
    except (OSError, IOError) as e:
        return {"pass": True, "file": file_path, "violations": [], "error": str(e)}

    lines = content.splitlines()

    for pdef in patterns:
        if not _scope_matches(file_path, pdef.get("scope", "**/*")):
            continue

        if pdef.get("exclude") and _scope_matches(file_path, pdef["exclude"]):
            continue

        ptype = pdef.get("type", "presence")
        if ptype != "presence":
            continue

        try:
            regex = re.compile(pdef["pattern"])
        except re.error:
            continue

        exclude_line_re = None
        if pdef.get("exclude_line"):
            try:
                exclude_line_re = re.compile(pdef["exclude_line"])
            except re.error:
                pass

        for i, line in enumerate(lines):
            match = regex.search(line)
            if match:
                if exclude_line_re and exclude_line_re.search(line):
                    continue

                violations.append({
                    "lesson_id": pdef["id"],
                    "severity": pdef["severity"],
                    "category": pdef["category"],
                    "description": pdef.get("description", ""),
                    "line": i + 1,
                    "match": match.group(0)[:80],
                    "fix_available": bool(pdef.get("fix")),
                })

    passed = not any(v["severity"] == "CRITICAL" for v in violations)

    return {
        "pass": passed,
        "file": file_path,
        "patterns_checked": len(patterns),
        "violations": violations,
        "critical": sum(1 for v in violations if v["severity"] == "CRITICAL"),
        "high": sum(1 for v in violations if v["severity"] == "HIGH"),
    }


def format_result(result: dict) -> str:
    """Format check result into a short string for Claude."""
    if result.get("skipped"):
        return ""

    if result["pass"] and not result["violations"]:
        return ""

    lines = []

    if not result["pass"]:
        lines.append(f"⛔ KIWI BLOCK: {result['critical']} CRITICAL violation(s) in {Path(result['file']).name}")
    elif result["violations"]:
        lines.append(f"⚠ KIWI: {len(result['violations'])} issue(s) in {Path(result['file']).name}")

    for v in result["violations"][:5]:
        fix_tag = " [auto-fix]" if v.get("fix_available") else ""
        lines.append(f"  {v['lesson_id']} [{v['severity']}] L{v['line']}: {v['description']}{fix_tag}")

    if len(result["violations"]) > 5:
        lines.append(f"  ... +{len(result['violations']) - 5} more")

    return "\n".join(lines)


def _get_patterns_for_ext(platform: str, severity: str, ext: str) -> list:
    """Get patterns pre-filtered by file extension. Much faster than checking all."""
    all_patterns = _get_patterns(platform, severity)

    cache_key = f"{platform}:{severity}:{ext}"
    if cache_key in _ext_index:
        return _ext_index[cache_key]

    filtered = []
    for p in all_patterns:
        scope = p.get("scope", "**/*")
        scope_exts = _extract_extensions(scope)
        if not scope_exts or ext in scope_exts:
            filtered.append(p)

    _ext_index[cache_key] = filtered
    return filtered


def _extract_extensions(scope: str) -> set:
    """Extract file extensions from a scope glob pattern."""
    exts = set()
    for part in scope.replace("|", "\n").splitlines():
        part = part.strip()
        if not part:
            continue
        e = Path(part).suffix.lower()
        if e:
            exts.add(e)
    return exts


def _get_patterns(platform: str, severity: str) -> list:
    """Get patterns, cached per platform."""
    cache_key = f"{platform}:{severity}"
    if cache_key in _patterns_cache:
        return _patterns_cache[cache_key]

    sys.path.insert(0, str(KIWI_DIR))
    from scanner.loader import load_patterns

    all_patterns = load_patterns(str(KIWI_DIR / "lessons"), platform=platform)

    if severity == "CRITICAL":
        filtered = [p for p in all_patterns if p["severity"] == "CRITICAL"]
    elif severity == "HIGH":
        filtered = [p for p in all_patterns if p["severity"] in ("CRITICAL", "HIGH")]
    else:
        filtered = all_patterns

    for p in filtered:
        lesson_fm = _get_fix_config(p["id"])
        if lesson_fm:
            p["fix"] = lesson_fm

    _patterns_cache[cache_key] = filtered
    return filtered


def _get_fix_config(lesson_id: str) -> dict:
    """Check if a lesson has a fix config — O(1) via cached index."""
    sys.path.insert(0, str(KIWI_DIR))
    from scanner.loader import get_lesson_frontmatter
    fm, _ = get_lesson_frontmatter(lesson_id, str(KIWI_DIR / "lessons"))
    if fm:
        return fm.get("fix", {})
    return {}


def _scope_matches(file_path: str, scope: str) -> bool:
    """Check if file matches scope glob pattern."""
    from fnmatch import fnmatch

    normalized = file_path.replace("\\", "/")
    filename = Path(file_path).name

    for part in scope.replace("|", "\n").splitlines():
        part = part.strip()
        if not part:
            continue
        if fnmatch(filename, part) or fnmatch(normalized, f"*/{part}"):
            return True
        if "**" in part:
            simple = part.replace("**/", "")
            if fnmatch(filename, simple):
                return True

    return False


def _detect_platform(file_path: str) -> str:
    """Detect platform from file path."""
    normalized = file_path.replace("\\", "/").lower()
    if "/themes/" in normalized or "/wezone-plugins/" in normalized or "/mu-plugins/" in normalized:
        return "wp"
    if "/webstore-vn/" in normalized or "/src/" in normalized:
        ext = Path(file_path).suffix.lower()
        if ext in (".tsx", ".jsx", ".ts"):
            return "nextjs"
    return "wp"