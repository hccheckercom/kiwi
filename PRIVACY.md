# Kiwi — Privacy & Data Disclosure

**Last updated:** 2026-05-29
**Version:** 3.0

## Tóm tắt

Kiwi là tool local chạy trên máy bạn. Không gửi data ra ngoài (trừ khi bạn explicit configure remote sync). Học từ session log của bạn để cải thiện code suggestions, scan accuracy, và auto-fix recommendations.

---

## Data Kiwi LƯU

### 1. Session log (`memory/reasoning.db`)

- Tool calls (Read/Write/Edit + path)
- Timestamps
- Theme path + task type inference
- **KHÔNG lưu:** file content, command output, secrets

### 2. Pattern knowledge

- Function names (`wp:get_theme_mod`, `wz_component`, etc.)
- Style tokens (Tailwind class frequency)
- Hook names (`wezone_*`, custom hooks)
- **Bindings = NAMES ONLY** (không phải VALUES — verified by BUG #11 secret-leakage prevention test)

### 3. Lesson suggestions (`memory/db.sqlite`)

- Pattern (regex)
- Bad/Good code snippets (truncated 500 chars)
- Confidence + frequency
- **KHÔNG lưu:** absolute file paths, line numbers chứa secrets

### 4. Scan history (`memory/kiwi.db`)

- Violation counts theo file/lesson
- Severity trends
- False positive dismissals
- **KHÔNG lưu:** code content of violations

### 5. Confidence tracking (`memory/confidence.db`)

- Lesson IDs + confidence scores
- True/false positive ratios

---

## Data Kiwi KHÔNG lưu

- File content (chỉ extract metadata + truncated snippets)
- API keys, tokens, passwords (verified by BUG #11 secret-leakage prevention test)
- User identity, email, IP address
- Network requests, browser data
- Files ngoài `themes/`, `wezone-plugins/`, `.claude/kiwi/`
- Git commit content, branch names, remote URLs

---

## Opt-out

### Tắt hoàn toàn (per-session):

```powershell
$env:KIWI_LEARNING_DISABLED = "1"
```

### Tắt persistent:

```powershell
New-Item .claude/kiwi/memory/.learning_disabled -ItemType File
```

### Xóa data đã học:

```powershell
Remove-Item .claude/kiwi/memory/reasoning.db
Remove-Item .claude/kiwi/memory/db.sqlite
Remove-Item .claude/kiwi/memory/confidence.db
```

(scanner DB `kiwi.db` không phải learning data — chứa scan results để dedup, có thể giữ.)

### Tắt single MCP tool:

Edit `.claude/mcp.json` → remove `wezone-rag` hoặc `kiwi` server entry.

---

## Data sharing (DEFAULT: NONE)

Kiwi KHÔNG gửi data ra ngoài. Không telemetry, không analytics, không cloud sync, không phone-home.

**Future:** opt-in pattern sharing (anonymized, aggregated) sẽ có separate consent dialog. Không bao giờ enable by default.

---

## Retention

| Data | Retention |
|------|-----------|
| Session log | 30 days (auto-prune) |
| Pattern knowledge | Indefinite (manual delete) |
| Lesson suggestions | Indefinite |
| Scan history | 90 days (auto-prune) |
| Confidence scores | Indefinite |

---

## Compliance

- **GDPR:** tất cả data local, user control hoàn toàn — đáp ứng "right to access" và "right to erasure" qua file deletion
- **CCPA:** same as GDPR
- **HIPAA:** **NOT recommended** cho healthcare data — Kiwi không có encryption-at-rest by default
- **PCI-DSS:** **NOT recommended** cho payment card data — không có audit trail certified

---

## Subprocess & Network

Kiwi spawn subprocess cho:
- `python` scripts (scanner, agent, RAG indexing)
- `git` commands (changed-file detection)

Kiwi mở network connection chỉ khi:
- User explicit gọi RAG remote (default: local ChromaDB only)
- User chạy Claude API calls qua agent mode (separate consent)

---

## Audit Trail

Bug fixes liên quan privacy:
- **BUG #11** — Secret leakage prevention test (2026-05-29)
- **BUG #20** — Truncate-then-escape ngăn HTML injection
- **BUG #22** — Subprocess error capture không leak stdout content
- **BUG #25** — Pattern dedup không cross-theme leak

Xem `.claude/docs/AUDIT-REPORT-2026-05-29.md` cho full audit history.

---

## Contact

Issues: github.com/wezone/kiwi/issues
Email: privacy@wezone.vn
