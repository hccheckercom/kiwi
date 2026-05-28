# C1 — Kiwi VS Code Extension Plan

## Status

| Dependency | Status |
|------------|--------|
| C0 LSP Server | **DONE** — `lsp/` package, pygls 2.x, 4 capabilities |
| LSP Capabilities | diagnostics, code_actions, hover, didOpen/didSave/didChange |
| CLI Entry | `kiwi lsp --stdio` / `kiwi lsp --tcp --port 7892` |
| QA | 13/13 unit + 10/10 integration PASS |

C0 delivered the **server side**. C1 delivers the **client side** — a VS Code extension that spawns the LSP server and surfaces its capabilities in the IDE.

---

## Architecture

```
kiwi-vscode/
├── src/
│   ├── extension.ts           # activate/deactivate, spawn LSP client
│   ├── client.ts              # LanguageClient config (stdio transport)
│   ├── commands/
│   │   ├── viewLesson.ts      # kiwi.viewLesson — open lesson in panel
│   │   ├── scanProject.ts     # kiwi.scanProject — full project scan
│   │   └── dismissViolation.ts # kiwi.dismiss — mark false positive
│   ├── statusBar.ts           # violation count + scan status
│   └── settings.ts            # contributes.configuration mapping
├── package.json               # extension manifest + contributes
├── tsconfig.json
├── esbuild.config.mjs         # bundle for production
├── .vscodeignore
└── README.md
```

**Communication:** Standard LSP over stdio. Extension spawns `python -m kiwi.lsp` (or `kiwi lsp --stdio`) as child process. No HTTP, no WebSocket, no custom protocol.

**Key dependency:** `vscode-languageclient` ^9.x (official MS LSP client library).

---

## Phases

### Phase 1: LSP Client + Core UX [3 days]

Minimum viable extension — install and immediately get value.

**T1.1: Extension scaffold (0.5 day)**
- `package.json` with `activationEvents`, `contributes.configuration`, `contributes.commands`
- Language support: `php`, `javascript`, `typescript`, `css`, `html`
- Settings: `kiwi.severity`, `kiwi.scanOnOpen`, `kiwi.scanOnSave`, `kiwi.scanOnChange`, `kiwi.platform`, `kiwi.pythonPath`
- Activation: on language match OR `workspaceContains:**/*.php`

**T1.2: LSP Client (0.5 day)**
- Spawn `kiwi lsp --stdio` via `ServerOptions` (command + args)
- Auto-detect Python path: `kiwi.pythonPath` setting → `python3` → `python`
- Pass `initializationOptions` from VS Code settings → LSP server config
- Handle server crash/restart gracefully (max 3 restarts)
- `LanguageClient` with `documentSelector` for supported languages

**T1.3: Status Bar (0.5 day)**
- Show: `$(shield) Kiwi: 3 issues` or `$(check) Kiwi: clean`
- Click → open Problems panel filtered to source "kiwi"
- Spinner during scan, error icon if server crashed
- Update on diagnostics change event

**T1.4: Commands (0.5 day)**
- `kiwi.viewLesson` — triggered by code action "View lesson LES-XXX"
  - Opens webview panel with lesson markdown (title, why, bad/good code)
  - Fallback: open lesson file in editor if webview fails
- `kiwi.scanProject` — trigger full workspace scan (custom LSP request)
- `kiwi.restart` — kill and restart LSP server

**T1.5: Settings sync (0.5 day)**
- `onDidChangeConfiguration` → send `workspace/didChangeConfiguration` to server
- Validate Python path on activation, show error notification if missing
- Output channel "Kiwi LSP" for server logs (stderr pipe)

**T1.6: Package + Test (0.5 day)**
- esbuild bundle (single file, no node_modules in vsix)
- `.vscodeignore` to minimize package size
- Manual smoke test: open PHP project → see diagnostics → quick fix → hover
- `vsce package` produces installable .vsix

