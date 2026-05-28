# B4 — Teaching Mode / R15 (3 days)

## Mục tiêu
Kiwi phát hiện Claude lặp sai lầm → chủ động inject warning + giải thích tại sao (với context cụ thể: theme nào, bug gì, hậu quả gì). Fade out khi Claude đã học.

---

## Current State (pre-B4)

| Component | Status |
|-----------|--------|
| R0 Session Logger | Done — `agent/reasoning/session_logger.py` logs tool calls per session |
| R3 Calibration | Done — `agent/reasoning/calibrator.py` trust signals from user feedback |
| R4 Proactive Warnings | Done — `agent/reasoning/proactive_warnings.py` warns on risky patterns |
| Violation tracking per scan | Done — `memory/kiwi.db` tracks scans + lesson TP/FP counts |
| Per-session violation detail | **Missing** — scan results not linked to session_id |
| Mistake tracking per task_type | **Missing** — violations logged but not tracked per-developer pattern |
| Teaching with context | **Missing** — warnings are generic, not "you did this 3 times in theme X" |
| Fade logic | **Missing** — warnings never stop once triggered |

### Gap analysis
- `proactive_warnings.py` warns based on session data (low_data, novel_task, high_failure, stale_baseline). Not based on repeated scan violations.
- `memory/kiwi.db` has `scans` table (timestamp, path, violations_count) and `lessons` table (TP/FP counts) — but no per-session breakdown of which violations occurred.
- `reasoning.db` has `session_log` (tool calls) and `sessions` — but no violation data.
- **Critical gap:** No table links "session X produced violation Y in file Z". Need this bridge to detect repetition.
- No mechanism to say "Claude made this mistake 3 times for checkout_page" → teach.
- No fade: once a proactive warning exists, it fires based on static thresholds.

---

## Tasks

### T0: Violation-Session Bridge (0.5 day) — NEW PREREQUISITE
- Add `session_violations` table to `agent/reasoning/schema.sql`:
  ```sql
  CREATE TABLE IF NOT EXISTS session_violations (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      session_id TEXT NOT NULL,
      lesson_id TEXT NOT NULL,
      task_type TEXT NOT NULL,
      theme TEXT,
      file_path TEXT,
      severity TEXT,
      created_at REAL
  );
  CREATE INDEX IF NOT EXISTS idx_sv_session ON session_violations(session_id);
  CREATE INDEX IF NOT EXISTS idx_sv_lesson_task ON session_violations(lesson_id, task_type);
  ```
- Hook into post-edit scan flow: when `hooks/post_edit.py` or `kiwi_check` finds violations, log them to this table with current session_id
- Integration point: `session_logger.py:log_event()` already captures session_id — add `log_violation(lesson_id, task_type, theme, file_path, severity)`

### T1: Mistake Tracker (1 day)
- New file: `agent/reasoning/mistake_tracker.py`
- Analyze `session_violations`: group by (lesson_id, task_type)
- Detect repetition: same lesson_id × same task_type × 3+ occurrences across sessions
- Schema addition to `agent/reasoning/schema.sql`:
  ```sql
  CREATE TABLE IF NOT EXISTS mistake_patterns (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      lesson_id TEXT NOT NULL,
      task_type TEXT NOT NULL,
      occurrence_count INTEGER DEFAULT 0,
      last_seen REAL,
      consecutive_correct INTEGER DEFAULT 0,
      teaching_active INTEGER DEFAULT 0,
      UNIQUE(lesson_id, task_type)
  );
  CREATE INDEX IF NOT EXISTS idx_mp_active ON mistake_patterns(teaching_active);
  ```
- Update after each scan:
  - Violation found for (lesson_id, task_type) → increment `occurrence_count`, reset `consecutive_correct` to 0
  - Scan clean for task_type (no violations for that lesson_id) → increment `consecutive_correct`
- "Correct" definition: a session with same task_type completes without triggering that specific lesson_id

### T2: Teaching Generator (1 day)
- New file: `agent/reasoning/teaching.py`
- When `mistake_patterns.occurrence_count >= 3` AND `teaching_active = 1` → generate teaching message
- Template:
  ```
  ⚠️ KIWI TEACHING: Trong {count} sessions gần đây cho {task_type},
  {lesson_title} ({lesson_id}) đã vi phạm.
  Lần cuối: {theme_name}/{file_path} — severity {severity}.
  → Cách đúng: {good_example_snippet}
  ```
