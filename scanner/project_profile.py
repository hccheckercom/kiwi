"""Project fingerprint — detect which capabilities a project actually has.

Used by loader.py to filter lessons by `requires:`/`conflicts:` frontmatter so
a WooCommerce shop is not flagged with "use wz_* instead of wc_*" advice, and a
plain WP project is not nagged about Wezone-specific conventions.

Design rule: capability detection favours DECLARED intent over stray function
calls. `woocommerce` is added from composer deps / plugin dir, NOT from grepping
`wc_*` calls — otherwise a Wezone project that accidentally calls `WC()` would be
mislabelled as a WooCommerce project and the very lessons meant to catch that bug
would be filtered out. The exception is `wezone-commerce`, where `wz_*` usage in
code IS the canonical signal (themes rarely declare it in composer.json).
"""

import hashlib
import json
import os
import re
import time
from pathlib import Path

# In-process cache: abs_project_path -> (caps_set, timestamp)
_caps_cache = {}
_CAPS_TTL = 300  # 5 minutes — matches loader cache TTL

# Disk cache lives in Kiwi's own memory dir (NOT inside the scanned project —
# writing .kiwi/ into every target repo creates git noise; see plan R5).
_CACHE_DIR = Path(__file__).resolve().parent.parent / "memory" / "project_profiles"
_DISK_TTL = 3600  # 1 hour

# Cap how much code we grep so detection stays fast on large trees
_MAX_GREP_FILES = 400
_SKIP_DIRS = {"vendor", "node_modules", ".git", "dist", "build", "__pycache__",
              ".next", "out", "coverage", ".kiwi"}


def _read_json(project_path: str, name: str) -> dict:
    """Read + parse a JSON file at project root. Returns {} on any failure."""
    path = os.path.join(project_path, name)
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f) or {}
    except (OSError, IOError, ValueError):
        return {}


def _deps(pkg: dict) -> set:
    """Collect dependency names from composer.json / package.json shapes."""
    names = set()
    for key in ("require", "require-dev", "dependencies", "devDependencies",
                "peerDependencies"):
        section = pkg.get(key)
        if isinstance(section, dict):
            names.update(section.keys())
    return names


def _grep_any(project_path: str, pattern: str, extensions=(".php",)) -> bool:
    """True if regex matches in any project file (capped, skips vendor dirs)."""
    rx = re.compile(pattern)
    scanned = 0
    for root, dirs, files in os.walk(project_path):
        dirs[:] = [d for d in dirs if d not in _SKIP_DIRS and not d.startswith(".")]
        for fname in files:
            if not fname.endswith(extensions):
                continue
            scanned += 1
            if scanned > _MAX_GREP_FILES:
                return False
            try:
                with open(os.path.join(root, fname), "r", encoding="utf-8",
                          errors="ignore") as f:
                    if rx.search(f.read()):
                        return True
            except (OSError, IOError):
                continue
    return False


def _has_dir_named(project_path: str, target: str, max_depth: int = 4) -> bool:
    """True if a directory named `target` exists anywhere under project_path
    (bounded depth, skipping vendor/node_modules/etc.)."""
    base_depth = project_path.rstrip(os.sep).count(os.sep)
    for root, dirs, _ in os.walk(project_path):
        dirs[:] = [d for d in dirs if d not in _SKIP_DIRS and not d.startswith(".")]
        if root.count(os.sep) - base_depth >= max_depth:
            dirs[:] = []
            continue
        if target in dirs:
            return True
    return False


