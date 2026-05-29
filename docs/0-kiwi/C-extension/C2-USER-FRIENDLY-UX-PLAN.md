# C2 — Kiwi Extension User-Friendly UX Plan (12 features)

> **Bổ sung cho** [KIWI-VSCODE-EXTENSION-PLAN.md](./KIWI-VSCODE-EXTENSION-PLAN.md). Plan này tập trung vào UX cho user không thích CLI.

## Context

Kiwi VSCode extension đã hoạt động ổn (LSP + diagnostics + sidebar + 3-button fix). Nhưng nhiều user team Wezone không thích CLI, cần các tính năng "ambient" (tự xuất hiện trong editor) thay vì phải nhớ command.

**Hiện trạng** (đã có):
- [statusBar.ts](../../../vscode/src/statusBar.ts) — status bar 1-tone
- [fileDecorations.ts](../../../vscode/src/providers/fileDecorations.ts) — file badge
- [gutterDecorations.ts](../../../vscode/src/providers/gutterDecorations.ts) — gutter strips
- [violationsTree.ts](../../../vscode/src/providers/violationsTree.ts) — sidebar tree
- [dashboard.ts](../../../vscode/src/providers/dashboard.ts) — dashboard webview
- 12 commands (scanProject, scanUncommitted, viewLesson, dismiss, previewFix, applyFix, copyFixContext, ...)

**Thiếu** (12 features dưới đây):

---

## TIER 1 — Quick wins, impact cao nhất (~1-2 ngày)

### [T1.1] Status Bar 3-tone

**Hiện**: `Kiwi: 3 issues` — không phân biệt severity.
**Sau**: `Kiwi 33⛔ 37⚠ 9ℹ` — partition theo `DiagnosticSeverity`.

- Click → `kiwi.openDashboard` (không phải Problems panel).
- Khi 0 violation: `Kiwi: clean ✓` xanh.
- Khi có CRITICAL: bg đỏ.
- Khi chỉ HIGH/SUGGEST: bg vàng.

File: [statusBar.ts](../../../vscode/src/statusBar.ts) — rewrite.

### [T1.2] Fix All in File

Title bar button (khi `editorLangId in [php,javascript,typescript,css,html]` và file có Kiwi diagnostics).

- Loop qua mọi violation có `good_code` → call `kiwi/applyFix` → apply qua `WorkspaceEdit` (1 atomic edit).
- Confirm 1 lần: "Apply 12 auto-fixes?".
- Skip violations không có template → báo "8 fixed, 4 cần manual".

File mới: [fixAllInFile.ts](../../../vscode/src/commands/fixAllInFile.ts).

### [T1.3] Search Lessons Palette

`Ctrl+Shift+P → Kiwi: Search Lessons` → quickpick fuzzy theo title/category/id.

- Server: LSP endpoint `kiwi/searchLessons` filter substring trên `bridge._ensure_patterns()`.
- Click → `kiwi.viewLesson(id)` (đã có).

File mới: [searchLessons.ts](../../../vscode/src/commands/searchLessons.ts).

### [T1.4] CodeLens "Apply Fix · Copy · Why"

Hiện 3 lens trên dòng vi phạm:
- 💡 Apply Fix → `kiwi.applyFix({lessonId, uri, range})`
- 📋 Copy Context → `kiwi.copyFixContext(...)`
- ❓ Why? → `kiwi.viewLesson(lessonId)`

Listen `vscode.languages.onDidChangeDiagnostics`. Cap 50 lens/file, throttle 500ms.

File mới: [codeLens.ts](../../../vscode/src/providers/codeLens.ts).

---

## TIER 2 — Trust & retention (~2-3 ngày)

### [T2.1] Confidence Badge trong Tree

Tree item description hiện thêm `92%` xanh / `45%` vàng / `<30%` xám.

- Server: LSP endpoint `kiwi/lessonConfidence` → returns `{lesson_id: score}` từ table `lesson_confidence`.
- Cache server-side, refresh 60s.

File: [violationsTree.ts](../../../vscode/src/providers/violationsTree.ts) — modify.

### [T2.2] Side-by-side Diff cho Preview Fix

Thay webview HTML bằng `vscode.diff(originalUri, fixedUri, title)`.

- URI scheme `kiwi-preview-{uuid}:` với `TextDocumentContentProvider` trả về file content đã apply `good_code`.
- User accept/reject từng hunk như git diff.

File: [previewFix.ts](../../../vscode/src/commands/previewFix.ts) — rewrite.

### [T2.3] Add Lesson from Selection

Right-click code → `Kiwi: Add Lesson from Selection`:
- Multi-step quickpick: title → severity → category → why.
- Pre-fill `bad_code` = selection, `pattern` = regex-escape preview.
- Server: `kiwi/addLesson` → subprocess `python tools/add.py`.
- Sau add → `bridge.invalidate_patterns()` + `kiwi.refreshViolations`.

File mới: [addLessonFromSelection.ts](../../../vscode/src/commands/addLessonFromSelection.ts).

### [T2.4] Templates Library Sidebar

View thứ 2 trong activity bar Kiwi: `kiwiTemplates`.
- Tree theo section: header / hero / footer / product-card.
- Click template → insert vào cursor.
- Server: `kiwi/listTemplates` → call `templates/tools/query.py`.

