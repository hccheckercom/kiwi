# A1 — Core/Plugin Separation (5 days)

## Mục tiêu
Tách Kiwi thành Core (language-agnostic reasoning engine) + Plugin (language-specific knowledge packs).
Wezone vẫn hoạt động y hệt — zero regression.

---

## Current State Analysis (2026-05-28)

### Codebase metrics
| Module | Python files | Role |
|--------|-------------|------|
| scanner/ | 29 | Checkers, loader, resolver, reporters, fixer |
| agent/ | 58 | Reasoning R0-R8, context, orchestrator, tools |
| generator/ | 77 | Theme generation, ML classifier, exporters |
| learning/ | 22 | Pattern mining, anomaly detection, embeddings |
| memory/ | 8 | SQLite persistence, confidence scoring |
| deploy/ | 7 | VPS deployment, health checks |
| hooks/ | 8 | Post-edit guardrails |
| tests/ | 48 files | Integration + unit tests |
| **Total** | **~300+** | |

### Knowledge base
- **740 lesson files** across 39 categories
- **3 platforms** already defined in `_meta.json`: wp, nextjs, python
- **11 checker types**: presence, absence, cross-check, bom-check, ast, semgrep, class_conflict, dark_coverage, pattern_presence, responsive_coverage, sibling_consistency

### Already language-agnostic (NO changes needed)
- `agent/reasoning/` — R0-R8 (trust scorer, calibrator, thinker, learner, etc.)
- `memory/` — SQLite persistence, confidence scoring
- `scanner/models.py` — Violation, Report dataclasses
- `scanner/reporters/` — text + JSON output formatters
- `scanner/cache.py` — scan result caching
- `agent/loop.py`, `agent/state.py`, `agent/orchestrator.py`
- `agent/cost.py`, `agent/retry.py`, `agent/scoring.py`
- `learning/embeddings.py`, `learning/dedup.py`, `learning/models.py`

### Language-specific (needs extraction into plugin)
- `scanner/checkers/` — 11 checkers (some generic, some WP-specific)
- `scanner/loader.py` — lesson loading (generic engine, but paths are hardcoded)
- `agent/context.py` — task-to-category mapping (WP keywords hardcoded)
- `agent/reasoning/code_drafter.py` — generates PHP/Tailwind code
- `generator/` — entire module is WP theme generation
- `lessons/` — 740 files, mostly WP-specific
- `templates/` — WP theme templates
- `hooks/post_edit.py` — WP-specific guardrails
- `deploy/` — WP/Next.js deployment configs

### Mixed (needs refactoring)
- `mcp_server.py` — core tools + WP-specific logic in one file
- `scanner/resolver.py` — generic file resolution + WP-specific excludes
- `scanner/cli.py` — generic scan loop + WP project detection

---

## Architecture Target

```
kiwi/
├── core/                              # Language-agnostic engine
│   ├── __init__.py
│   ├── plugin_base.py                 # Abstract: KiwiPlugin, PluginManifest
│   ├── checker_base.py                # Abstract: BaseChecker.check(pattern_def, files, root) → list[Violation]
│   ├── drafter_base.py                # Abstract: BaseDrafter.generate(brief, path) → str
│   ├── quality_base.py                # Abstract: BaseQualityRule
│   ├── plugin_loader.py               # Auto-detect project → load correct plugin(s)
│   ├── plugin_registry.py             # Discover installed plugins (entry_points or folder scan)
│   ├── scanner/
│   │   ├── engine.py                  # Generic scan loop (extracted from cli.py)
│   │   ├── models.py                  # Violation, Report (moved from scanner/models.py)
│   │   ├── loader.py                  # Generic lesson loader (parameterized paths)
│   │   ├── resolver.py                # Generic file resolution (configurable excludes)
│   │   ├── cache.py                   # Scan caching (unchanged)
│   │   └── reporters/                 # text + JSON (unchanged)
│   ├── reasoning/                     # R0-R8 (moved from agent/reasoning/)
│   ├── memory/                        # SQLite (unchanged)
│   ├── learning/                      # Pattern mining (unchanged)
│   └── mcp_server.py                  # Core-only tools (scan, check, query, fix, stats)
│
├── plugins/
│   └── wezone_wp/                     # Wezone WordPress Plugin
│       ├── __init__.py
│       ├── plugin.py                  # Implements KiwiPlugin
│       ├── manifest.json              # Plugin metadata
│       ├── lessons/                   # 740 lessons (moved)
│       ├── templates/                 # WP theme templates (moved)
│       ├── checkers/                  # WP-specific checkers
│       │   ├── presence.py            # PresenceChecker (unchanged logic)
│       │   ├── absence.py
│       │   ├── cross_check.py
│       │   ├── bom.py
│       │   ├── ast_checker.py
│       │   ├── responsive_coverage.py
│       │   ├── dark_coverage.py
│       │   ├── sibling_consistency.py
│       │   ├── class_conflict.py
│       │   ├── pattern_presence.py
│       │   └── semgrep.py
│       ├── context_map.py             # Task-to-category mapping (from agent/context.py)
│       ├── code_drafter.py            # PHP/Tailwind generation
│       ├── quality_rules.py           # wz_*, BEM, WooCommerce checks
│       ├── generator/                 # Theme generation (moved)
│       ├── deploy/                    # WP deployment configs
│       └── hooks/                     # Post-edit guardrails
```

