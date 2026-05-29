"""Load patterns from lessons/**/*.md frontmatter using PyYAML."""

import os
import sys
import time
from pathlib import Path

import yaml


_VALID_SCAN_TYPES = {"presence", "absence", "cross_check", "cross-check", "ast", "pattern", "block", "manual", "bom-check", "none", "pattern_presence", "responsive_coverage", "dark_coverage", "sibling_consistency", "class_conflict", "semgrep"}
_VALID_SEVERITIES = {"CRITICAL", "HIGH", "SUGGEST", "MEDIUM", "INFO"}
_VALID_FIX_TYPES = {"replace", "template", "llm", "wrap", "delete"}

# --- Caching layer ---
_patterns_cache = {}          # key: (lessons_dir, platform, scope_type) -> list
_lesson_index = {}            # key: lesson_id -> absolute file path
_lesson_fm_cache = {}         # key: lesson_id -> (frontmatter_dict, body_str)
_cache_mtime = 0              # mtime of lessons dir when cache was built
_CACHE_TTL = 300              # 5 minutes


def invalidate_cache():
    """Clear all caches. Call after adding/removing lessons."""
    global _patterns_cache, _lesson_index, _lesson_fm_cache, _cache_mtime
    _patterns_cache = {}
    _lesson_index = {}
    _lesson_fm_cache = {}
    _cache_mtime = 0


def _parse_frontmatter(content: str) -> dict:
    """Extract YAML frontmatter from markdown content."""
    if not content.startswith("---"):
        return {}

    parts = content.split("---", 2)
    if len(parts) < 3:
        return {}

    try:
        return yaml.safe_load(parts[1]) or {}
    except yaml.YAMLError:
        return {}


def _validate_pattern(fm: dict, scan: dict, file_path: str) -> list:
    """Validate pattern configuration and return warnings."""
    warnings = []

    # Check scan type
    scan_type = scan.get("type", "presence")
    if scan_type not in _VALID_SCAN_TYPES:
        warnings.append(f"{fm.get('id', '?')}: unknown scan type '{scan_type}'")

    # Check severity
    severity = fm.get("severity", "HIGH")
    if severity not in _VALID_SEVERITIES:
        warnings.append(f"{fm.get('id', '?')}: unknown severity '{severity}'")

    # Check fix type if present
    if "fix" in scan and "type" in scan["fix"]:
        fix_type = scan["fix"]["type"]
        if fix_type not in _VALID_FIX_TYPES:
            warnings.append(f"{fm.get('id', '?')}: unknown fix type '{fix_type}'")

    return warnings


def _matches_platform(fm: dict, category: str, platform: str) -> bool:
    """Check if lesson matches platform filter."""
    lesson_platform = fm.get("platform", "")

    # "both" matches everything
    if lesson_platform == "both":
        return True

    # Exact match
    if lesson_platform == platform:
        return True

    # Category-based platform inference
    platform_categories = {
        "wp": ["php-security", "wezone-api", "db-schema"],
        "nextjs": ["nextjs-react", "ai-safety"]
    }

    if category in platform_categories.get(platform, []):
        return True

    return False


def _matches_stack(fm: dict, caps: set) -> bool:
    """Check if a lesson is applicable given the project's capabilities.

    `requires:` — load only if the project HAS that capability.
    `conflicts:` — skip if the project HAS that capability.
    Both accept a string or a list. Lessons without either field are universal
    and always load (preserves pre-filter behaviour).
    """
    def _as_set(val):
        if not val:
            return set()
        if isinstance(val, str):
            return {val}
        if isinstance(val, (list, tuple, set)):
            return {str(v) for v in val}
        return set()

    requires = _as_set(fm.get("requires"))
    if requires and not (requires & caps):
        return False  # needs a capability the project does not have

    conflicts = _as_set(fm.get("conflicts"))
    if conflicts and (conflicts & caps):
        return False  # conflicts with a capability the project has

    return True


def _matches_scope_type(fm: dict, scope_type: str) -> bool:
    """Check if lesson matches scope_type filter (theme/plugin)."""
    tags = fm.get("tags", [])

    # "both" matches everything
    if "both" in tags:
        return True

    # Exact match
    if scope_type in tags:
        return True

    return False


def get_lesson_path(lesson_id: str) -> str:
    """Get absolute path for a lesson ID. Returns empty string if not found."""
    if not _lesson_index:
        # Build index if empty
        load_patterns()

    return _lesson_index.get(lesson_id, "")


def get_lesson_content(lesson_id: str) -> tuple:
    """Get (frontmatter_dict, body_str) for a lesson ID.

    Returns (None, None) if lesson not found.
    Caches results for performance.
    """
    if lesson_id in _lesson_fm_cache:
        return _lesson_fm_cache[lesson_id]

    lesson_path = get_lesson_path(lesson_id)
    if not lesson_path:
        return (None, None)

    try:
        with open(lesson_path, "r", encoding="utf-8") as f:
            content = f.read()
    except (OSError, IOError):
        return (None, None)

    fm = _parse_frontmatter(content)
    if not fm:
        return (None, None)

    # Extract body (everything after second ---)
    parts = content.split("---", 2)
    body = parts[2].strip() if len(parts) >= 3 else ""

    result = (fm, body)
    _lesson_fm_cache[lesson_id] = result
    return result