File mới: [templatesTree.ts](../../../vscode/src/providers/templatesTree.ts).

---

## TIER 3 — Power user (~2-3 ngày)

### [T3.1] Trends Chart Panel

Webview với SVG line chart 30 ngày từ `scan_history`.
- Server: `kiwi/trends` (params: `days`).
- Regression alert khi violation tăng > 20%.

File mới: [trendsPanel.ts](../../../vscode/src/providers/trendsPanel.ts).

### [T3.2] Auto-scan on Git Status Change

Setting `kiwi.autoScanOnGitChange` (default false).
- Watch `**/.git/index` qua `createFileSystemWatcher`.
- Debounce 2s → call `kiwi.scanUncommitted`.

File: [extension.ts](../../../vscode/src/extension.ts) — modify.

### [T3.3] Agent Mode UI

`Kiwi: Run Agent` → quickpick mode (`review` / `interactive` / `auto`).
- `vscode.window.withProgress` + `child_process.spawn` + `cancellationToken`.
- Stream stdout vào output channel.
- 5min timeout, cancel → `child.kill()`.

File mới: [runAgent.ts](../../../vscode/src/commands/runAgent.ts).

### [T3.4] Welcome Walkthrough

5-step trong `package.json` `contributes.walkthroughs`:
1. Open PHP file → see diagnostics
2. Hover violation
3. Click fix in CodeLens
4. Open dashboard
5. Configure severity

File mới: [walkthroughs/getting-started.md](../../../vscode/walkthroughs/getting-started.md).

---

## Critical files

| File | Loại | Mục đích |
|------|------|----------|
| [server.py](../../../lsp/server.py) | Modify | 5 endpoints: searchLessons, lessonConfidence, addLesson, listTemplates, trends |
| [bridge.py](../../../lsp/bridge.py) | Modify | Helper search/list templates |
| [statusBar.ts](../../../vscode/src/statusBar.ts) | Rewrite | 3-tone breakdown |
| [violationsTree.ts](../../../vscode/src/providers/violationsTree.ts) | Modify | Confidence badge |
| [previewFix.ts](../../../vscode/src/commands/previewFix.ts) | Rewrite | Diff editor |
| [extension.ts](../../../vscode/src/extension.ts) | Modify | Register CodeLens, templates tree, file watcher |
| [package.json](../../../vscode/package.json) | Modify | 8 commands + menus + walkthroughs + view kiwiTemplates |
| commands/* (new) | New | fixAllInFile, searchLessons, addLessonFromSelection, runAgent |
| providers/* (new) | New | codeLens, templatesTree, trendsPanel |
| walkthroughs/* (new) | New | Markdown step files |

## Reuse existing utilities

- LSP `kiwi/applyFix` + `kiwi/getFixContext` — Fix All loop sử dụng.
- LSP `kiwi/lessonDetail` — CodeLens "Why?" + Search palette.
- `bridge.get_lesson_info()`, `bridge._ensure_patterns()` — search source.
- `memory/confidence.py` — confidence badge query.
- `vscode.languages.getDiagnostics()` — status bar + CodeLens listener.
- `tools/add.py`, `templates/tools/query.py` — subprocess endpoints.

## Implementation order (3 commits)

1. **Tier 1**: status bar 3-tone, Fix All, Search palette, CodeLens.
2. **Tier 2**: confidence badge, diff editor, add lesson UI, templates sidebar.
3. **Tier 3**: trends chart, git auto-scan, agent UI, walkthrough.

Sau mỗi commit:
```powershell
Set-Location "d:\projects\wezone\.claude\kiwi\vscode"
npm run build
npx vsce package --allow-missing-repository --no-dependencies
code --install-extension "kiwi-lsp-0.1.0.vsix" --force
```

## Verification

### Tier 1 acceptance
- Status bar `33⛔ 37⚠ 9ℹ` đúng count.
- Click status bar → dashboard mở.
- File 5 violations → 5 cụm CodeLens 3-button.
- `Ctrl+Shift+P → Kiwi: Search Lessons` → gõ "sql" → list.
- "Fix All in File" → confirm "Apply 12?" → 1 atomic edit.

### Tier 2 acceptance
- Tree badge `92%` / `45%` / xám đúng confidence.
- Preview Fix mở diff editor side-by-side.
- Add Lesson → file mới trong `lessons/{category}/`.
- Templates tab → click → insert vào cursor.

### Tier 3 acceptance
- Trends panel SVG chart 30 ngày.
- `kiwi.autoScanOnGitChange` → `git add .` → 2s sau scan.
- `Kiwi: Run Agent` → progress + cancel.
- Walkthrough auto-open lần đầu.

## Risks

| Risk | Mitigation |
|------|------------|
| CodeLens spam | Cap 50 lens/file, throttle 500ms |
| Diff URI conflict | Prefix `kiwi-preview-{uuid}:` |
| Agent hang | `cancellationToken` + 5min timeout |
| Walkthrough interrupt | Auto-open lần đầu (`globalState`) |
| Confidence query slow | Server cache 60s |
| Git watcher fire nhiều | Debounce 2s |
| addLesson Windows path bug | Spawn args array, escape, log stderr |

## Out of scope

- i18n (Vietnamese UI strings).
- Cloud sync confidence/dismiss.
- Inline AI chat.
- Mobile companion.
- Marketplace publish.