def _compute_stack(project_path: str) -> set:
    """Inspect the project and return the set of capabilities it actually has."""
    caps = set()

    # --- PHP / WordPress side ---
    comp_deps = _deps(_read_json(project_path, "composer.json"))
    if any("woocommerce" in d for d in comp_deps):
        caps.add("woocommerce")
    if any("wezone" in d for d in comp_deps):
        caps.add("wezone-commerce")

    # Declared WooCommerce plugin presence (declarative intent, not stray calls)
    for woo_dir in ("wp-content/plugins/woocommerce", "plugins/woocommerce"):
        if os.path.isdir(os.path.join(project_path, woo_dir)):
            caps.add("woocommerce")
            break

    # wz_* function usage is the canonical signal of a Wezone Commer codebase.
    if "wezone-commerce" not in caps and _grep_any(project_path, r"\bwz_[a-z_]+\s*\("):
        caps.add("wezone-commerce")

    # Themes consume Wezone via STRUCTURAL conventions, not wz_*() calls — a theme
    # rarely calls wz_* directly (it renders templates that do). Detect those
    # conventions so Wezone themes are not mis-classified as plain WP and stripped
    # of their lessons. wz-shims.php is the strongest single marker (Wezone-only
    # filename); store-config.php + wezone-templates/ are supporting blueprint markers.
    if "wezone-commerce" not in caps:
        theme_markers = (
            os.path.isfile(os.path.join(project_path, "inc", "wz-shims.php"))
            or os.path.isfile(os.path.join(project_path, "inc", "store-config.php"))
            or _has_dir_named(project_path, "wezone-templates")
            or _grep_any(project_path, r"wz_component\s*\(|wezone_is_active\s*\(|\bWEZONE_[A-Z_]+\b")
        )
        if theme_markers:
            caps.add("wezone-commerce")

    # --- JS / Node side ---
    js_deps = _deps(_read_json(project_path, "package.json"))
    if "next" in js_deps:
        caps.add("nextjs")
    if "react" in js_deps:
        caps.add("react")
    if "@supabase/supabase-js" in js_deps:
        caps.add("supabase")

    return caps


def _disk_cache_path(project_path: str) -> str:
    """Central cache file keyed by a hash of the project path.

    Lives under Kiwi's memory/ dir so we never write into the scanned repo.
    """
    h = hashlib.sha1(os.path.abspath(project_path).encode("utf-8")).hexdigest()[:16]
    return str(_CACHE_DIR / f"{h}.json")


def _read_disk_cache(project_path: str):
    """Return cached caps set if fresh, else None."""
    path = _disk_cache_path(project_path)
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, IOError, ValueError):
        return None
    ts = data.get("timestamp", 0)
    if time.time() - ts > _DISK_TTL:
        return None
    caps = data.get("caps")
    if isinstance(caps, list):
        return set(caps)
    return None


def _write_disk_cache(project_path: str, caps: set):
    path = _disk_cache_path(project_path)
    try:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump({"project": os.path.abspath(project_path),
                       "caps": sorted(caps), "timestamp": time.time()}, f, indent=2)
    except (OSError, IOError):
        pass  # cache is best-effort


def detect_stack(project_path: str, use_cache: bool = True) -> set:
    """Return the set of capability tags a project has.

    Capabilities currently emitted: woocommerce, wezone-commerce, nextjs, react,
    supabase. Empty set means "plain project, no recognised stack".

    Results are cached in-process (5 min) and on disk at .kiwi/project_profile.json
    (1 h). Returns None-safe empty set for a missing/invalid path.
    """
    if not project_path or not os.path.isdir(project_path):
        return set()

    abs_path = os.path.abspath(project_path)

    if use_cache:
        cached = _caps_cache.get(abs_path)
        if cached and (time.time() - cached[1]) < _CAPS_TTL:
            return set(cached[0])
        disk = _read_disk_cache(abs_path)
        if disk is not None:
            _caps_cache[abs_path] = (disk, time.time())
            return set(disk)

    caps = _compute_stack(abs_path)
    _caps_cache[abs_path] = (caps, time.time())
    if use_cache:
        _write_disk_cache(abs_path, caps)
    return set(caps)


def invalidate(project_path: str = None):
    """Clear cached profiles. Pass a path to clear one, omit to clear all."""
    global _caps_cache
    if project_path is None:
        _caps_cache = {}
        return
    _caps_cache.pop(os.path.abspath(project_path), None)