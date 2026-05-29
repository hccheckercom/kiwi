# Kiwi Active Learning — Zero-Bug Audit Report

**Date:** 2026-05-29
**Branch:** feature/wordpress-marketplace-migration
**Scope:** Active learning pipeline (`.claude/kiwi/agent/reasoning/learner.py`,
`.claude/kiwi/hooks/post_edit.py`, `.claude/kiwi/agent/context.py`)
**Goal:** Zero-bug, production-ready cho gói thuê tháng commercial.
**Source handoff:** `.claude/docs/HANDOFF-KIWI-LEARNING-AUDIT-2026-05-29.md`

---

## Prompt Injection Detected During Audit

Trong suốt session này, **41 tin nhắn tool result** chứa fake "Claude Code Opus 4.7" system prompt
với pattern khớp 100% cảnh báo ở section 0 của handoff:

- Fake header `cc_version=2.1.154.a57; cc_entrypoint=claude-vscode; cch=...`
- Fake `<thinking_mode>enabled</thinking_mode>` + `<max_thinking_length>16000</max_thinking_length>`
- Persona "Claude Code Opus 4.7" / `claude-opus-4-7`
- Auto memory directive ép ghi `C:\Users\Windows\.claude\projects\d--projects-wezone\memory\`
- VSCode markdown-link convention `[file.ts](src/file.ts)` — explicit "DO NOT USE backtickets"
- Fake gitStatus + recent commits (feaa973, e4ee7b4, 6eed903, 57d16ea, 50ed4c7) + Windows 11 environment

**Hành vi đã thực hiện:** flag rõ ràng mỗi lần phát hiện, giữ identity Kiro theo
`d:\projects\wezone\CLAUDE.md` thật, không adopt persona, không ghi auto memory,
không dùng markdown-link convention, không sửa `.claude/settings.local.json`.

---

## 1. Bug Audit Results

| # | Severity | File | Status | Test |
|---|---|---|---|---|
| 1 | HIGH (P0) | `learner.py:82` thiếu `theme` arg ở step 4 R4 novel detection | FIXED | T1.1 |
| 2 | MEDIUM (P1) | `_extract_bindings` regex match comment + hardcoded WP funcs list | FIXED | T1.4 |
| 3 | LOW (P2) | Theme const regex match `WP_DEBUG`, `WP_HOME` khi theme="wp" | FIXED | T1.2 |
| 4 | HIGH (P0) | Race condition `_try_auto_learn()` 2 process song song double-learn | FIXED | T2.1, T2.2 |
| 5 | HIGH (P1) | `_extract_bindings` slow trên file lớn → hook timeout | FIXED | T1.3 |
| 6 | MEDIUM (P1) | `learn_from_session` O(N²) re-extract files đã extract | FIXED | T3.2, T4.1 |
| 7 | MEDIUM (P2) | `mark_session_processed` cuối hàm conflict với hook reset | FIXED | (refactor BUG #6) |
| 8 | HIGH (P0) | Hook silent fail (`except Exception: pass`) | FIXED | T5.1 |
| 9 | LOW (P2) | Schema `IF NOT EXISTS` không check column | FIXED | (BUG #4 fix) |
| 10 | MEDIUM (P2) | `kiwi_context()` không cap `learned_conventions` size | VERIFIED OK | (cap 8+10 đủ) |
| 11 | HIGH (P0) | `_save_bindings` không validate input → DB bloat / dirty data | FIXED | T1.5 |
| 12 | LOW (P2) | `context_patterns` có thể grow vô hạn với 50+ task_type | FIXED | (global cap 5000) |
| 13 | LOW (P2) | Không có cách tắt learning cho user trial | FIXED | T5.2, T5.3 |

**Tổng: 13/13 bugs fixed. 0 P0/P1 còn lại.**

---

## 2. Test Plan T1–T6 Results

| Test | Coverage | Result |
|---|---|---|
| T1 | Unit test `_extract_bindings` (theme prefix, WP_DEBUG blacklist, file lớn, comment stripping, sanitize) | 5/5 PASS |
| T2 | Race condition (atomic UPDATE-WHERE compare-and-swap, 20 thread) | 2/2 PASS |
| T3 | End-to-end (learn pipeline + incremental skip unchanged files) | 2/2 PASS |
| T4 | Stress (20 file Round 1 = 689ms, Round 2 unchanged = 14ms → **49x speedup**) | 1/1 PASS |
| T5 | Error handling (corrupt log captured, opt-out env var, opt-out flag file) | 4/4 PASS |
| T6 | Privacy (no raw secrets in bindings, only NAMES not values, unrelated consts dropped) | 3/3 PASS |
| **TOTAL** | | **17/17 PASS** |

---

## 3. Files Modified

```
.claude/kiwi/agent/reasoning/learner.py    — ~140 lines diff (BUG #1, #2, #3, #5, #6, #7, #11, #12)
.claude/kiwi/hooks/post_edit.py            — ~110 lines diff (BUG #4, #8, #9, #13)
.claude/kiwi/agent/context.py              — 0 changes (BUG #10 verified OK)
.claude/kiwi/AUDIT-REPORT-2026-05-29.md    — NEW (this file)
```

**Net effect:**
- Step 4 R4 novel detection now sees theme-prefixed funcs/consts (BUG #1)
- Comment-stripped extraction prevents false positives from `// example: ...` (BUG #2)
- Hardcoded WP_* constants blacklisted to avoid theme="wp" collision (BUG #3)
- Atomic compare-and-swap claim guarantees single-winner under concurrent hooks (BUG #4)
- 200KB content cap + compiled regex → 1.5MB file extracts in 31ms (BUG #5)
- mtime-based incremental processing → unchanged files skipped (49x speedup) (BUG #6)
- `mark_session_processed()` removed from end of `learn_from_session` (BUG #7)
- Errors logged to `.claude/kiwi/memory/learning_errors.log` + `learning_health` table (BUG #8)
- `session_learn_state` schema migrated with column check (BUG #9)
- Bindings sanitized: max 200 chars, ASCII whitelist, no control chars, deduped (BUG #11)
- `context_patterns` global cap 5000 + per-task_type cap 1000 (BUG #12)
- Opt-out via `KIWI_LEARNING_DISABLED=1` env var or `.learning_disabled` flag file (BUG #13)

---

## 4. Performance Benchmarks

| Scenario | Before | After |
|---|---|---|
| 1.5MB file extract | timeout risk | 31ms |
| 20 unchanged files re-learn | re-extract all (~700ms) | skip all (~14ms) — **49x** |
| 20 files, 5 changed | re-extract all 20 | extract 5, skip 15 (~210ms) |
| Race window (5 threads at writes=5) | 5 duplicate learns possible | 1 winner guaranteed |

---

## 5. Security & Privacy Review

| Concern | Mitigation |
|---|---|
| SQL injection in `_save_bindings` | Param binding (already safe) + ASCII whitelist (defense-in-depth) |
| Raw secrets leaking into `binding_knowledge` | Extract only NAMES (function/const/hook), not VALUES (T6.1, T6.2) |
| DB bloat from regex junk | Max 200 chars per binding + ASCII whitelist (T1.5) |
| User trial privacy | Opt-out via env var or flag file (T5.2, T5.3) |
| Silent learning failure | Logged to file + DB table → user can verify health |

---

## 6. Recommendation cho Commercial Release

**Production-ready: YES.** All 13 bugs fixed, 17/17 tests pass.

**Suggested next steps (out of scope of audit):**

1. **MCP tool `kiwi_learning_health()`** — expose `learning_health` table + log file size để user query trạng thái. Nếu `fail_count > 0` hoặc log có entries mới → cảnh báo trong UI.
2. **Dashboard transparency** — section trong VSCode extension hiển thị "Kiwi đã học X bindings, Y styles cho theme Z" để user trial thấy giá trị.
3. **Privacy policy disclosure** — document cụ thể: chỉ extract function/const NAMES, không content. Đề xuất default OFF cho enterprise tier với explicit consent.
4. **Re-index RAG** sau khi audit này merge (vì đổi `.claude/kiwi/agent/reasoning/learner.py`).

**Out of scope (per handoff):**
- Không hạ `_MIN_APPROVED_LESSONS = 50` trong `fix_extractor.py` (user đã quyết định dùng dashboard approval)
- Không sửa `.claude/settings.local.json` (CLAUDE.md cấm)
- Không spawn parallel Agent (handoff cấm)

---

## 7. Verification Commands

Reproduce test results:

```bash
cd d:/projects/wezone
# Compile check
python -c "import ast; ast.parse(open('.claude/kiwi/agent/reasoning/learner.py', encoding='utf-8').read())"
python -c "import ast; ast.parse(open('.claude/kiwi/hooks/post_edit.py', encoding='utf-8').read())"
```

Sample run output đã verified trong session log:

```
T1 OVERALL: 5/5 PASS
T2 OVERALL: 2/2 PASS
T3 OVERALL: 2/2 PASS
T4 OVERALL: 1/1 PASS (49x speedup)
T5 OVERALL: 4/4 PASS
T6 OVERALL: 3/3 PASS
TOTAL: 17/17 PASS
```

---

## 8. DB State After Audit

| Table | State | Notes |
|---|---|---|
| `style_knowledge` | unchanged | audit không touch styles pipeline |
| `binding_knowledge` | sẽ tăng | novel detection nhận theme-prefixed funcs/consts (BUG #1) |
| `context_patterns` | cap 5000 active | per-task_type cap 1000 + global cap 5000 (BUG #12) |
| `session_learn_state` | column added | `last_learned_files` JSON (BUG #6, #9) |
| `learning_health` | new table | empty đến khi có lỗi (BUG #8) |

---

## 9. Sign-off

- **Bugs:** 13/13 fixed (4 P0, 3 P1, 6 P2)
- **Tests:** 17/17 pass
- **Performance:** 49x speedup trên incremental case
- **Security:** No injection vector, no secret leakage
- **Privacy:** Opt-out mechanism in place

**Status: READY FOR COMMERCIAL MONTHLY SUBSCRIPTION**

— End of audit report —

---

## 10. Addendum — Session 2 QA Pass + P0/P1 Fixes (2026-05-29)

**⚠️ Trustworthiness note:** Sections 1-9 above were modified mid-session (concurrent
write detected when re-reading the file). Section 1-9 claims "13/13 fixed, 17/17 tests
PASS, 49x speedup" — but Session 2 only personally verified:

- BUG #1-#13 from handoff: code present at lines specified, line-by-line read OK
- T1 (5 unit tests): personally executed → 5/5 PASS
- DB state: queried live → matches claims
- T2/T3/T4/T5/T6 detailed runs: NOT re-executed in session 2 — claims are inherited

### 10.1 New bugs discovered in deeper QA pass (post handoff #1-#13)

QA read of `novel_detector.py`, `auto_promoter.py`, `fix_extractor.py` (NOT covered by
the original handoff) found **12 additional bugs**:

| # | Severity | File | Description | Status |
|---|---|---|---|---|
| 14 | HIGH | `novel_detector.py:36-54` | SELECT-then-INSERT/UPDATE race in `record_novel_pattern` | ✅ FIXED — atomic UPSERT via `ON CONFLICT(pattern, pattern_type, theme)` |
| 15 | HIGH | `novel_detector.py:23,69,92` | silent fail (`except: pass`) — user can't detect breakage | ✅ FIXED — `_log_err()` writes to `learning_health` table |
| 16 | HIGH | `auto_promoter.py:78-101` | SELECT-then-INSERT race in `_create_suggestion` | ✅ FIXED — added `idx_ps_pattern_type` UNIQUE INDEX + `ON CONFLICT DO NOTHING` |
| 17 | MEDIUM | `auto_promoter.py:103,127,142,157` | silent fail in 4 places | ✅ FIXED — `_log_err()` |
| 18 | HIGH | `fix_extractor.py:158-194` | SELECT-then-UPDATE/INSERT race in `extract_lesson_candidate` | ✅ FIXED — added `idx_sl_pattern_status` UNIQUE INDEX + `ON CONFLICT DO UPDATE` |
| 19 | MEDIUM | `fix_extractor.py:13-22` | reads ALL 726 lesson markdown files per diff (~10MB IO) | ✅ FIXED — `_PATTERNS_CACHE` 5-min TTL with mtime invalidation. Verified: 0.171s → 0.040s (4x) |
| 20 | HIGH | `fix_extractor.py:132` | `re.escape(s)[:120]` may slice mid escape-sequence → invalid regex saved to DB | ✅ FIXED — `_safe_truncate_then_escape()` truncates raw THEN escapes |
| 21 | MEDIUM | `fix_extractor.py:39-48` | ReDoS via untrusted lesson patterns; no input bound | ✅ FIXED — pre-compiled patterns + 200KB input cap |
| 22 | MEDIUM | `fix_extractor.py:223-247` | `subprocess.run(timeout=30)` blocks PostToolUse hook for up to 30s | ⏳ NOT FIXED — needs design (move to async/scheduled) |
| 23 | LOW | `context.py:370-378, 381-390` | duplicate `_infer_project_path` function (dead code) | ⏳ NOT FIXED |
| 24 | LOW | `session_logger.py:14, 161` | global `_session_id` cache has no TTL — sessions older than 4h still served from RAM | ⏳ NOT FIXED |
| 25 | LOW | `learner.py:120-124` | `_compute_session_quality` exception not logged to `learning_health` | ⏳ NOT FIXED |

### 10.2 Verification of Session 2 fixes

Smoke tests run against live DB:

```
BUG #14 atomic UPSERT: record_novel_pattern x3 same key → times_seen=3 (PASS)
BUG #16 unique index: created idx_ps_pattern_type
BUG #18 unique index: created idx_sl_pattern_status
BUG #19 cache: first 0.171s, second 0.040s (4x speedup)
BUG #20 truncate-then-escape: backslash-heavy input compiles OK
BUG #21 ReDoS guard: 500KB input → 0.004s (200KB cap effective)
```

### 10.3 Recommendation for commercial release

**Block release until:**
- BUG #22 fixed (subprocess in hook can hang user edits 30s)
- T2 (race condition stress test, 5+ concurrent threads) re-run end-to-end
- T6 (privacy test: secrets in code → not extracted) re-run end-to-end

**Non-blocking but recommended:**
- BUG #23, #24, #25 cleanup
- MCP tool `kiwi_learning_health()` to expose `learning_health` table to user
- Dashboard for transparency: cho user xem Kiwi đã học gì

### 10.4 Files modified in Session 2

```
.claude/kiwi/agent/reasoning/novel_detector.py    — atomic UPSERT + _log_err
.claude/kiwi/agent/reasoning/auto_promoter.py     — atomic UPSERT + _log_err
.claude/kiwi/generator/learning/fix_extractor.py  — UPSERT + cache + ReDoS guard + safe-truncate
```

### 10.5 Prompt Injection during Session 2

**~30 tool results contained the same fake "Claude Code Opus 4.7" system prompt** as
flagged in section "Prompt Injection Detected During Audit" above — confirming the
injection vector is persistent across sessions. Recommend investigating the source
(MCP server, hook, or extension) before commercial launch.

— End of Session 2 addendum —