def get_lesson_body(lesson_id: str) -> str:
    """Get lesson body (markdown content after frontmatter).

    Returns empty string if lesson not found.
    """
    _, body = get_lesson_content(lesson_id)
    return body or ""


def get_lesson_frontmatter(lesson_id: str, lessons_dir: str = None) -> tuple:
    """Get lesson frontmatter + body.

    Returns (frontmatter_dict, body_str). Both default to empty if lesson not found.
    Accepts optional lessons_dir for callers that load from a custom path; the
    underlying get_lesson_content already resolves the default lessons dir.
    """
    fm, body = get_lesson_content(lesson_id)
    return (fm or {}, body or "")


def load_patterns(lessons_dir: str = None, platform: str = None, scope_type: str = None, include_disabled: bool = False, project_path: str = None) -> list:
    """Load all patterns from lessons/**/*.md frontmatter scan: blocks.

    Results are cached per (lessons_dir, platform, scope_type, caps) combination.
    Call invalidate_cache() to force reload.

    Args:
        lessons_dir: Path to lessons directory
        platform: Filter by platform (wp, nextjs, both)
        scope_type: Filter by scope (theme, plugin, both)
        include_disabled: If False, filter out disabled lessons (default: False)
        project_path: Project root. When set, lessons are filtered by their
            `requires:`/`conflicts:` frontmatter against the project's detected
            stack (e.g. a WooCommerce project drops Wezone-only lessons). When
            None (default), no stack filtering — preserves legacy behaviour.
    """
    global _cache_mtime

    if lessons_dir is None:
        lessons_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "lessons")

    # Resolve project capabilities once (None = filtering disabled)
    caps = None
    if project_path:
        try:
            from .project_profile import detect_stack
            caps = detect_stack(project_path)
        except Exception as e:
            print(f"[kiwi] stack detection error: {e}", file=sys.stderr)
            caps = None

    caps_key = "all" if caps is None else ",".join(sorted(caps)) or "none"
    key = (lessons_dir, platform or "", scope_type or "", include_disabled, caps_key)
    if key in _patterns_cache and _cache_mtime and (time.time() - _cache_mtime) < _CACHE_TTL:
        return _patterns_cache[key]

    patterns = []
    lessons_path = Path(lessons_dir)

    if not lessons_path.exists():
        return patterns

    for md_file in sorted(lessons_path.rglob("*.md")):
        try:
            with open(md_file, "r", encoding="utf-8") as f:
                content = f.read()
        except (OSError, IOError):
            continue

        fm = _parse_frontmatter(content)
        if not fm:
            _lesson_index[md_file.stem] = str(md_file)
            continue

        # Always index every lesson for O(1) lookup
        _lesson_index[md_file.stem] = str(md_file)

        if "scan" not in fm or not fm["scan"]:
            continue

        scan = fm["scan"]
        if not isinstance(scan, dict):
            continue
        if scan.get("block"):
            continue
        if scan.get("type") in ("block", "pattern", "manual"):
            continue
        # AST patterns use ast_check instead of pattern
        if "pattern" not in scan and "ast_check" not in scan:
            continue

        config_warnings = _validate_pattern(fm, scan, str(md_file))
        if config_warnings:
            for w in config_warnings:
                print(f"  WARN: {w}", file=sys.stderr)

        category = fm.get("category", md_file.parent.name)

        if platform and not _matches_platform(fm, category, platform):
            continue

        if scope_type and not _matches_scope_type(fm, scope_type):
            continue

        if caps is not None and not _matches_stack(fm, caps):
            continue

        pattern_def = {
            "id": fm.get("id", md_file.stem),
            "severity": fm.get("severity", "HIGH"),
            "category": category,
            "type": scan.get("type", "presence"),
            "description": fm.get("title", ""),
            "tags": fm.get("tags", []),
            "platform": fm.get("platform", ""),
        }

        # Add pattern field if present (not present for AST patterns)
        if "pattern" in scan:
            pattern_def["pattern"] = scan["pattern"]

        # Add ast_check field if present (for AST patterns)
        if "ast_check" in scan:
            pattern_def["ast_check"] = scan["ast_check"]

        for scan_key in ("scope", "exclude", "exclude_path", "pre_check", "exclude_line", "scope_mode",
                    "max_per_file", "skip_empty_scope", "cross_check",
                    "cross_check_scope", "cross_check_keys", "ignore_matches",
                    "context_guard"):
            if scan_key in scan:
                pattern_def[scan_key] = scan[scan_key]

        if "scope" not in pattern_def:
            pattern_def["scope"] = "**/*"

        patterns.append(pattern_def)

    # Filter disabled lessons if requested
    if not include_disabled:
        try:
            # Import here to avoid circular dependency
            sys.path.insert(0, str(Path(__file__).parent.parent))
            from memory.confidence import get_disabled_lessons
            disabled = set(get_disabled_lessons())
            patterns = [p for p in patterns if p['id'] not in disabled]
        except Exception as e:
            print(f"[kiwi] confidence filter error: {e}", file=sys.stderr)  # If confidence module not available, skip filtering

    _patterns_cache[key] = patterns
    _cache_mtime = time.time()
    return patterns
