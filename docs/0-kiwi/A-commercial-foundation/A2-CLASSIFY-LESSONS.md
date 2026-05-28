# A2 — Audit & Classify 740 Lessons (2 days)

## Mục tiêu
Phân loại 740 lessons thành Universal (ship free cho mọi user) vs Wezone-specific (giữ private).
Output: `plugins/generic/lessons/` chứa ~400-500 universal lessons sẵn sàng cho A3 (Generic Plugin).

---

## Current State (post-A1)

### Đã có
- `core/` — 11 files, plugin interfaces hoạt động
- `plugins/wezone_wp/` — wraps full 740 lessons, 6 checkers, 67 context keywords
- `plugins/wezone_wp/manifest.json` — lessons_count: 740
- Plugin loader + registry — auto-detect project → load plugin

### Cần làm
- Classification script → phân loại 740 lessons
- Copy universal subset → `plugins/generic/lessons/`
- Generic plugin manifest (lessons_count = actual)
- Verify: wezone_wp vẫn dùng full 740, generic dùng subset

---

## Actual Category Breakdown (39 categories, 740 lessons)

### Tier 1: Clearly Universal (~450 lessons)
| Category | Count | Rationale |
|----------|-------|-----------|
| php-security | 118 | XSS, SQLi, CSRF — universal PHP |
| performance | 62 | N+1, cache, lazy load — any project |
| nextjs-react | 39 | React/Next.js patterns — universal |
| python | 36 | Python best practices |
| security | 27 | General security (non-PHP) |
| supabase | 28 | Supabase patterns |
| edge-cases | 18 | Error boundary, null checks |
| fastapi | 17 | FastAPI patterns |
| js-contract | 15 | JS type contracts |
| responsive | 14 | Mobile-first, breakpoints |
| db-schema | 14 | Schema design, migrations |
| accessibility | 13 | ARIA, focus, contrast |
| concurrency | 11 | Race conditions, locks |
| component-pattern | 10 | Loading/error/empty states |
| dark-mode | 9 | Dark mode class pairing |
| reliability | 9 | Retry, circuit breaker |
| php-db | 9 | Prepared statements, transactions |
| ai-safety | 7 | Prompt injection, guardrails |
| portability | 7 | Cross-platform code |
| layout-consistency | 7 | Container width, spacing |
| php-performance | 6 | PHP-specific perf |
| code-quality | 5 | Naming, dead code |
| react | 5 | React-specific |
| php-architecture | 4 | PHP design patterns |
| php-i18n | 4 | Internationalization |
| js-security | 3 | JS security |
| websocket | 3 | WebSocket patterns |
| error-handling | 2 | Error handling |
| d3 | 1 | D3.js |
| deployment | 1 | Deploy patterns |
| placeholder | 1 | Placeholder |
| python-windows | 1 | Python Windows |
| resource-management | 1 | Resource cleanup |
| **Subtotal** | **~546** | |

### Tier 2: Needs Per-Lesson Inspection (~194 lessons)
| Category | Count | Why ambiguous |
|----------|-------|---------------|
| wezone-api | 109 | Mix of generic REST patterns + wz_* specific |
| feature-suggest | 37 | May contain Wezone business logic |
| css-tokens | 34 | Mix of generic Tailwind + Wezone design tokens |
| ads-compliance | 27 | Generic ad compliance vs Wezone-specific |
| file-structure | 22 | Generic WP structure vs Wezone conventions |
| loyalty | 4 | Likely Wezone-specific |
| **Subtotal** | **~233** | |

### Expected outcome after classification
- **Universal: ~450-520 lessons** (Tier 1 full + ~50% of Tier 2)
- **Wezone-specific: ~220-290 lessons** (wz_* patterns + Wezone conventions)

---

## Classification Logic (3-layer)