**Done criteria Phase 1:**
- [ ] Extension activates on PHP/JS/TS/CSS files
- [ ] LSP server spawns automatically, diagnostics appear as squiggly lines
- [ ] Severity mapping: CRITICAL=error (red), HIGH=warning (yellow), SUGGEST=info (blue)
- [ ] Quick fix light bulb works (from C0 code_actions)
- [ ] Hover shows lesson info (from C0 hover)
- [ ] Status bar shows violation count
- [ ] `kiwi.viewLesson` command opens lesson detail
- [ ] Settings UI works (severity filter, scan triggers, platform)
- [ ] Server crash → auto-restart (max 3)
- [ ] .vsix installs cleanly on fresh VS Code

---

### Phase 2: Enhanced UX [3 days]

Polish and power-user features.

**T2.1: Diagnostic decorations (0.5 day)**
- Gutter icons: red shield (CRITICAL), yellow triangle (HIGH), blue info (SUGGEST)
- Inline hint text after line (configurable: on/off)

**T2.2: Problem matcher integration (0.5 day)**
- Custom problem matcher for `kiwi scan` CLI output
- Tasks: `kiwi.scan` task in tasks.json template
- Terminal output links to file:line

**T2.3: File explorer decorations (0.5 day)**
- Badge on files with CRITICAL violations (red dot)
- Tooltip: "3 Kiwi violations"
- Update on diagnostics change

**T2.4: Dismiss/suppress flow (0.5 day)**
- Code action: "Kiwi: Dismiss (this file)" / "Kiwi: Dismiss (project)"
- Calls `kiwi_dismiss` via custom LSP request
- Inline comment option: `// kiwi-ignore LES-XXX`

**T2.5: Workspace scan results (0.5 day)**
- TreeView in sidebar: violations grouped by severity → file → line
- Click → navigate to violation
- Refresh button → re-scan workspace
- Filter by severity, category

**T2.6: Lesson browser (0.5 day)**
- TreeView: browse all lessons by category
- Search box: filter by keyword
- Click → open lesson detail webview
- Show which lessons triggered in current workspace

**Done criteria Phase 2:**
- [ ] Gutter icons visible for all severity levels
- [ ] File explorer shows violation badges
- [ ] Dismiss flow works (file + project scope)
- [ ] Sidebar TreeView shows grouped violations
- [ ] Lesson browser searchable
- [ ] Problem matcher works with `kiwi scan` terminal output

---

### Phase 3: Dashboard + Metrics [4 days]

Value visualization — show ROI of using Kiwi.

**T3.1: Dashboard webview (1.5 days)**
- Panel: "Kiwi Dashboard" (command: `kiwi.openDashboard`)
- Sections:
  - Scan summary: total files, violations by severity, trend chart
  - Top violations: most frequent lesson IDs
  - Fix rate: how many violations were fixed vs dismissed
  - Session stats: scans today, fixes applied
- Data source: query LSP server via custom requests (server reads SQLite memory)

**T3.2: Savings calculator (0.5 day)**
- Estimate: "Kiwi caught X bugs that would have cost Y hours to debug"
- Based on: violation count × average fix time per severity
- Show in dashboard + status bar tooltip

**T3.3: Learning progress (1 day)**
- Track: which lessons user has seen, fixed, dismissed
- Progress bar: "You've addressed 45/120 patterns in this project"
- Suggestions: "3 new patterns detected since last scan"
- Persist in workspace storage

**T3.4: Comparison mode (1 day)**
- Before/after view: show code with Kiwi fixes applied
- Diff editor integration
- "What would Kiwi catch?" — scan uncommitted changes only

**Done criteria Phase 3:**
- [ ] Dashboard opens with scan summary and trend
- [ ] Savings estimate visible
- [ ] Learning progress tracks user interaction
- [ ] Comparison mode shows before/after

---

### Phase 4: Multi-editor Support [2 days]

Extend beyond VS Code using the same LSP server.

**T4.1: Neovim config (0.5 day)**
- nvim-lspconfig snippet for `kiwi`
- Document: add to `lspconfig.lua`
- Test: diagnostics + hover + code actions work