---

## Abstract Interfaces

### plugin_base.py

```python
from abc import ABC, abstractmethod
from dataclasses import dataclass, field


@dataclass
class PluginManifest:
    name: str
    version: str
    languages: list[str]          # ["php", "js", "css"]
    frameworks: list[str]         # ["wordpress", "tailwind"]
    lessons_dir: str | None       # Path to pre-built lessons (None = auto-learn only)
    platforms: list[str]          # ["wp"] — matches _meta.json platform keys
    scope_types: list[str]        # ["theme", "plugin"]


class KiwiPlugin(ABC):
    @abstractmethod
    def get_manifest(self) -> PluginManifest: ...

    @abstractmethod
    def get_checkers(self) -> dict[str, object]:
        """Return {type_name: checker_instance} registry."""
        ...

    @abstractmethod
    def get_quality_rules(self) -> list[dict]: ...

    @abstractmethod
    def get_context_map(self) -> dict[str, list[str]]:
        """Return {keyword: [categories]} for task routing."""
        ...

    def get_drafters(self) -> list:
        return []

    def get_excluded_dirs(self) -> set[str]:
        return set()

    def get_excluded_files(self) -> set[str]:
        return set()

    def detect_project(self, path: str) -> float:
        """Return confidence 0.0-1.0 that this plugin handles the given project."""
        return 0.0
```

### checker_base.py

```python
from abc import ABC, abstractmethod
from core.scanner.models import Violation


class BaseChecker(ABC):
    @abstractmethod
    def check(self, pattern_def: dict, files: list, root_path: str) -> list[Violation]:
        """Run check against files, return violations."""
        ...
```

### drafter_base.py

```python
from abc import ABC, abstractmethod


class BaseDrafter(ABC):
    @abstractmethod
    def generate(self, brief: dict, target_path: str, level: str = "skeleton") -> str:
        """Generate code at given completeness level."""
        ...
```

---

## Tasks (Detailed)

### Day 1: Extract core interfaces + models

| # | Task | Files affected |
|---|------|---------------|
| 1.1 | Create `core/__init__.py`, `core/plugin_base.py` | New |
| 1.2 | Create `core/checker_base.py` | New |
| 1.3 | Create `core/drafter_base.py`, `core/quality_base.py` | New |
| 1.4 | Create `core/plugin_loader.py` (auto-detect logic) | New |
| 1.5 | Create `core/plugin_registry.py` (discover plugins) | New |
| 1.6 | Move `scanner/models.py` → `core/scanner/models.py` + re-export | Move + alias |
| 1.7 | Move `scanner/cache.py` → `core/scanner/cache.py` | Move + alias |
| 1.8 | Move `scanner/reporters/` → `core/scanner/reporters/` | Move + alias |

**Backward compat:** Old import paths (`from scanner.models import Violation`) still work via re-exports.

### Day 2: Extract scanner engine + refactor loader

| # | Task | Files affected |
|---|------|---------------|
| 2.1 | Extract generic scan loop from `scanner/cli.py` → `core/scanner/engine.py` | Refactor |
| 2.2 | Refactor `scanner/loader.py` — parameterize `lessons_dir` (remove hardcoded path) | Refactor |
| 2.3 | Refactor `scanner/resolver.py` — make excludes configurable via plugin | Refactor |
| 2.4 | Create `core/scanner/__init__.py` with `scan(path, plugins, **opts)` entry point | New |
| 2.5 | `scanner/cli.py` becomes thin wrapper calling `core/scanner/engine.scan()` | Refactor |

### Day 3: Wrap existing code as Wezone plugin