### Layer 1: Category-level auto-classify
```python
# Categories that are 100% universal — copy entire category
UNIVERSAL_CATEGORIES = {
    'accessibility', 'ai-safety', 'code-quality', 'component-pattern',
    'concurrency', 'd3', 'dark-mode', 'db-schema', 'deployment',
    'edge-cases', 'error-handling', 'fastapi', 'js-contract',
    'js-security', 'layout-consistency', 'nextjs-react', 'performance',
    'php-architecture', 'php-db', 'php-i18n', 'php-performance',
    'php-security', 'placeholder', 'portability', 'python',
    'python-windows', 'react', 'reliability', 'resource-management',
    'responsive', 'security', 'supabase', 'websocket',
}

# Categories that are 100% Wezone — skip entirely
WEZONE_CATEGORIES = {
    'loyalty',  # Wezone loyalty program
}
```

### Layer 2: Keyword-based per-lesson classification (for ambiguous categories)
```python
WEZONE_KEYWORDS = [
    # Wezone Commer API
    'wz_', 'wezone', 'wezone_is_active', 'wezone-commer',
    'wz_config', 'wz_bulk_insert', 'wz_get_product',
    'wz_cart', 'wz_order', 'wz_product',
    # Wezone data patterns
    "$product['", '$product["',
    'store-config.php', 'store_config',
    # Wezone design system
    'wz-', 'sfvn-', 'trunganh-', 'funilux-',
    # BEM ban (Wezone-specific rule)
    'BEM', '__', '--',
]

WEZONE_PATTERN_REGEXES = [
    r'wz_\w+',           # wz_* function calls
    r'wezone_\w+',       # wezone_* hooks
    r'\$product\[',      # bracket accessor
    r'Plugin\.php',      # Wezone plugin entry
]
```

### Layer 3: Manual review (~30-50 edge cases)
Lessons that don't match Layer 1 or 2 clearly → output to `review_needed.json` for manual decision.

---

## Tasks

### Day 1: Build & run classification script

| # | Task | Output |
|---|------|--------|
| 2.1 | Create `tools/classify_lessons.py` | Script file |
| 2.2 | Scan all 740 lessons, apply 3-layer logic | `classification_report.json` |
| 2.3 | Generate summary stats | Console output + report |
| 2.4 | Output `review_needed.json` for ambiguous lessons | ~30-50 lessons |
| 2.5 | Manual review + classify edge cases | Updated report |

### Day 2: Copy + verify

| # | Task | Output |
|---|------|--------|
| 2.6 | Create `plugins/generic/` directory structure | Folder tree |
| 2.7 | Copy universal lessons → `plugins/generic/lessons/` | ~450-520 files |
| 2.8 | Generate `plugins/generic/manifest.json` | Manifest with actual count |
| 2.9 | Create minimal `plugins/generic/plugin.py` (stub for A3) | Plugin file |
| 2.10 | Test: `kiwi_scan` with wezone_wp → still uses 740 lessons | Pass |
| 2.11 | Test: `kiwi_scan` with generic → uses universal subset | Pass |
| 2.12 | Test: no lesson appears in generic that contains wz_* | Pass |

---

## Output Structure

```
plugins/
├── generic/
│   ├── __init__.py
│   ├── plugin.py              # Minimal KiwiPlugin impl (stub, expanded in A3)
│   ├── manifest.json          # {lessons_count: N, categories: [...]}
│   └── lessons/               # ~450-520 universal lessons (COPY, not symlink)
│       ├── accessibility/
│       ├── performance/
│       ├── php-security/
│       ├── responsive/
│       ├── security/
│       ├── python/
│       ├── nextjs-react/
│       └── ... (32+ categories)
│
└── wezone_wp/
    ├── plugin.py              # Unchanged — still points to ../../lessons/
    └── manifest.json          # Unchanged — lessons_count: 740
```

**Key decisions:**
- Universal lessons are COPIED (not symlinked) — generic plugin is self-contained
- Wezone plugin keeps pointing to original `lessons/` dir (all 740)
- Generic plugin.py is a stub — full auto-learn logic comes in A3
- Generic plugin `detect_project()` returns 0.1 (lowest priority, fallback only)

---

## Classification Script Design

