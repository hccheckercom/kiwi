# Kiwi Commands — Hướng Dẫn Đầy Đủ

**Last updated:** 2026-05-25  
**Version:** 3.0 (Pattern Discovery Complete)

---

## 📋 Mục Lục

1. [MCP Tools (13 tools)](#mcp-tools)
2. [CLI Commands (3 commands)](#cli-commands)
3. [Pattern Discovery (3 tools)](#pattern-discovery)
4. [Deployment Framework](#deployment-framework)
5. [Knowledge Base (473 lessons)](#knowledge-base)
6. [Workflows](#workflows)
7. [Quick Reference](#quick-reference)

---

## 🔧 MCP Tools (13 tools — dùng trong Claude Code)

### 1. `kiwi_context` — Inject Rules Trước Khi Code

**Chức năng:** Đọc rules, anti-patterns, code snippets liên quan đến task  
**Khi nào dùng:** BẮT BUỘC trước khi Write/Edit bất kỳ file `.php/.css/.js/.ts/.tsx/.jsx`

```javascript
kiwi_context({
  task: "mô tả task",
  scope_type: "plugin" | "theme",
  platform: "wp" | "nextjs",
  files: ["Plugin.php", "admin.js"],  // optional
  compact: true | false,
  target_file: "path/to/file.php"     // optional — smart filtering
})
```

**Examples:**

```javascript
// Fix bug nhỏ (< 10 dòng) — compact mode
kiwi_context({
  task: "fix SQL injection in search",
  scope_type: "plugin",
  platform: "wp",
  compact: true,
  target_file: "packages/wezone-search/src/SearchController.php"
})
// → Output: ~300-600 chars, chỉ rules liên quan

// Feature mới — full context
kiwi_context({
  task: "loyalty points system",
  scope_type: "plugin",
  platform: "wp",
  compact: false,
  files: ["Plugin.php", "LoyaltyController.php"]
})
// → Output: ~6000 chars, full rules + snippets + templates
```

---

### 2. `kiwi_scan` — Scan Toàn Project/Theme

**Chức năng:** Quét toàn bộ project tìm violations theo 473 patterns  
**Output:** CRITICAL/HIGH/SUGGEST violations với file:line

```javascript
kiwi_scan({
  path: "project-name" | "path/to/theme",
  severity: "CRITICAL" | "HIGH" | "SUGGEST" | "ALL",
  platform: "wp" | "nextjs",
  scope: "theme" | "plugin",
  diff_only: true | false,
  max_per_lesson: 5
})
```

**Examples:**

```javascript
// Scan wezone-plugins (monorepo)
kiwi_scan({
  path: "wezone-plugins",
  severity: "CRITICAL",
  max_per_lesson: 3
})

// Scan only changed files (git diff)
kiwi_scan({
  path: "wezone-plugins",
  severity: "CRITICAL",
  diff_only: true
})
```

---

### 3. `kiwi_check` — Validate Single/Multiple Files

**Chức năng:** Scan 1 hoặc nhiều files sau khi edit, 0 API token  
**Khi nào dùng:** Sau mỗi Write/Edit để verify

```javascript
// Single file
kiwi_check({
  file: "path/to/file.php",
  severity: "CRITICAL" | "HIGH" | "ALL",
  platform: "wp" | "nextjs",
  compact: true  // hide clean files
})

// Multiple files (batch)
kiwi_check({
  files: ["file1.php", "file2.php", "file3.js"],
  severity: "CRITICAL",
  compact: true
})
```

---

### 4. `kiwi_fix` — Auto-Fix Violation

**Chức năng:** Preview hoặc apply fix cho violation

```javascript
kiwi_fix({
  lesson_id: "LES-XXX",
  file: "path/to/file.php",  // optional
  line: 42,                   // optional
  apply: true | false
})
```

**Examples:**

```javascript
// Preview fix (dry-run)
kiwi_fix({
  lesson_id: "LES-392",
  file: "packages/wezone-backup/src/Plugin.php",
  line: 25,
  apply: false
})

// Apply fix
kiwi_fix({
  lesson_id: "LES-392",
  file: "packages/wezone-backup/src/Plugin.php",
  line: 25,
  apply: true
})
```

---

### 5. `kiwi_query` — Search Lessons

**Chức năng:** Tìm lessons theo keyword/category/severity

```javascript
kiwi_query({
  keyword: "nonce" | "IDOR" | "mobile-first",
  category: "php-security" | "css-tokens" | "js-contract",
  severity: "CRITICAL" | "HIGH" | "SUGGEST",
  platform: "wp" | "nextjs",
  limit: 10
})
```

---

### 6. `kiwi_lesson` — Đọc Full Lesson

**Chức năng:** Đọc chi tiết lesson (Bad/Good code, Why, Grep pattern)

```javascript
kiwi_lesson({
  id: "LES-XXX" | "FEA-XXX"
})
```

---

### 7. `kiwi_add` — Thêm Lesson Mới

**Chức năng:** Tạo lesson file mới từ bug pattern

```javascript
kiwi_add({
  category: "php-security" | "css-tokens" | "js-contract" | ...,
  severity: "CRITICAL" | "HIGH" | "SUGGEST",
  title: "Short description",
  scan_type: "presence" | "absence" | "cross-check" | "bom-check",
  pattern: "regex pattern",
  scope: "**/*.php",
  tags: ["theme", "plugin"],
  bad_code: "// bad example",
  good_code: "// good example",
  why: "explanation",
  platform: "wp" | "nextjs" | "both"
})
```

---

### 8. `kiwi_stats` — Thống Kê Knowledge Base

**Chức năng:** Xem tổng quan knowledge base

```javascript
kiwi_stats()
```

**Output:**
```
Kiwi Knowledge Base — 473 patterns

Severity:
  CRITICAL   115
  HIGH       306
  SUGGEST    47
  INFO       2

Category:
  ads-compliance      16
  ai-safety           7
  concurrency         10
  css-tokens          24
  ...
```

---

### 9. `kiwi_template` — Query Template Library

**Chức năng:** Tìm code templates đã kiểm chứng

```javascript
kiwi_template({
  section: "hero" | "header" | "footer" | "product-card",
  tag: "mobile-first" | "dark-mode",
  keyword: "flash sale",
  detail: true | false  // true = full code
})
```

---

### 10. `kiwi_agent` — Autonomous Agent Loop

**Chức năng:** Scan → Analyze → Fix → Verify loop tự động

```javascript
kiwi_agent({
  path: "project-name" | "path/to/theme",
  mode: "review" | "interactive" | "auto",
  severity: "CRITICAL" | "HIGH" | "SUGGEST" | "ALL",
  max_fixes: 10
})
```

**Modes:**
- **review**: Scan only, không fix, trả report
- **interactive**: Scan, show diffs, hỏi trước khi apply
- **auto**: Scan, fix all, verify, report

---

### 11. `kiwi_dismiss` — Dismiss False Positive

**Chức năng:** Mark violation là false positive, không hiện lại

```javascript
kiwi_dismiss({
  lesson_id: "LES-XXX",
  file: "path/to/file.php",
  reason: "why this is false positive",
  scope: "file" | "project" | "global"
})
```

**Scopes:**
- **file**: Chỉ dismiss trong file này
- **project**: Dismiss trong toàn project
- **global**: Dismiss globally (mọi project)

---

### 12. `kiwi_trends` — Violation Trends

**Chức năng:** Xem trends violations theo thời gian, phát hiện regression

```javascript
kiwi_trends({
  path: "project-name" | "path/to/theme",
  days: 30
})
```

---

### 13. `kiwi_confidence` — Lesson Confidence Score

**Chức năng:** Xem confidence score của lessons (auto-disable noisy lessons)

```javascript
// Specific lesson
kiwi_confidence({
  lesson_id: "LES-XXX"
})

// Overview (noisy lessons)
kiwi_confidence({
  min_fps: 3  // min false positives
})
```

---

## 🚀 CLI Commands (3 commands — dùng trong terminal)

### 1. `kiwiscan` — Scan với Realtime Progress

```powershell
kiwiscan <path> [--severity CRITICAL|HIGH|ALL]
```

**Chức năng:** Scan theme/plugin với progress output mỗi 10 patterns  
**Alias:** `ks`

**Output:**
```
Scanning wezone-haven...
Checking 416 patterns...
  [10/416] Checked 10 patterns, 0 violations found
  [20/416] Checked 20 patterns, 1 violations found
  ...
  [410/416] Checked 410 patterns, 100 violations found

============================================================
  KIWI SMART SCANNER v3 — Violation Report
============================================================
  Theme: wezone-haven
  Patterns checked: 414
  Files scanned: 11325

  CRITICAL: 0  |  HIGH: 104  |  SUGGEST: 0
============================================================
```

**Examples:**

```powershell
# Scan theme
kiwiscan D:\projects\wezone\themes\funilux

# Scan with severity filter
kiwiscan D:\projects\wezone\themes\funilux --severity CRITICAL

# Using alias
ks D:\projects\wezone\wezone-plugins
```

---

### 2. `kiwilearn` — Learn from Folder

```powershell
kiwilearn <path> [--min-occurrences N] [--auto-approve]
```

**Chức năng:** Scan folder bất kỳ, detect 15 bug patterns, suggest lessons

**15 Built-in Detectors:**

**PHP (10):**
1. Hardcoded credentials (CRITICAL)
2. SQL injection (CRITICAL)
3. XSS risk (HIGH)
4. Missing nonce (HIGH)
5. File inclusion (CRITICAL)
6. Hardcoded URLs (HIGH)
7. Missing error handling (HIGH)
8. Deprecated functions (HIGH)
9. Inefficient loops (SUGGEST)
10. Missing sanitization (HIGH)

**JavaScript/TypeScript (5):**
11. Hardcoded API keys (CRITICAL)
12. eval() usage (CRITICAL)
13. innerHTML XSS (HIGH)
14. Missing error handling (HIGH)
15. console.log (SUGGEST)

---

### 3. `kiwi-backup` — Backup Knowledge Base

```powershell
kiwi-backup
```

**Chức năng:** Backup toàn bộ lessons + memory DB

---

## 📚 Pattern Discovery (3 tools)

### 1. `kiwi_mine_patterns` — Mine từ Scan History

**Input:** Scan history DB  
**Algorithm:** Levenshtein clustering  
**Use case:** Tìm recurring bugs across scans

```javascript
kiwi_mine_patterns({
  path: "project-name",
  min_occurrences: 5,
  lookback_days: 30,
  similarity_threshold: 0.8
})
```

**Workflow:**
```
1. Scan projects → build history
2. Mine patterns → cluster similar violations
3. Review suggestions → kiwi_review_suggestions()
4. Approve → kiwi_approve_suggestion(id)
```

---

### 2. `kiwi_learn_from_folder` — Learn từ Arbitrary Folder

**Input:** Bất kỳ folder nào (không cần scan trước)  
**Algorithm:** 15 built-in detectors  
**Use case:** Bootstrap KB, audit external code

```javascript
kiwi_learn_from_folder({
  path: "/path/to/folder",
  min_occurrences: 3,
  auto_approve: false,
  categories: ["security"]  // optional filter
})
```

**Workflow:**
```
1. Scan folder → detect 15 patterns
2. Review suggestions → kiwi_review_suggestions()
3. Approve/Reject → kiwi_approve_suggestion(id) | kiwi_reject_suggestion(id)
```

---

### 3. `kiwi_detect_anomalies` — Detect Novel Patterns

**Input:** Scan history DB  
**Algorithm:** Fingerprint matching (Jaccard similarity)  
**Use case:** Tìm zero-day patterns

```javascript
kiwi_detect_anomalies({
  lookback_days: 7
})
```

---

## 🚢 Deployment Framework

### `kiwi_deploy` — Token-Optimized Deployment

**Chức năng:** Deploy với pre-checks, health verification, auto-rollback  
**Token savings:** 65-75% reduction via git-based scan cache

```javascript
kiwi_deploy({
  path: "project-name" | "path/to/theme",
  type: "wp_theme" | "wp_plugin" | "nextjs" | "demo_html",
  target: "staging" | "production",
  mode: "dry-run" | "verify" | "execute",
  skip_scan: false,           // use cached scan if available
  rollback_on_fail: true,     // auto-rollback on health check failure
  remote_path: "/path/on/vps" // required for demo_html type
})
```

**Modes:**
- **dry-run**: Show commands only, không execute
- **verify**: Pre-checks + show plan (recommended)
- **execute**: Full deploy + health checks + rollback

**Deploy Types:**
- **wp_theme**: Deploy theme WordPress
- **wp_plugin**: Deploy plugins WordPress
- **nextjs**: Deploy Next.js app với PM2
- **demo_html**: Deploy demo HTML tĩnh (screenshot, design specs)

**Workflow:**

```javascript
// Step 1: Verify
kiwi_deploy({
  path: "themes/sfvn",
  type: "wp_theme",
  target: "staging",
  mode: "verify"
})

// Step 2: Execute
kiwi_deploy({
  path: "themes/sfvn",
  type: "wp_theme",
  target: "staging",
  mode: "execute"
})
```

**Cache Behavior:**

| Scenario | Scan behavior | Token cost |
|----------|---------------|------------|
| First deploy | Full Kiwi scan | ~3,500 tokens |
| Code unchanged | Skip scan (use cache) | ~500 tokens (90% reduction) |
| Few files changed | Scan only changed files | ~1,000 tokens (70% reduction) |

---

## 📊 Knowledge Base (473 lessons)

### Severity Distribution
- **CRITICAL:** 115 lessons (security, data loss, fatal errors)
- **HIGH:** 306 lessons (bugs, performance, UX issues)
- **SUGGEST:** 47 lessons (best practices, optimizations)
- **INFO:** 2 lessons (warnings)

### Top Categories
- **ads-compliance** (16) — Google Ads/Meta Ads policy violations
- **ai-safety** (7) — AI API security (prompt injection, cost control)
- **concurrency** (10) — Race conditions, atomic operations
- **css-tokens** (24) — Hardcoded colors/fonts, mobile-first violations
- **db-schema** (9) — Missing indexes, FK constraints
- **edge-cases** (15) — Overflow handling, empty states
- **feature-suggest** (40) — Missing features (dark mode, skeleton, a11y)
- **php-security** (92) — SQL injection, XSS, CSRF, IDOR
- **js-contract** (38) — Frontend validation, API contracts
- ... 28 more categories

---

## 🎯 Workflows

### Workflow 1: Code Mới

```javascript
// Step 1: Get context
kiwi_context({
  task: "create checkout page",
  scope_type: "theme",
  platform: "wp",
  compact: false
})

// Step 2: Write code
// ... Write/Edit files ...

// Step 3: Verify (auto-run via post_edit hook)
// Hook tự chạy kiwi_check với severity=CRITICAL

// Step 4: Manual check nếu cần
kiwi_check({
  file: "themes/funilux/wezone-templates/checkout/checkout.php",
  severity: "ALL"
})
```

---

### Workflow 2: Scan Project

```javascript
// Step 1: Scan
kiwiscan D:\projects\wezone\themes\funilux --severity CRITICAL

// Step 2: Fix violations
kiwi_fix({
  lesson_id: "LES-392",
  file: "themes/funilux/functions.php",
  line: 25,
  apply: true
})

// Step 3: Re-scan để verify
kiwiscan D:\projects\wezone\themes\funilux --severity CRITICAL
```

---

### Workflow 3: Deploy

```javascript
// Step 1: Verify
kiwi_deploy({
  path: "themes/sfvn",
  type: "wp_theme",
  target: "staging",
  mode: "verify"
})

// Step 2: Execute
kiwi_deploy({
  path: "themes/sfvn",
  type: "wp_theme",
  target: "staging",
  mode: "execute"
})
```

---

### Workflow 4: Pattern Discovery

```javascript
// Option A: Mine from scan history
kiwi_mine_patterns({
  path: "wezone-plugins",
  min_occurrences: 5,
  lookback_days: 30
})

// Option B: Learn from external folder
kiwi_learn_from_folder({
  path: "D:/downloads/suspicious-plugin",
  min_occurrences: 1,
  categories: ["security"]
})

// Step 2: Review suggestions
kiwi_review_suggestions({status: "pending"})

// Step 3: Approve/Reject
kiwi_approve_suggestion({suggestion_id: 1})
kiwi_reject_suggestion({suggestion_id: 2, reason: "Too generic"})
```

---

## 📖 Quick Reference

### MCP Tools Summary

| Tool | Chức năng | Token Cost |
|------|-----------|------------|
| `kiwi_context` | Inject rules trước code | ~300-6000 chars |
| `kiwi_scan` | Scan toàn project | 0 |
| `kiwi_check` | Verify 1/nhiều files | 0 |
| `kiwi_fix` | Auto-fix violation | 0 |
| `kiwi_query` | Search lessons | 0 |
| `kiwi_lesson` | Đọc full lesson | 0 |
| `kiwi_add` | Thêm lesson mới | 0 |
| `kiwi_stats` | Thống kê KB | 0 |
| `kiwi_template` | Query templates | 0 |
| `kiwi_agent` | Autonomous loop | High (Claude API) |
| `kiwi_dismiss` | Dismiss false positive | 0 |
| `kiwi_trends` | Violation trends | 0 |
| `kiwi_confidence` | Confidence score | 0 |

### CLI Commands Summary

| Command | Chức năng |
|---------|-----------|
| `kiwiscan <path>` | Scan với realtime progress |
| `kiwilearn <path>` | Learn 15 patterns từ folder |
| `kiwi-backup` | Backup KB + memory DB |

### Pattern Discovery Summary

| Tool | Input | Algorithm | Use Case |
|------|-------|-----------|----------|
| `kiwi_mine_patterns` | Scan history | Clustering | Recurring bugs |
| `kiwi_learn_from_folder` | Any folder | 15 detectors | Bootstrap KB |
| `kiwi_detect_anomalies` | Scan history | Fingerprinting | Novel patterns |

---

## 💡 Best Practices

1. **Luôn dùng `compact=true` cho fix nhỏ** — tiết kiệm 91% token
2. **Dùng `target_file` khi có** — chỉ trả rules liên quan
3. **Batch verify nhiều files cùng lúc** — hiệu quả hơn check từng file
4. **Dùng `diff_only=true` khi scan** — chỉ scan changed files
5. **Dismiss false positives ngay** — giúp confidence score chính xác
6. **Check hook output sau mỗi edit** — CRITICAL violations tự động block
7. **Dùng `kiwiscan` thay CLI trực tiếp** — realtime progress output

---

## 🔗 Related Documentation

- [QUICKSTART.md](../QUICKSTART.md) — 5 common use cases
- [PATTERN-MINING-GUIDE.md](../PATTERN-MINING-GUIDE.md) — Deep dive into pattern mining
- [LEARN-FROM-FOLDER-GUIDE.md](../LEARN-FROM-FOLDER-GUIDE.md) — 15 detectors guide
- [PATTERN-DISCOVERY-OVERVIEW.md](../PATTERN-DISCOVERY-OVERVIEW.md) — Decision tree
- [ARCHITECTURE.md](../../ARCHITECTURE.md) — System design

---

**Version History:**
- **3.0 (2026-05-25):** Added pattern discovery tools, realtime scan progress, 15 detectors
- **2.0 (2026-05-20):** Added deployment framework, token optimization
- **1.0 (2026-05-01):** Initial release with 13 MCP tools
