"""Convert Kiwi lessons to Semgrep rules."""

from typing import Dict, Optional, List


def lesson_to_semgrep_rule(lesson: dict) -> Optional[dict]:
    """Convert Kiwi lesson to Semgrep rule YAML.

    Returns None if pattern not convertible (e.g., BOM check).
    """
    scan = lesson.get("scan", {})
    scan_type = scan.get("type", "presence")

    # BOM check is byte-level, not AST-based
    if scan_type == "bom-check":
        return None

    # Check if lesson already has Semgrep pattern (type must be "semgrep")
    if scan_type == "semgrep" and ("pattern" in scan or "patterns" in scan):
        return {
            "id": lesson["id"],
            "pattern": scan.get("pattern"),
            "patterns": scan.get("patterns"),
            "languages": scan.get("languages", ["php"]),
            "severity": _map_severity(lesson.get("severity", "HIGH")),
            "message": lesson.get("title", "")
        }

    # Convert from regex pattern
    if scan_type == "presence":
        return _convert_presence(lesson)
    elif scan_type == "absence":
        return _convert_absence(lesson)
    elif scan_type in ("cross-check", "cross_check"):
        return _convert_cross_check(lesson)
    else:
        # Unknown type, cannot convert
        return None


def _convert_presence(lesson: dict) -> Optional[dict]:
    """Convert presence pattern to Semgrep.

    Presence: pattern SHOULD NOT exist.
    """
    scan = lesson.get("scan", {})
    pattern = scan.get("pattern", "")

    # Try to convert simple function calls
    semgrep_pattern = _regex_to_semgrep(pattern)

    if semgrep_pattern is None:
        return None

    rule = {
        "id": lesson["id"],
        "pattern": semgrep_pattern,
        "languages": ["php"],
        "severity": _map_severity(lesson.get("severity", "HIGH")),
        "message": lesson.get("title", "")
    }

    # Add context guard if present
    context_guard = scan.get("context_guard")
    if context_guard:
        guard_pattern = context_guard.get("pattern", "")
        guard_semgrep = _regex_to_semgrep(guard_pattern)
        if guard_semgrep:
            rule["patterns"] = [
                {"pattern": semgrep_pattern},
                {"pattern-not-inside": guard_semgrep}
            ]
            del rule["pattern"]

    return rule


def _convert_absence(lesson: dict) -> Optional[dict]:
    """Convert absence pattern to Semgrep.

    Absence: pattern SHOULD exist but doesn't.
    This is tricky in Semgrep - we need to invert the logic.
    """
    # Absence patterns are hard to convert to Semgrep
    # because Semgrep finds what matches, not what's missing.
    # For now, return None (use regex fallback)
    return None


def _convert_cross_check(lesson: dict) -> Optional[dict]:
    """Convert cross-check pattern to Semgrep.

    Cross-check: pattern exists but cross_check pattern doesn't.
    """
    scan = lesson.get("scan", {})
    pattern = scan.get("pattern", "")
    cross_check = scan.get("cross_check", "")

    # Convert both patterns
    main_pattern = _regex_to_semgrep(pattern)
    guard_pattern = _regex_to_semgrep(cross_check)

    if main_pattern is None:
        return None

    rule = {
        "id": lesson["id"],
        "languages": ["php"],
        "severity": _map_severity(lesson.get("severity", "HIGH")),
        "message": lesson.get("title", "")
    }

    if guard_pattern:
        # Use pattern-not-inside for cross-check
        rule["patterns"] = [
            {"pattern": main_pattern},
            {"pattern-not-inside": f"{guard_pattern}"}
        ]
    else:
        # No guard pattern, just use main pattern
        rule["pattern"] = main_pattern

    return rule


def _regex_to_semgrep(regex: str) -> Optional[str]:
    """Convert regex pattern to Semgrep pattern.

    Returns None if pattern cannot be converted.
    """
    # Method call with \s*\(: $wpdb->query\s*\( → $wpdb->query(...)
    if "->" in regex and r"\s*\(" in regex:
        parts = regex.split(r"\s*\(")
        if len(parts) >= 2:
            method_part = parts[0].replace("\\", "")
            return f"{method_part}(...)"

    # Simple function call: wp_mail\s*\( → wp_mail(...)
    if r"\s*\(" in regex:
        func_name = regex.split(r"\s*\(")[0].replace("\\", "")
        return f"{func_name}(...)"

    # Variable access: $_GET\[|$_POST\[|$_REQUEST\[ → $_GET[...]
    if r"\[" in regex and ("$_GET" in regex or "$_POST" in regex or "$_REQUEST" in regex):
        var_name = regex.split(r"\[")[0].replace("\\", "")
        return f"{var_name}[...]"

    # define() call: define\s*\( → define(...)
    if "define" in regex and r"\s*\(" in regex:
        return "define(...)"

    # register_rest_route: register_rest_route → register_rest_route(...)
    if "register_rest_route" in regex:
        return "register_rest_route(...)"

    # Simple pattern without special regex chars → use as-is
    # This handles absence patterns like "wp_verify_nonce"
    if not any(c in regex for c in r"\[](){}.*+?^$|"):
        return regex

    # Cannot convert complex regex
    return None


def _map_severity(kiwi_severity: str) -> str:
    """Map Kiwi severity to Semgrep severity."""
    mapping = {
        "CRITICAL": "ERROR",
        "HIGH": "WARNING",
        "SUGGEST": "INFO",
        "MEDIUM": "WARNING",
        "INFO": "INFO"
    }
    return mapping.get(kiwi_severity, "WARNING")


def convert_lesson_file(lesson_path: str, dry_run: bool = True) -> dict:
    """Convert a lesson file to include Semgrep patterns.

    Returns dict with:
    - success: bool
    - rule: dict (Semgrep rule) or None
    - error: str or None
    """
    from pathlib import Path
    import yaml

    try:
        content = Path(lesson_path).read_text(encoding="utf-8")
    except (OSError, IOError) as e:
        return {"success": False, "rule": None, "error": str(e)}

    # Parse frontmatter
    if not content.startswith("---"):
        return {"success": False, "rule": None, "error": "No frontmatter"}

    end = content.find("\n---", 3)
    if end == -1:
        return {"success": False, "rule": None, "error": "Invalid frontmatter"}

    fm_text = content[3:end]
    body = content[end + 4:]

    try:
        lesson = yaml.safe_load(fm_text)
    except yaml.YAMLError as e:
        return {"success": False, "rule": None, "error": f"YAML error: {e}"}

    # Convert to Semgrep rule
    rule = lesson_to_semgrep_rule(lesson)

    if rule is None:
        return {
            "success": False,
            "rule": None,
            "error": "Pattern not convertible to Semgrep"
        }

    # Update lesson frontmatter
    scan = lesson.get("scan", {})

    # Save original pattern as fallback
    if "pattern" in scan:
        scan["regex_fallback"] = scan["pattern"]
    if "cross_check" in scan:
        scan["cross_check_fallback"] = scan["cross_check"]

    # Add Semgrep fields
    scan["type"] = "semgrep"
    if "pattern" in rule:
        scan["pattern"] = rule["pattern"]
    if "patterns" in rule:
        scan["patterns"] = rule["patterns"]
    scan["languages"] = rule["languages"]

    lesson["scan"] = scan

    # Write back if not dry run
    if not dry_run:
        new_fm = yaml.dump(lesson, default_flow_style=False, allow_unicode=True)
        new_content = f"---\n{new_fm}---\n{body}"
        Path(lesson_path).write_text(new_content, encoding="utf-8")

    return {"success": True, "rule": rule, "error": None}
