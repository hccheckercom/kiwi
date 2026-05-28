# Kiwi Installation & Onboarding Guide (Commercial)

## Installation Methods

### Method 1: npm (Recommended — works with Claude Code)

```bash
npm install -g @kiwi-ai/cli

# Initialize in project
cd your-project
kiwi init
```

**What `kiwi init` does:**
1. Scans codebase → detects language, framework, structure
2. Creates `.kiwi/` folder (knowledge base, config)
3. Registers as MCP server in Claude Code settings
4. Runs first scan → builds initial lessons from codebase
5. Ready in ~30 seconds

### Method 2: VS Code Extension

1. Open VS Code → Extensions → Search "Kiwi AI"
2. Install → Click "Initialize" in sidebar
3. Kiwi scans workspace automatically
4. Status bar shows: "Kiwi: Learning... (32%)" → "Kiwi: Ready"

### Method 3: pip (for Python-heavy projects)

```bash
pip install kiwi-ai
kiwi init
```

---

## What Gets Installed

```
your-project/
├── .kiwi/                    # Kiwi's brain (gitignore'd)
│   ├── config.json           # Settings, API keys, preferences
│   ├── knowledge.db          # SQLite: patterns, trust, sessions
│   ├── lessons/              # Learned bug patterns
│   └── cache/                # Think cache, prefetch cache
├── .claude/settings.json     # Auto-updated: registers Kiwi MCP server
└── (your code)
```

**Size:** ~5MB initial. Grows to ~20-50MB over time (knowledge base).

---

## Onboarding Flow (First 5 Minutes)

```
$ kiwi init

  🥝 Kiwi AI — Local Intelligence for Claude

  Scanning project...
  ├── Language: PHP (WordPress theme)
  ├── Framework: Tailwind CSS
  ├── Files: 47 PHP, 12 JS, 8 CSS
  └── Structure: theme (templates + inc + assets)

  Building knowledge base...
  ├── Extracted 23 style patterns
  ├── Found 15 common bindings
  ├── Detected 8 potential issues
  └── Created 31 initial lessons

  Registering with Claude Code...
  ├── MCP server: registered ✓
  ├── Post-edit hook: installed ✓
  └── Context provider: active ✓

  ✓ Ready! Kiwi will learn from your Claude sessions automatically.

  Next steps:
  - Use Claude Code normally — Kiwi works in background
  - Run `kiwi status` to see learning progress
  - Run `kiwi dashboard` after 1 week to see savings
```

---

## Configuration (config.json)

```json
{
  "version": "1.0",
  "project": {
    "name": "my-project",
    "language": "php",
    "framework": "wordpress",
    "detected_at": "2026-05-28"
  },
  "routing": {
    "local_threshold": 0.7,
    "escalate_always": ["security", "architecture"],
    "max_local_complexity": 0.8
  },
  "learning": {
    "auto_learn": true,
    "learn_from_claude": true,
    "cross_project": false
  },
  "cost": {
    "track_savings": true,
    "monthly_budget_alert": 100
  },
  "plan": "pro"
}
```

---

## How It Integrates with Claude Code

### As MCP Server (primary)
```json
// .claude/settings.json (auto-added by kiwi init)
{
  "mcpServers": {
    "kiwi": {
      "command": "kiwi",
      "args": ["serve", "--project", "."],
      "env": {}
    }
  }
}
```

Claude Code sees Kiwi tools: `kiwi_context`, `kiwi_check`, `kiwi_reason`, etc.

### As Post-Edit Hook (quality gate)
```json
// .claude/settings.json
{
  "hooks": {
    "postToolUse": [{
      "matcher": "Write|Edit",
      "command": "kiwi check --file $FILE --severity CRITICAL"
    }]
  }
}
```

### As Context Provider (invisible to user)
- Before Claude processes any request → Kiwi injects relevant context
- Claude receives optimized brief instead of reading 50 files
- User doesn't see this — it just works

---

## CLI Commands (After Install)

```bash
kiwi status          # Show learning progress, trust scores
kiwi dashboard       # Intelligence score, cost savings
kiwi scan            # Manual full scan
kiwi check <file>    # Check single file
kiwi learn           # Force learn from recent sessions
kiwi config          # Edit settings
kiwi upgrade         # Update to latest version
kiwi export          # Export knowledge (for team sharing)
kiwi import <file>   # Import team knowledge
kiwi reset           # Reset knowledge base (start fresh)
kiwi uninstall       # Clean removal
```

---

## Team Setup (Tier 3)

```bash
# Team admin creates shared knowledge
kiwi team create "my-agency"
kiwi team invite user@email.com

# Team members join
kiwi team join "my-agency" --token <invite-token>

# Knowledge syncs automatically
kiwi team sync   # manual sync
kiwi team status # see team learning progress
```

**Sync mechanism:** 
- Local knowledge → encrypted → synced to Kiwi Cloud
- Team members pull shared patterns (not code, just patterns)
- Privacy: only patterns/rules sync, never source code

---

## Uninstall

```bash
kiwi uninstall

  Removing Kiwi...
  ├── MCP server: unregistered ✓
  ├── Hooks: removed ✓
  ├── .kiwi/ folder: deleted ✓
  └── Global CLI: removed ✓

  ✓ Kiwi removed. Your Claude Code works as before.
```

---

## Requirements

| Requirement | Minimum |
|-------------|---------|
| Node.js | 18+ |
| Python | 3.10+ (for reasoning engine) |
| Disk space | 50MB |
| OS | Windows, macOS, Linux |
| Claude Code | Any version with MCP support |

---

## Privacy & Security

- **All data stays local** (Free + Pro tiers)
- Knowledge base is in `.kiwi/` — add to `.gitignore`
- No source code leaves your machine
- Team tier: only patterns sync (encrypted), never code
- Enterprise: fully on-premise, zero cloud dependency
- API key stored in OS keychain, not plaintext

---

## Pricing Activation

```bash
# Free tier (default after install)
kiwi status
# → Plan: Free (context optimization only)

# Upgrade to Pro
kiwi upgrade pro
# → Opens browser for payment
# → After payment: "Plan: Pro — full local intelligence active"

# Team
kiwi upgrade team
# → Requires team admin setup first
```