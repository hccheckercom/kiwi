"""File scope resolution for Kiwi Scanner."""

import os
from fnmatch import fnmatchcase
from pathlib import Path

GLOBAL_EXCLUDE_DIRS = {"node_modules", ".git", "vendor", ".claude", "__pycache__", ".next", "dist", "build", ".turbo", "out"}

GLOBAL_EXCLUDE_FILES = {
    "src/main.css", "src/output.css", "assets/css/main.css",
    "dist/style.css", "build/style.css", "style.min.css",
}

COMPILED_CSS_PATTERNS = (
    "main.css", "output.css", "style.min.css", "tailwind.css",
    "compiled.css", "bundle.css", "app.min.css",
)


def is_compiled_file(filepath: str, theme_path: str) -> bool:
    """Check if file is a compiled/generated CSS/JS that should be skipped."""
    rel = os.path.relpath(filepath, theme_path).replace("\\", "/")
    if rel in GLOBAL_EXCLUDE_FILES:
        return True
    basename = os.path.basename(filepath)
    if basename in COMPILED_CSS_PATTERNS:
        return True
    if basename.endswith(".min.css") or basename.endswith(".min.js"):
        return True
    return False


def _is_globally_excluded(filepath: str, theme_path: str) -> bool:
    rel = os.path.relpath(filepath, theme_path).replace("\\", "/")
    parts = rel.split("/")
    for p in parts:
        if p in GLOBAL_EXCLUDE_DIRS:
            return True
        if p.startswith(".disabled-"):
            return True
    if is_compiled_file(filepath, theme_path):
        return True
    return False


def rewrite_scope_for_theme(scope):
    """Strip monorepo-level prefixes (themes/*/, themes/**/) from each scope part.

    When scanning a single theme inside a themes_folder, patterns written for
    monorepo roots (e.g. "themes/*/functions.php") must be rewritten to their
    per-theme equivalent ("functions.php").

    Args:
        scope: str or list of patterns

    Returns:
        str (pipe-separated) or list, matching input type
    """
    import re

    # Handle list input
    if isinstance(scope, list):
        rewritten = []
        for part in scope:
            cleaned = re.sub(r"^themes/\*\*?/", "", part.strip())
            rewritten.append(cleaned)
        # Deduplicate while preserving order
        seen = set()
        result = []
        for p in rewritten:
            if p not in seen:
                seen.add(p)
                result.append(p)
        return result

    # Handle string input (original behavior)
    parts = [s.strip() for s in scope.split("|")]
    rewritten = []
    for part in parts:
        # Strip leading themes/*/ or themes/**/ prefix
        cleaned = re.sub(r"^themes/\*\*?/", "", part)
        rewritten.append(cleaned)
    # Deduplicate while preserving order
    seen = set()
    result = []
    for p in rewritten:
        if p not in seen:
            seen.add(p)
            result.append(p)
    return "|".join(result)


def resolve_scope(theme_path: str, scope: str, exclude: str = None) -> list:
    """Resolve glob scope to actual file paths within theme."""
    theme = Path(theme_path)
    files = []

    if not scope:
        return []

    if scope == "theme root":
        return [str(p) for p in theme.iterdir() if p.is_file()]

    scope_parts = [s.strip() for s in scope.split("|")]

    for scope_pattern in scope_parts:
        if "**" in scope_pattern:
            parts = scope_pattern.split("**")
            base = theme / parts[0].rstrip("/\\")
            if not base.exists():
                continue
            suffix = parts[1].lstrip("/\\") if len(parts) > 1 else "*"
            for p in base.rglob(suffix):
                if p.is_file():
                    files.append(str(p))
        elif "*" in scope_pattern:
            parent = scope_pattern.rsplit("/", 1)
            if len(parent) == 2:
                base = theme / parent[0]
                pattern = parent[1]
            else:
                base = theme
                pattern = parent[0]
            if base.exists():
                for p in base.glob(pattern):
                    if p.is_file():
                        files.append(str(p))
        else:
            target = theme / scope_pattern
            if target.is_file():
                files.append(str(target))
            elif target.is_dir():
                for p in target.rglob("*"):
                    if p.is_file():
                        files.append(str(p))

    files = [f for f in files if not _is_globally_excluded(f, theme_path)]

    if exclude:
        # Handle exclude as string or list
        if isinstance(exclude, list):
            exclude_patterns = [e.strip() for e in exclude]
        else:
            exclude_patterns = [e.strip() for e in exclude.split("|")]

        filtered = []
        for f in files:
            rel = os.path.relpath(f, theme_path).replace("\\", "/")
            excluded = False
            for ep in exclude_patterns:
                if fnmatchcase(rel, ep) or fnmatchcase(rel, f"**/{ep}"):
                    excluded = True
                    break
            if not excluded:
                filtered.append(f)
        files = filtered

    return list(set(files))