```python
# tools/classify_lessons.py
# Usage: python tools/classify_lessons.py [--dry-run] [--output report.json]

import json, re, os
from pathlib import Path

LESSONS_DIR = Path(__file__).parent.parent / "lessons"

def classify_lesson(path: Path, category: str) -> tuple[str, str]:
    """Returns (classification, reason)"""
    
    # Layer 1: category-level
    if category in UNIVERSAL_CATEGORIES:
        return ('universal', f'category:{category} is universal')
    if category in WEZONE_CATEGORIES:
        return ('wezone', f'category:{category} is wezone-only')
    
    # Layer 2: keyword scan
    content = path.read_text(encoding='utf-8', errors='ignore')
    for keyword in WEZONE_KEYWORDS:
        if keyword in content:
            return ('wezone', f'keyword:{keyword}')
    for regex in WEZONE_PATTERN_REGEXES:
        if re.search(regex, content):
            return ('wezone', f'regex:{regex}')
    
    # Layer 3: ambiguous
    return ('review', 'no clear signal')

def main():
    report = {'universal': [], 'wezone': [], 'review': []}
    
    for category_dir in sorted(LESSONS_DIR.iterdir()):
        if not category_dir.is_dir():
            continue
        category = category_dir.name
        for lesson_file in sorted(category_dir.glob('*.md')):
            classification, reason = classify_lesson(lesson_file, category)
            report[classification].append({
                'file': str(lesson_file.relative_to(LESSONS_DIR)),
                'category': category,
                'reason': reason,
            })
    
    print(f"Universal: {len(report['universal'])}")
    print(f"Wezone:    {len(report['wezone'])}")
    print(f"Review:    {len(report['review'])}")
    
    with open('classification_report.json', 'w') as f:
        json.dump(report, f, indent=2)
```

---

## Generic Plugin Stub (created in A2, expanded in A3)

```python
# plugins/generic/plugin.py
"""Generic plugin — universal lessons for any codebase."""

from pathlib import Path
from core.plugin_base import KiwiPlugin, PluginManifest

_PLUGIN_DIR = Path(__file__).parent

class GenericPlugin(KiwiPlugin):

    def get_manifest(self) -> PluginManifest:
        return PluginManifest(
            name="generic",
            version="1.0.0",
            languages=["php", "js", "ts", "python", "css"],
            frameworks=[],
            platforms=["wp", "nextjs", "python"],
            scope_types=["theme", "plugin", "app"],
            lessons_dir=str(_PLUGIN_DIR / "lessons"),
            description="Universal code quality — 450+ lessons for any project",
        )

    def get_checkers(self) -> dict:
        # Reuse core checkers (presence, absence, cross-check)
        from scanner.checkers import REGISTRY
        return {k: v for k, v in REGISTRY.items()
                if k in ('presence', 'absence', 'cross-check', 'bom-check')}

    def get_quality_rules(self) -> list:
        return []  # No opinionated rules — expanded in A3

    def get_context_map(self) -> dict:
        return {}  # Auto-learn in A3

    def detect_project(self, path: str) -> float:
        return 0.1  # Lowest priority — fallback when no specific plugin matches

Plugin = GenericPlugin
```

---

## Verification Checklist

| # | Check | Expected |
|---|-------|----------|
| 1 | `len(universal) + len(wezone) + len(review) == 740` | True |
| 2 | No lesson in `plugins/generic/lessons/` contains `wz_` in pattern field | True |
| 3 | `plugins/wezone_wp/` still loads 740 lessons | True |
| 4 | `plugins/generic/` loads ~450-520 lessons | True |
| 5 | `plugin_registry.discover_plugins()` finds both plugins | True |
| 6 | `detect_project(wezone_path)` → wezone_wp wins (higher confidence) | True |
| 7 | `detect_project(random_wp_path)` → generic wins (fallback) | True |
| 8 | Existing 21 tests still pass | True |

---

## Dependencies
- A1 (DONE) — plugin structure exists

## Blocks
- A3 (Generic Plugin) — needs universal lessons from A2

## Done khi
- Classification script runs, produces clear report
- ~450-520 lessons classified as universal (zero wz_* contamination)
- `plugins/generic/` exists with lessons + stub plugin
- Wezone plugin unchanged — zero regression
- All 21 existing tests pass
- `kiwi_scan` on non-Wezone WP project → uses generic lessons
