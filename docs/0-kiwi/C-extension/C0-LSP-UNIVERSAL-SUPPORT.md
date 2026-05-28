# C0 — LSP Server: Universal Agent Support (1 week)

## Mục tiêu
Kiwi hoạt động với MỌI AI coding agent và IDE — không chỉ Claude Code.
LSP (Language Server Protocol) là chuẩn universal mà mọi tool đều hỗ trợ.

---

## Tại sao LSP

| Agent/IDE | MCP (hiện tại) | LSP (thêm mới) |
|-----------|----------------|-----------------|
| Claude Code | ✓ | ✓ |
| Cursor | ✗ | ✓ |
| GitHub Copilot | ✗ | ✓ |
| Cody (Sourcegraph) | ✗ | ✓ |
| Continue.dev | ✗ | ✓ |
| Aider | ✗ | ✓ |
| Windsurf | ✗ | ✓ |
| VS Code | ✗ | ✓ |
| JetBrains | ✗ | ✓ |
| Neovim | ✗ | ✓ |
| Zed | ✗ | ✓ |

**MCP = chỉ Claude Code. LSP = mọi thứ.** Thị trường mở rộng 10x.

---

## LSP Features

### Phase 1: Diagnostics (inline warnings)
```
User mở file → Kiwi scan → hiện squiggly lines cho violations
Giống ESLint nhưng powered by 400+ lessons
```

### Phase 2: Code Actions (quick fix)
```
User hover violation → "Quick Fix: Apply Kiwi suggestion"
1-click fix từ lessons
```

### Phase 3: Hover Info
```
User hover function → Kiwi hiện trust score + relevant patterns
"Trust: 0.85 | 3 known patterns for this function type"
```

### Phase 4: Completion (suggest)
```
User đang code → Kiwi suggest based on learned conventions
"Convention: this project uses camelCase for functions"
```

---

## Architecture

```
kiwi-lsp/
├── server.py                  # LSP server (pygls library)
├── capabilities/
│   ├── diagnostics.py         # Publish violations as diagnostics
│   ├── code_actions.py        # Quick fix suggestions
│   ├── hover.py               # Trust info on hover
│   └── completion.py          # Convention-based suggestions
├── bridge.py                  # Connect LSP ↔ Kiwi Core engine
└── config.py                  # LSP settings
```

**Communication:**
```
IDE/Agent ←→ LSP Protocol (stdin/stdout) ←→ Kiwi LSP Server ←→ Kiwi Core Engine
```

**Library:** `pygls` (Python LSP framework) — mature, well-documented.

---

## Tương thích với mọi agent

| Integration | Cách hoạt động |
|-------------|----------------|
| Claude Code | MCP server (giữ nguyên) + LSP (thêm mới) |
| Cursor | LSP — user add vào settings.json |
| VS Code | Extension gọi LSP server |
| JetBrains | LSP plugin (built-in support từ 2023+) |
| Neovim | nvim-lspconfig |
| Aider/Continue | LSP diagnostics feed vào context |

**User setup (1 dòng):**
```json
// VS Code settings.json
{
  "kiwi.lsp.enable": true
}

// Hoặc bất kỳ IDE nào hỗ trợ LSP:
// Command: kiwi lsp --stdio
```

---

## Tasks

### Day 1-2: Core LSP server
| # | Task |
|---|------|
| 0.1 | Setup pygls project structure |
| 0.2 | Implement textDocument/didOpen → trigger Kiwi scan |
| 0.3 | Implement textDocument/didSave → re-scan |
| 0.4 | Publish diagnostics (violations → LSP Diagnostic objects) |
| 0.5 | Test: VS Code hiện squiggly lines từ Kiwi |

### Day 3-4: Code Actions + Hover
| # | Task |
|---|------|
| 0.6 | Implement textDocument/codeAction → return fixes |
| 0.7 | Implement textDocument/hover → return trust info |
| 0.8 | Map Kiwi severity → LSP DiagnosticSeverity |
| 0.9 | Test: quick fix works in VS Code |

### Day 5: Multi-IDE testing + packaging
| # | Task |
|---|------|
| 0.10 | Test: Cursor recognizes LSP server |
| 0.11 | Test: Neovim nvim-lspconfig works |
| 0.12 | Package: `kiwi lsp --stdio` command in CLI |
| 0.13 | Documentation: setup guide per IDE |

---

## Dependencies
- A1 (core engine phải có)
- A6 (CLI phải có `kiwi lsp` command)

## Done khi
- `kiwi lsp --stdio` starts LSP server
- VS Code hiện violations inline (squiggly lines)
- Cursor hiện violations inline
- Quick fix works (1-click apply Kiwi suggestion)
- Mọi IDE hỗ trợ LSP đều dùng được Kiwi