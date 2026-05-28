# B1 — Reflective Learning / R9 (3.5 days)

## Mục tiêu
Think results (R8) feed back vào trust calibration. Kiwi học từ chính decisions của mình — biết khi nào nên think() và khi nào deterministic đủ tốt.

---

## Current State (pre-B1)

| Component | Status |
|-----------|--------|
| R8 Thinking | Done — `agent/reasoning/thinker.py` gọi LLM cho edge cases |
| R3 Calibration | Done — `agent/reasoning/calibrator.py` adjust trust scores |
| R7 Metrics | Done — `agent/reasoning/metrics.py` track intelligence score |
| Think event logging | **Done** — `_log_think_event()` logs trigger/decision/confidence/tokens vào `think_events` table |
| Think outcome backfill | **Missing** — `think_events.success` luôn NULL, không ai fill sau session end |
| Think ROI measurement | **Missing** — tokens_used tracked per event nhưng chưa có so sánh think vs no-think |
| Adaptive thresholds | **Missing** — `should_think()` dùng hardcoded thresholds, không tự adjust |

### Gap analysis
- `thinker.py` gọi LLM → log event (trigger, decision, confidence, tokens_used) → xong. `success` field = NULL mãi.
- `calibrator.py` chỉ dùng session-level signals (brief_insufficient, multiple_rewrites, kiwi_violations). Không map outcome → individual think decisions.
- `should_think()` thresholds cố định (e.g. trust gap < 0.05, pattern confidence gap < 0.15). Không có feedback loop để tự adjust.
- Không có cơ chế "think decision X dẫn đến session thành công/thất bại".

---

## Tasks

### T1: Think Outcome Backfill (0.5 day) — INFRA EXISTS
- `think_events` table đã có `success INTEGER DEFAULT NULL` — chỉ cần logic fill nó
- Khi session kết thúc → query `think_events WHERE session_id = ? AND success IS NULL`
- Evaluate outcome (xem T2) → UPDATE `think_events SET success = 1/0/-1`
- Hook vào `mark_session_processed()` trong `session_logger.py`

### T2: Session Outcome Evaluator (1 day)
- Khi session kết thúc → evaluate: thành công hay thất bại?
- Signals (reuse từ R3 calibrator):
  - `kiwi_violations` post-code = negative
  - `multiple_rewrites` = negative (think decision didn't help)
  - Session `files_written > 0` + no violations = positive
- Map outcome → tất cả think decisions trong session đó
- Granularity: per-trigger evaluation (not just session-level)
  - `pattern_conflict` think → check if chosen pattern had violations after
  - `borderline_trust` think → check if trust adjustment was correct
  - `novel_validation` think → check if novel pattern was later promoted
  - `style_ambiguity` think → check if style tokens were reused in next session

### T3: Think Calibrator (1.5 days)
- New table: `think_calibration(trigger TEXT PK, accuracy REAL, sample_count INT, threshold REAL, last_updated REAL)`
- Aggregate think outcomes per trigger type from `think_events.success`
- Nếu trigger X → think → 80%+ positive → giảm threshold (think more often)
- Nếu trigger X → think → 60%+ negative → tăng threshold (think less often)
- Modify `should_think()` in `thinker.py` to read dynamic thresholds:
  - Current hardcoded: `pattern_conflict` gap < 0.15, `borderline_trust` gap < 0.05
  - New: read from `think_calibration` table, fallback to hardcoded defaults
- Require 10+ samples before adjusting (cold start protection)

### T4: Think ROI Calculator (0.5 day)
- `think_events` already tracks `tokens_used` per call
- Compare: sessions with think vs without think (same task_type) using `output_quality` table
- ROI = (quality_delta × 100) / total_tokens_used_for_thinks
- Add to `metrics.py` dashboard: "Think: X calls, Y tokens, Z% positive outcome rate"

### T5: Tests + Integration (0.5 day)
- Unit tests cho evaluator, calibrator, ROI calculator
- Integration test: mock session → think → evaluate → calibrate → verify threshold change
- Regression: existing R8 `should_think()` behavior unchanged when no calibration data exists

---

## Output Structure

```
agent/reasoning/
├── thinker.py              # EXISTING — modify should_think() to read dynamic thresholds
├── think_evaluator.py      # NEW T2: evaluate session outcomes → map to think decisions
├── think_calibrator_r9.py  # NEW T3: adjust should_think() thresholds from outcomes
├── think_roi.py            # NEW T4: token cost vs quality improvement
├── session_logger.py       # EXISTING — hook T1 backfill into mark_session_processed()
└── test_r9.py              # NEW T5: unit + integration tests

agent/reasoning/schema.sql  # EXISTING — add think_calibration table
```

**Already exists (no new files needed):**
- `think_events` table with `success` column (schema.sql line 191-213)
- `_log_think_event()` in thinker.py (logs every think call)
- `output_quality` table (for ROI comparison)
- `calibration_events` table (for cross-referencing)

**New schema addition:**
```sql
-- R9: Think Calibration (adaptive thresholds)
CREATE TABLE IF NOT EXISTS think_calibration (
    trigger TEXT PRIMARY KEY,
    accuracy REAL DEFAULT 0.5,
    sample_count INTEGER DEFAULT 0,
    threshold REAL DEFAULT 0.5,
    last_updated REAL
);
CREATE INDEX IF NOT EXISTS idx_tcal_trigger ON think_calibration(trigger);
```

---

## Dependencies

| Dependency | From | What's needed |
|------------|------|---------------|
| R8 Thinking | `agent/reasoning/thinker.py` | `think()`, `should_think()`, `THINK_TRIGGERS`, `_log_think_event()` |
| R3 Calibration | `agent/reasoning/calibrator.py` | `calibrate_trust_from_session()` signals reuse |
| R7 Metrics | `agent/reasoning/metrics.py` | `record_output_quality()` for ROI comparison |
| Session Logger | `agent/reasoning/session_logger.py` | `_get_conn()`, `get_session_id()`, `mark_session_processed()` |
| Schema | `agent/reasoning/schema.sql` | `think_events` table (already has `success` column) |

---

## Done Criteria

- [x] Mỗi think() call được log với trigger + decision + context — **DONE** (`_log_think_event()`)
- [x] `think_events` table có `success` column — **DONE** (schema.sql)
- [ ] Session end → outcome evaluation chạy, backfill `think_events.success`
- [ ] Think accuracy metric available: "X% of think decisions led to positive outcomes"
- [ ] `should_think()` thresholds tự adjust sau 10+ samples per trigger
- [ ] ROI metric: "Think cost X tokens, Z% positive outcome rate"
- [ ] Existing R8 tests still pass (zero regression)
- [ ] Think calibration survives restart (persisted in SQLite `think_calibration` table)
- [ ] Fallback: khi `think_calibration` empty → hardcoded defaults (current behavior)

---

## Risks & Mitigations

| Risk | Impact | Mitigation |
|------|--------|------------|
| Outcome evaluation too noisy | Calibration oscillates | Require 10+ samples before adjusting threshold; use EMA not raw average |
| Think always "positive" (false attribution) | Never learns to skip think | Per-trigger granular eval (T2); compare sessions with/without think for same task_type |
| Token cost tracking inaccurate | ROI misleading | Already using actual `response.usage.output_tokens` in `_call_haiku()` |
| Circular dependency: calibrator imports thinker | Import error | `think_calibrator_r9.py` reads DB directly, no import of `thinker.py` |
| Cold start: no data → no calibration | Thresholds never adjust | Explicit 10-sample minimum; hardcoded defaults always available |