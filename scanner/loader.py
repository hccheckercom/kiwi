"""Load patterns from lessons/**/*.md frontmatter using PyYAML."""

import os
import sys
import time
from pathlib import Path

import yaml


_VALID_SCAN_TYPES = {"presence", "absence", "cross_check", "cross-check", "ast", "pattern", "block", "manual", "bom-check", "none"}
_VALID_SEVERITIES = {"CRITICAL", "HIGH", "SUGGEST", "MEDIUM", "INFO"}
_VALID_FIX_TYPES = {"replace", "template", "llm", "wrap", "delete"}

# --- Caching layer ---
_patterns_cache = {}          # key: (lessons_dir, platform, scope_type) -> list
_lesson_index = {}            # key: lesson_id -> absolute file path
_lesson_fm_cache = {}         # key: lesson_id -> (frontmatter_dict, body_str)
_cache_mtime = 0              # mtime of lessons dir when cache was built
_CACHE_TTL = 300              # 5 minutes


def invalidate_cache():
    """Force reload on next call."""
    global _patterns_cache, _lesson_index, _lesson_fm_cache, _cache_mtime
    _patterns_cache.clear()
    _lesson_index.clear()
    _lesson_fm_cache.clear()
    _cache_mtime = 0


def get_lesson_path(lesson_id: str, lessons_dir: str = None) -> str:
    """Fast O(1) lookup: lesson_id -> absolute file path."""
    if not _lesson_index:
        _build_index(lessons_dir)
    return _lesson_index.get(lesson_id, "")


def get_lesson_frontmatter(lesson_id: str, lessons_dir: str = None) -> tuple:
    """Fast O(1) lookup: lesson_id -> (frontmatter_dict, body_str)."""
    if lesson_id in _lesson_fm_cache:
        return _lesson_fm_cache[lesson_id]
    path = get_lesson_path(lesson_id, lessons_dir)
    if not path:
        return None, None
    try:
        content = Path(path).read_text(encoding="utf-8")
    except (OSError, IOError):
        return None, None
    fm = _parse_frontmatter(content)
    body = ""
    if content.startswith("---"):
        end = content.find("\n---", 3)
        if end != -1:
            body = content[end + 4:].strip()
        else:
            body = content
    else:
        body = content
    _lesson_fm_cache[lesson_id] = (fm, body)
    return fm, body


def _build_index(lessons_dir: str = None):
    """Build lesson_id -> file path index (one-time scan)."""
    global _lesson_index, _cache_mtime
    if lessons_dir is None:
        lessons_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "lessons")
    lessons_path = Path(lessons_dir)
    if not lessons_path.exists():
        return
    for md_file in lessons_path.rglob("*.md"):
        _lesson_index[md_file.stem] = str(md_file)
    _cache_mtime = time.time()


def _validate_pattern(fm: dict, scan: dict, filepath: str) -> list:
    """Validate lesson config, return list of warning strings."""
    warnings = []
    lesson_id = fm.get("id", Path(filepath).stem)

    cg = scan.get("context_guard")
    if cg is not None and not isinstance(cg, dict):
        warnings.append(f"{lesson_id}: context_guard must be dict (got {type(cg).__name__}), use {{pattern: ...}}")

    if cg and isinstance(cg, dict) and "pattern" not in cg:
        warnings.append(f"{lesson_id}: context_guard missing 'pattern' key")

    stype = scan.get("type", "presence")
    if stype not in _VALID_SCAN_TYPES:
        warnings.append(f"{lesson_id}: unknown scan type '{stype}'")

    sev = fm.get("severity", "HIGH")
    if sev not in _VALID_SEVERITIES:
        warnings.append(f"{lesson_id}: unknown severity '{sev}'")

    for key in ("exclude_path", "exclude_line", "pre_check", "scope"):
        val = scan.get(key)
        if val is not None and not isinstance(val, str):
            warnings.append(f"{lesson_id}: {key} must be string (got {type(val).__name__})")

    # exclude can be string or list
    exclude_val = scan.get("exclude")
    if exclude_val is not None and not isinstance(exclude_val, (str, list)):
        warnings.append(f"{lesson_id}: exclude must be string or list (got {type(exclude_val).__name__})")

    fix = fm.get("fix")
    if fix and isinstance(fix, dict):
        ft = fix.get("type")
        if ft and ft not in _VALID_FIX_TYPES:
            warnings.append(f"{lesson_id}: unknown fix type '{ft}'")

    return warnings