- Pull context from `session_violations`: which theme, what file, severity
- Pull lesson details from Kiwi lessons (title, good_code) via existing `scanner/loader.py`
- Inject into `kiwi_reason()` output — add `output.teachings` field alongside existing `output.warnings`

### T3: Fade Logic (0.5 day)
- Integrated into `mistake_tracker.py`
- Activate teaching: `occurrence_count >= 3` → set `teaching_active = 1`
- Deactivate teaching: `consecutive_correct >= 5` → set `teaching_active = 0`
- Resume immediately: if violation returns after fade → `consecutive_correct = 0`, `teaching_active = 1`
- Rate limit: max 1 teaching message per task_type per session (check `session_id` in `warnings_issued` table)
- Global cap: max 2 active teachings per `kiwi_reason()` call (prevent context overload)

### T4: Tests + Integration (0.5 day)
- New file: `agent/reasoning/test_r15.py`
- Unit test: 3 violations for same (lesson_id, task_type) → teaching activates
- Unit test: 5 consecutive clean sessions → teaching fades
- Unit test: mistake returns after fade → teaching resumes
- Unit test: max 2 teachings per session enforced
- Integration: verify teaching message appears in `kiwi_reason()` output
- Verify: teaching message includes specific theme name + file + correct way

---

## Output Structure

```
agent/reasoning/
├── teaching.py              # T2+T3: generate teaching messages + fade logic
├── mistake_tracker.py       # T1: detect repeated mistakes per task_type
└── test_r15.py              # T4: unit + integration tests

agent/reasoning/schema.sql   # T0+T1: add session_violations + mistake_patterns tables

hooks/post_edit.py           # T0: add log_violation() call after scan
```

---

## Dependencies

| Dependency | From | What's needed |
|------------|------|---------------|
| R0 Session Logger | `agent/reasoning/session_logger.py` | `get_session_id()`, `_get_conn()`, DB connection |
| R3 Calibration | `agent/reasoning/calibrator.py` | Trust signals (positive = no violations) |
| R4 Proactive Warnings | `agent/reasoning/proactive_warnings.py` | Pattern for warning injection + `warnings_issued` table |
| R1 Context | `agent/reasoning/context_assembler.py` | `AssembledContext.task_type` for grouping |
| Main entry | `agent/reasoning/__init__.py:kiwi_reason()` | Inject teachings into output |
| Scanner | `scanner/loader.py` | Load lesson details (title, good_code) |
| Post-edit hook | `hooks/post_edit.py` | Hook point to log violations per session |
| Memory DB | `memory/kiwi.db` via `memory/schema.sql` | Existing `lessons` table for lesson metadata |

---

## Done Criteria

- [ ] `session_violations` table exists and populated by post-edit hook
- [ ] Repeated mistakes detected: same lesson_id × same task_type × 3+ times
- [ ] Teaching message includes: count, task_type, theme_name, file_path, correct way
- [ ] Fade works: 5 consecutive correct → teaching stops
- [ ] Resume works: mistake returns after fade → teaching resumes immediately
- [ ] Max 1 teaching per task_type per session (no nagging)
- [ ] Max 2 active teachings per kiwi_reason() call (context cap)
- [ ] Teaching injected into `kiwi_reason()` output as `output.teachings` list
- [ ] Zero token cost (all deterministic, template-based)
- [ ] Existing proactive warnings unaffected (teaching is additive)
- [ ] All tests in `test_r15.py` pass

---

## Risks & Mitigations

| Risk | Impact | Mitigation |
|------|--------|------------|
| Too many teachings at once | Context overload | Max 2 active teachings per session |
| False repetition (different root cause) | Annoying teaching | Group by (lesson_id + task_type), not just lesson_id |
| Teaching message too long | Token waste | Cap at 4 lines, link to lesson for details |
| Fade threshold too low | Teaching stops too early | 5 consecutive correct is conservative; can increase |
| session_violations not populated | Teaching never triggers | T0 is prerequisite; hook into post_edit.py which already runs on every edit |
| DB schema migration on existing installs | Crash on missing table | Use `CREATE TABLE IF NOT EXISTS` + `_migrate()` pattern from session_logger.py |