| # | Task | Files affected |
|---|------|---------------|
| 3.1 | Create `plugins/wezone_wp/__init__.py` + `plugin.py` implementing KiwiPlugin | New |
| 3.2 | Create `plugins/wezone_wp/manifest.json` | New |
| 3.3 | Wrap all 11 checkers — implement BaseChecker interface | Thin wrappers |
| 3.4 | Extract task-to-category map from `agent/context.py` → `plugins/wezone_wp/context_map.py` | Extract |
| 3.5 | Wrap quality rules from existing code → `plugins/wezone_wp/quality_rules.py` | Extract |
| 3.6 | Symlink/reference `lessons/` and `templates/` from plugin (no file move yet) | Config |

### Day 4: Plugin loader + routing integration

| # | Task | Files affected |
|---|------|---------------|
| 4.1 | Implement `plugin_loader.py` — detect WP project → load wezone_wp | Implement |
| 4.2 | Refactor `mcp_server.py` — route scan/check/context through plugin interface | Refactor |
| 4.3 | Refactor `agent/context.py` — delegate to plugin's `get_context_map()` | Refactor |
| 4.4 | Refactor `agent/reasoning/code_drafter.py` — delegate to plugin's drafter | Refactor |
| 4.5 | Update `hooks/post_edit.py` — use plugin-aware scan | Refactor |

### Day 5: Tests + validation + cleanup

| # | Task | Files affected |
|---|------|---------------|
| 5.1 | Run ALL existing 48 test files — ensure 0 regression | Verify |
| 5.2 | Add new tests: plugin loading, interface contracts, detection | New tests |
| 5.3 | Test: `kiwi_scan` on wezone-plugins still works identically | Integration test |
| 5.4 | Test: `kiwi_context` still returns correct rules | Integration test |
| 5.5 | Test: `kiwi_check` on single file still works | Integration test |
| 5.6 | Update `_meta.json` if needed | Config |
| 5.7 | Update imports across codebase (grep for old paths) | Bulk update |

---

## Migration Strategy: Symlinks First, Move Later

**Phase A1 (this task):** Create plugin interface + wrap existing code. Lessons/templates stay in current location, plugin references them via path config. Zero file moves = zero risk.

**Phase A2 (next task):** Once generic plugin exists and is tested, physically move `lessons/` → `plugins/wezone_wp/lessons/`. This is a separate PR with clear git history.

---

## Detection Logic (plugin_loader.py)

```python
def detect_project_type(path: str) -> list[tuple[KiwiPlugin, float]]:
    """Return [(plugin, confidence)] sorted by confidence desc."""
    results = []
    for plugin in discover_plugins():
        confidence = plugin.detect_project(path)
        if confidence > 0.0:
            results.append((plugin, confidence))
    return sorted(results, key=lambda x: x[1], reverse=True)


# Wezone WP detection signals:
# - functions.php exists → WP theme (0.6)
# - wz_* functions found → Wezone specifically (0.9)
# - style.css with "Theme Name:" → WP theme (0.7)
# - mu-plugins/ structure → WP plugin (0.7)
# - composer.json with "wordpress" → WP (0.5)
```

---

## Risk Mitigation

| Risk | Mitigation |
|------|-----------|
| Import breakage | Re-export from old paths (backward compat shims) |
| Test regression | Run full test suite after each day's work |
| MCP server breaks | Keep old `mcp_server.py` as fallback, new one delegates |
| Performance regression | Benchmark scan time before/after (target: < 5% slower) |
| Generator breaks | Generator stays untouched in Day 1-4, only wired in Day 4 |

---

## Dependencies
- Không có — task đầu tiên trong commercial roadmap
- Blocks: A2 (Generic Plugin), A3 (Usage Tracking), A5 (CLI Packaging)

## Done khi
- [ ] `core/plugin_base.py` có abstract classes hoàn chỉnh
- [ ] `core/scanner/engine.py` chạy scan loop generic
- [ ] `plugins/wezone_wp/plugin.py` implements KiwiPlugin đầy đủ
- [ ] Plugin loader detect WP project → load wezone_wp tự động
- [ ] ALL 48 test files pass (zero regression)
- [ ] `kiwi_scan`, `kiwi_check`, `kiwi_context` MCP tools hoạt động y hệt
- [ ] Benchmark: scan time không tăng quá 5%
- [ ] Old import paths vẫn work (backward compat re-exports)

---

## Estimated Effort

| Day | Focus | Output |
|-----|-------|--------|
| 1 | Interfaces + models extraction | `core/` skeleton with abstract classes |
| 2 | Scanner engine extraction | Generic scan loop, parameterized loader |
| 3 | Wezone plugin wrapper | `plugins/wezone_wp/` fully implements interface |
| 4 | Integration + routing | MCP server + agent use plugin interface |
| 5 | Tests + validation | Zero regression confirmed, new tests added |

**Total: 5 days. Zero breaking changes for Wezone.**