**T4.2: JetBrains (0.5 day)**
- Document LSP setup via Settings → Languages & Frameworks → LSP
- Test with PhpStorm (primary target for WP developers)

**T4.3: Cursor/Windsurf (0.5 day)**
- Same extension works (VS Code compatible)
- Document any differences
- Test activation + diagnostics

**T4.4: Sublime Text (0.5 day)**
- LSP-kiwi package config for Sublime LSP
- Document setup

**Done criteria Phase 4:**
- [ ] Neovim: diagnostics + hover + code actions confirmed
- [ ] JetBrains: diagnostics work via LSP plugin
- [ ] Cursor: extension installs and works
- [ ] Setup docs for each editor

---

## Custom LSP Requests (server-side additions needed)

Phase 2-3 require custom LSP requests beyond standard protocol:

| Request | Purpose | Phase |
|---------|---------|-------|
| `kiwi/scanWorkspace` | Scan all files in workspace | P1 |
| `kiwi/dismiss` | Mark violation as false positive | P2 |
| `kiwi/lessonDetail` | Get full lesson content | P1 |
| `kiwi/stats` | Get scan statistics for dashboard | P3 |
| `kiwi/trends` | Get violation trends over time | P3 |

These extend the C0 server — add handlers in `server.py` using `@server.feature("kiwi/requestName")`.

---

## Distribution

| Channel | Phase |
|---------|-------|
| Manual .vsix install | P1 |
| VS Code Marketplace (free) | P2 |
| Open VSX Registry (Cursor, Codium) | P2 |
| Neovim/JetBrains docs | P4 |

**Publisher:** `wezone` (VS Code Marketplace publisher account needed)

---

## Tech Stack

| Component | Choice | Why |
|-----------|--------|-----|
| Language | TypeScript 5.x | VS Code extension standard |
| LSP Client | vscode-languageclient ^9.x | Official MS library, handles protocol |
| Bundler | esbuild | Fast, single-file output, tree-shaking |
| Webview UI | Plain HTML + CSS | No framework needed for simple panels |
| Testing | @vscode/test-electron | Official extension testing |
| Package | vsce | Official packaging tool |

---

## Risks & Mitigations

| Risk | Impact | Mitigation |
|------|--------|------------|
| Python not installed on user machine | Extension won't activate | Clear error message + link to install guide; future: bundle Python via pyinstaller |
| LSP server slow on large projects | Bad UX, editor lag | Debounce (already in C0 config), scan-on-save only by default, max_diagnostics cap |
| pygls version conflicts | Server crash | Pin pygls in pyproject.toml, test with Python 3.9-3.12 |
| VS Code API breaking changes | Extension breaks | Pin @types/vscode engine version, test on stable + insiders |
| Large lesson count (726) slows hover | Latency | Bridge caches patterns on first load, lesson lookup is O(1) by ID |

---

## Timeline

| Phase | Duration | Cumulative |
|-------|----------|------------|
| P1: LSP Client + Core UX | 3 days | 3 days |
| P2: Enhanced UX | 3 days | 6 days |
| P3: Dashboard + Metrics | 4 days | 10 days |
| P4: Multi-editor | 2 days | 12 days |

**MVP (P1):** User installs extension → opens PHP file → sees violations → clicks fix → done. Zero configuration required beyond having Python installed.

---

## Relationship to Old Plan

The previous plan (pre-C0) assumed:
- HTTP/WebSocket communication → **replaced by LSP stdio**
- Custom `kiwi serve` command → **replaced by `kiwi lsp --stdio`**
- Custom diagnostics provider in TS → **replaced by LSP diagnostics (C0)**
- Custom code actions in TS → **replaced by LSP code actions (C0)**
- React dashboard as primary feature → **deferred to P3, core UX is LSP-native**

C0 moved all intelligence server-side. C1 is now a thin client — ~500 lines of TypeScript that spawns the server and wires VS Code UI to LSP events.