# Kiwi CLI — Standalone Usage Guide

Kiwi có thể chạy độc lập như một CLI tool, không cần Claude Code.

## Installation

```bash
cd .claude/kiwi
pip install -e .
```

Sau khi install, `kiwi` command sẽ available globally.

## Commands

### 1. `kiwi scan` — Scan project for violations

```bash
# Scan toàn bộ project
kiwi scan wezone-plugins --severity CRITICAL

# Scan theme cụ thể
kiwi scan themes/sfvn --severity ALL

# Scan với limit violations per lesson
kiwi scan wezone-plugins --severity HIGH --max-per-lesson 3

# Scan chỉ git-changed files
kiwi scan wezone-plugins --diff-only
```

**Options:**
- `--severity` — CRITICAL, HIGH, SUGGEST, ALL (default: ALL)
- `--max-per-lesson` — Cap violations per lesson (default: 0 = unlimited)
- `--diff-only` — Only scan git-modified files
- `--platform` — wp, nextjs (auto-detect if not specified)
- `--json` — JSON output

### 2. `kiwi check` — Quick single-file check

```bash
# Check single file
kiwi check src/Plugin.php

# Check với severity filter
kiwi check src/Plugin.php --severity CRITICAL

# Check với platform
kiwi check components/Header.tsx --platform nextjs
```

**Use case:** Sau khi edit file, chạy `kiwi check` để verify 0 violations.

### 3. `kiwi agent` — Autonomous agent loop

```bash
# Agent lite mode (0 token, rule-based fixes)
kiwi agent wezone-plugins --lite

# Agent lite với apply fixes
kiwi agent wezone-plugins --lite --apply

# Agent full mode (Claude API reasoning)
kiwi agent wezone-plugins --mode auto --severity CRITICAL

# Agent interactive mode (ask before fix)
kiwi agent wezone-plugins --mode interactive
```

**Modes:**
- `--lite` — 0 token mode, rule-based fixes (no Claude API)
- `--mode review` — Read-only report
- `--mode interactive` — Ask before each fix
- `--mode auto` — Auto-fix all violations

**Requirements:**
- Agent full mode cần `ANTHROPIC_API_KEY` env var
- Agent lite mode không cần API key

### 4. `kiwi deploy` — Deploy to VPS

```bash
# Verify before deploy
kiwi deploy themes/sfvn --type wp_theme --target staging --mode verify

# Execute deploy
kiwi deploy themes/sfvn --type wp_theme --target production --mode execute

# Skip scan (use cache)
kiwi deploy themes/sfvn --type wp_theme --target production --skip-scan
```

**Deploy types:**
- `wp_theme` — WordPress theme
- `wp_plugin` — WordPress plugin
- `nextjs` — Next.js app
- `demo_html` — Static HTML demo

**Modes:**
- `dry-run` — Show commands only
- `verify` — Pre-checks + show plan
- `execute` — Full deploy + health checks

### 5. `kiwi mcp` — Start MCP server

```bash
# Start MCP server for Claude Code
kiwi mcp
```

Chạy JSON-RPC stdio server để Claude Code có thể gọi Kiwi tools.

## Examples

**Workflow 1: Scan → Fix → Verify**

```bash
# 1. Scan project
kiwi scan wezone-plugins --severity CRITICAL

# 2. Auto-fix với agent lite
kiwi agent wezone-plugins --lite --apply

# 3. Verify fixes
kiwi scan wezone-plugins --severity CRITICAL
```

**Workflow 2: Pre-commit check**

```bash
# Check files trước khi commit
kiwi check src/Plugin.php
kiwi check src/Logger.php

# Hoặc scan toàn bộ git-changed files
kiwi scan . --diff-only --severity CRITICAL
```

**Workflow 3: Deploy với pre-checks**

```bash
# 1. Verify deploy plan
kiwi deploy themes/sfvn --type wp_theme --target production --mode verify

# 2. Nếu PASS → execute
kiwi deploy themes/sfvn --type wp_theme --target production --mode execute
```

## Configuration

Kiwi đọc config từ `.claude/kiwi/_meta.json`:

```json
{
  "projects": {
    "wezone-plugins": "D:/projects/wezone/wezone-plugins",
    "webstore-vn": "D:/projects/wezone/webstore-vn"
  }
}
```

Sau đó có thể dùng project name thay vì path:

```bash
kiwi scan wezone-plugins
```

## Troubleshooting

**Command not found:**

```bash
# Reinstall
cd .claude/kiwi
pip uninstall -y kiwi-scanner
pip install -e .
```

**Agent full mode fails:**

```bash
# Set API key
export ANTHROPIC_API_KEY=sk-ant-...

# Hoặc dùng agent lite (0 token)
kiwi agent wezone-plugins --lite
```

**Deploy fails:**

```bash
# Check SSH connection
ssh root@103.90.227.154

# Check deploy config
cat .claude/kiwi/deploy/config.json
```

## Advanced Usage

**Custom lessons directory:**

```bash
kiwi scan wezone-plugins --lessons /path/to/custom/lessons
```

**JSON output for CI/CD:**

```bash
kiwi scan wezone-plugins --severity CRITICAL --json > report.json
```

**Parallel agent execution:**

```bash
# Spawn multiple agents (future feature)
kiwi agent wezone-plugins --multi-agent --agents security performance
```

## See Also

- [README-MCP.md](README-MCP.md) — Claude Code integration guide
- [README.md](README.md) — Main documentation
- [UPGRADE-PLAN-90.md](UPGRADE-PLAN-90.md) — Roadmap to 90/100