def _parse_frontmatter(content: str) -> dict:
    """Parse YAML frontmatter from markdown file using PyYAML."""
    if not content.startswith("---"):
        return {}

    end = content.find("\n---", 3)
    if end == -1:
        return {}

    yaml_block = content[4:end]
    try:
        return yaml.safe_load(yaml_block) or {}
    except yaml.YAMLError:
        return {}


_WP_CATEGORIES = {"php-security", "wezone-api", "css-tokens", "js-contract",
                  "file-structure", "performance", "placeholder", "ads-compliance",
                  "feature-suggest", "edge-cases", "db-schema",
                  "php-db", "php-performance", "php-i18n", "php-architecture", "loyalty"}
_NEXTJS_CATEGORIES = {"nextjs-react", "supabase"}
_PYTHON_CATEGORIES = {"python", "python-windows", "fastapi", "websocket",
                      "error-handling", "resource-management"}
_WEBSTORE_TAGS = {"webstore"}
_WP_TAGS = {"theme", "plugin", "wp"}
_PYTHON_TAGS = {"python", "fastapi", "flask", "django"}

def _matches_platform(fm: dict, category: str, platform: str) -> bool:
    """Return True if this lesson should be included for the given platform."""
    lesson_platform = fm.get("platform")
    if lesson_platform:
        if lesson_platform == "both":
            return True
        return lesson_platform == platform

    # Infer from tags when platform field is absent
    tags = set(fm.get("tags", []))
    if "both" in tags:
        return True
    if tags & _PYTHON_TAGS and not (tags & _WP_TAGS) and not (tags & _WEBSTORE_TAGS):
        return platform in ("python", "both")
    if tags & _WEBSTORE_TAGS and not (tags & _WP_TAGS):
        return platform in ("nextjs", "both")
    if tags & _WP_TAGS and not (tags & _WEBSTORE_TAGS):
        return platform in ("wp", "both")

    # Infer from category when platform field and tags are absent
    if category in _PYTHON_CATEGORIES:
        return platform in ("python", "both")
    if category in _NEXTJS_CATEGORIES:
        return platform in ("nextjs", "both")
    if category in _WP_CATEGORIES:
        return platform in ("wp", "both")
    return platform != "python"  # unknown category — include for wp/nextjs, exclude for python


def _matches_scope_type(fm: dict, scope_type: str) -> bool:
    """Return True if this lesson applies to the given scope_type (theme|plugin|both)."""
    lesson_scope = fm.get("scope_type")
    if not lesson_scope:
        return True  # no scope_type declared — applies everywhere
    if lesson_scope == "both":
        return True
    return lesson_scope == scope_type


def load_patterns(lessons_dir: str = None, platform: str = None, scope_type: str = None, include_disabled: bool = False) -> list:
    """Load all patterns from lessons/**/*.md frontmatter scan: blocks.

    Results are cached per (lessons_dir, platform, scope_type) combination.
    Call invalidate_cache() to force reload.

    Args:
        lessons_dir: Path to lessons directory
        platform: Filter by platform (wp, nextjs, both)
        scope_type: Filter by scope (theme, plugin, both)
        include_disabled: If False, filter out disabled lessons (default: False)
    """
    global _cache_mtime

    if lessons_dir is None:
        lessons_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "lessons")

    key = (lessons_dir, platform or "", scope_type or "", include_disabled)
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
            import sys
            sys.path.insert(0, str(Path(__file__).parent.parent))
            from memory.confidence import get_disabled_lessons
            disabled = set(get_disabled_lessons())
            patterns = [p for p in patterns if p['id'] not in disabled]
        except Exception as e:
            print(f"[kiwi] confidence filter error: {e}", file=sys.stderr)  # If confidence module not available, skip filtering

    _patterns_cache[key] = patterns
    _cache_mtime = time.time()
    return patterns
