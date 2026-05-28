# A6 — CLI Packaging (3 days)

## Mục tiêu
User cài `pip install kiwi-ai` → chạy `kiwi init` → ready trong 30 giây.
Mọi command reuse logic có sẵn từ A1-A5, zero duplication.

## Dependencies
- A1 (core/plugin separation)
- A2 (classify lessons — generic plugin)
- A3 (generic auto-learn)
- A4 (usage tracking + dashboard)
- A5 (freemium gating)

## Scope — IN vs OUT

| IN (A6) | OUT (defer) |
|---------|-------------|
| Python CLI (`click`) | HTTP server (→ A7) |
| `pyproject.toml` packaging | npm wrapper (→ A7) |
| 6 subcommands | WebSocket events (→ A7) |
| Cross-platform (Win/Mac/Linux) | VS Code extension comm (→ A7) |
| MCP server registration | Cloud/team features |

## Tasks
1. CLI entry point: `kiwi` command group via `click`
2. `kiwi init`: scan codebase → detect → create `.kiwi/` → register MCP
3. `kiwi scan <path>`: full project scan (reuses `scanner.cli`)
4. `kiwi check <file>`: single file check (reuses `_handle_check`)
5. `kiwi dashboard`: show metrics (reuses `tracking.dashboard`)
6. `kiwi status`: quick summary (tier + patterns + savings)
7. `kiwi upgrade <tier>`: upgrade/activate license flow
8. `pyproject.toml` with `[project.scripts]` entry point
9. Cross-platform test (Windows PowerShell + Unix bash)
10. QA test suite: `tests/test_a6_cli.py`

## Output
```
kiwi/
├── cli/
│   ├── __init__.py
│   ├── main.py              # click.group entry point
│   ├── commands/
│   │   ├── __init__.py
│   │   ├── init_cmd.py      # kiwi init
│   │   ├── scan.py          # kiwi scan
│   │   ├── check.py         # kiwi check
│   │   ├── dashboard.py     # kiwi dashboard
│   │   ├── status.py        # kiwi status
│   │   └── upgrade.py       # kiwi upgrade
│   └── helpers.py           # output formatting, error handling, path resolution
├── pyproject.toml            # pip package (PEP 621)
└── tests/
    └── test_a6_cli.py       # 30+ checks
```

## `kiwi init` flow
```
1. Scan cwd → auto_detector.detect() → language, framework, structure
2. Create .kiwi/ folder:
   - config.json (project name, detected stack, plugin choice)
   - knowledge.db (empty SQLite — tracking ready)
3. plugin_registry.resolve_plugin(path) → load appropriate plugin
4. Run first scan → build initial lessons (if generic plugin)
5. Detect Claude Code → offer to register MCP in .claude/settings.json
6. Print summary: detected stack, loaded plugin, pattern count, next steps
```

## Command → Module mapping (zero duplication)

| Command | Reuses |
|---------|--------|
| `kiwi init` | `plugins.generic.auto_detector.detect()`, `core.plugin_registry` |
| `kiwi scan` | `scanner.cli.main()` logic, `scanner.loader`, `scanner.checkers` |
| `kiwi check` | `mcp_server._handle_check()` logic |
| `kiwi dashboard` | `tracking.dashboard.format_compact/detail()` |
| `kiwi status` | `core.tier_manager.get_tier_manager()`, `tracking.savings.get_savings()` |
| `kiwi upgrade` | `core.tier_manager.activate_license()` |

## `kiwi status` output example
```
Kiwi AI v1.0.0 — Pro tier (license)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Project: my-app (React + TypeScript)
Plugin:  generic (379 patterns loaded)
Scans:   47 today (unlimited)
Savings: $12.40 saved this week (89% reduction)
```

## pyproject.toml key fields
```toml
[project]
name = "kiwi-ai"
version = "1.0.0"
description = "AI-powered code quality scanner — learns your codebase patterns"
requires-python = ">=3.9"
dependencies = ["click>=8.0"]

[project.scripts]
kiwi = "kiwi.cli.main:cli"

[project.optional-dependencies]
dev = ["pytest"]
```

## Design decisions
1. **click over typer** — lighter (no pydantic/typing_extensions dep), sufficient for 6 commands
2. **No HTTP in A6** — CLI + MCP covers primary use case (Claude Code). HTTP server for VS Code extension is A7
3. **pyproject.toml over setup.py** — PEP 621 standard, cleaner
4. **Uninstall = `pip uninstall kiwi-ai`** — no custom command needed, standard Python packaging
5. **`.kiwi/` folder** — project-local config, gitignore-able, same pattern as `.eslintrc`

## Done khi
- [ ] `pip install -e .` works from kiwi/ directory
- [ ] `kiwi init` on fresh project creates `.kiwi/config.json` with correct detection
- [ ] `kiwi scan .` produces same output as `python -m scanner.cli --theme .`
- [ ] `kiwi check <file>` returns violations for known-bad file
- [ ] `kiwi dashboard` shows formatted metrics (or "no data" if fresh)
- [ ] `kiwi status` shows tier + pattern count + savings
- [ ] `kiwi upgrade pro --license <key>` activates license
- [ ] All commands work on Windows (PowerShell) and Unix (bash)
- [ ] `tests/test_a6_cli.py` — 30+ checks, all PASS
- [ ] A5 backward compat maintained (96/96 still pass)