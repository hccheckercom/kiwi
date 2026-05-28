# Kiwi VS Code Extension

Real-time code quality scanning powered by 726+ learned patterns.

## Install

```bash
code --install-extension kiwi-lsp-0.1.0.vsix
```

## Requirements

- Python 3.9+ with `pygls` and `lsprotocol` installed
- Kiwi LSP server (included in `.claude/kiwi/lsp/`)

## Features

- Inline diagnostics (squiggly lines) for code violations
- Quick fix suggestions from Kiwi lessons
- Hover info showing lesson details (why, good/bad code)
- Status bar with violation count
- Project-wide scan command

## Settings

| Setting | Default | Description |
|---------|---------|-------------|
| `kiwi.severity` | `ALL` | Minimum severity: CRITICAL, HIGH, SUGGEST, ALL |
| `kiwi.scanOnOpen` | `true` | Scan files when opened |
| `kiwi.scanOnSave` | `true` | Scan files when saved |
| `kiwi.scanOnChange` | `false` | Scan on every keystroke |
| `kiwi.platform` | `wp` | Target platform: wp, nextjs |
| `kiwi.pythonPath` | auto | Path to Python interpreter |
| `kiwi.serverPath` | auto | Path to Kiwi LSP server directory |

## Commands

- `Kiwi: Restart Server` — restart the LSP server
- `Kiwi: Scan Project` — scan all files in workspace
- `Kiwi: View Lesson` — view lesson details in panel