# Kiwi Quick Start Guide

5 common use cases to get started with Kiwi v2.1.

---

## 1. Scan a Project for Bugs

**Use case:** Find CRITICAL and HIGH severity violations in your WordPress theme or plugin.

```bash
# Scan with default severity (ALL)
cd .claude/kiwi
python -m scanner.cli --theme /path/to/your/theme

# Scan only CRITICAL violations
python -m scanner.cli --theme /path/to/your/theme --severity CRITICAL

# Scan WordPress plugin
python -m scanner.cli --theme /path/to/wezone-plugins --platform wp --scope plugin
```

**Via MCP (Claude Code):**
```javascript
kiwi_scan({
  path: "themes/your-theme",
  severity: "CRITICAL",
  platform: "wp"
})
```

**Output:** List of violations grouped by severity with file locations and line numbers.

---

## 2. Get Context Before Coding

**Use case:** Inject relevant rules, anti-patterns, and code snippets before writing code to avoid common bugs.

**IMPORTANT:** Always call `kiwi_context` BEFORE writing any `.php`, `.css`, `.js`, `.ts`, `.tsx`, or `.jsx` files.

```javascript
// Before creating a new plugin
kiwi_context({
  task: "Create loyalty points plugin with user balance tracking",
  scope_type: "plugin",
  platform: "wp",
  compact: false  // Full context with code examples
})

// Before fixing a small bug (saves ~70% tokens)
kiwi_context({
  task: "Fix SQL injection in search query",
  scope_type: "plugin",
  platform: "wp",
  compact: true  // Minimal context (id+title only)
})
```

**Output:** Relevant lessons, anti-patterns, code snippets, and templates for your task.

**Why this matters:** Kiwi's pre-edit hook will BLOCK file writes without context, preventing bugs before they happen.

---

## 3. Auto-Fix Violations

**Use case:** Automatically fix violations with zero-token Lite mode or Claude-powered reasoning.

**Lite Mode (0 tokens, pattern-based fixes):**
```bash
cd .claude/kiwi
python -m agent.cli --lite /path/to/theme --apply
```

**Full Agent Mode (Claude API, reasoning-based fixes):**
```bash
cd .claude/kiwi
python -m agent.cli /path/to/theme --mode auto --severity CRITICAL
```

**Via MCP (preview fix before applying):**
```javascript
// Preview fix
kiwi_fix({
  lesson_id: "LES-016",
  file: "themes/your-theme/functions.php",
  line: 42,
  apply: false
})

// Apply fix
kiwi_fix({
  lesson_id: "LES-016",
  file: "themes/your-theme/functions.php",
  line: 42,
  apply: true
})
```

**Output:** Fixed code with diff preview or applied changes.

---

## 4. Deploy with Pre-Checks

**Use case:** Deploy theme/plugin to VPS with automatic Kiwi scan, health checks, and rollback on failure.

```javascript
// Verify before deploy (dry-run + pre-checks)
kiwi_deploy({
  path: "themes/your-theme",
  type: "wp_theme",
  target: "staging",
  mode: "verify"
})

// Execute deploy (full deploy + health checks)
kiwi_deploy({
  path: "themes/your-theme",
  type: "wp_theme",
  target: "production",
  mode: "execute",
  rollback_on_fail: true
})
```

**What it does:**
1. Runs Kiwi scan (CRITICAL only)
2. Blocks deploy if violations found
3. Syncs files via rsync
4. Runs health checks
5. Auto-rollback if health checks fail

**Token savings:** 65-75% reduction via git-based scan cache.

---

## 5. Dismiss False Positives

**Use case:** Mark a violation as false positive so it won't appear in future scans.

```javascript
// Dismiss for this file only
kiwi_dismiss({
  lesson_id: "LES-020",
  file: "themes/your-theme/functions.php",
  reason: "This is a safe use of eval() for dynamic config loading",
  scope: "file"
})

// Dismiss for entire project
kiwi_dismiss({
  lesson_id: "LES-020",
  file: "themes/your-theme/functions.php",
  reason: "We use eval() safely throughout this project",
  scope: "project"
})

// Dismiss globally (all projects)
kiwi_dismiss({
  lesson_id: "LES-020",
  file: "themes/your-theme/functions.php",
  reason: "This pattern is safe in our architecture",
  scope: "global"
})
```

**What happens:**
- Violation won't appear in future scans for the specified scope
- Confidence score updated (high FP rate → lesson auto-disabled)
- Re-enable later with `kiwi_reenable({ lesson_id: "LES-020" })`

---

## Bonus: Check Confidence & Auto-Disable

**Use case:** See which lessons have high false positive rates and are auto-disabled.

```javascript
// Check confidence for specific lesson
kiwi_confidence({
  lesson_id: "LES-020"
})

// See all lessons with high FP rate (>= 3 false positives)
kiwi_confidence({
  min_fps: 3
})
```

**Auto-disable behavior:**
- Lessons with confidence < 0.2 (80% FP rate) and >= 10 hits are auto-disabled
- Disabled lessons are filtered out of scans by default
- Re-enable with `kiwi_reenable({ lesson_id: "LES-020" })`

---

## Next Steps

### Pattern Discovery Workflows

**Learn from external code:**
```javascript
// Audit downloaded plugin before installing
kiwi_learn_from_folder({
  path: "D:/downloads/plugin",
  min_occurrences: 1,
  categories: ["security"]
})
```

**Find recurring bugs:**
```javascript
// After scanning multiple projects
kiwi_mine_patterns({
  lookback_days: 30,
  min_occurrences: 5
})
```

**Review and approve patterns:**
```javascript
kiwi_review_suggestions({status: "pending"})
kiwi_approve_suggestion({suggestion_id: 1})
```

**Full guides:**
- [Pattern Discovery Overview](PATTERN-DISCOVERY-OVERVIEW.md) — Which tool to use?
- [Pattern Mining Guide](PATTERN-MINING-GUIDE.md) — Learn from scan history
- [Learn from Folder Guide](LEARN-FROM-FOLDER-GUIDE.md) — 15 built-in detectors

### More Resources

- **Full documentation:** See `.claude/kiwi/README.md`
- **Add new patterns:** Use `kiwi_add` or `kiwi_learn_from_folder`
- **Query knowledge base:** Use `kiwi_query` to search lessons
- **Detect anomalies:** Use `kiwi_detect_anomalies` to find novel patterns

**Need help?** Check `.claude/kiwi/docs/` or ask in Claude Code.
