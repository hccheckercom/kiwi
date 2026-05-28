# Phase R4 — Active Intelligence Layer [1 tuần]

## Mục đích

R0-R3 là passive: observe → learn → calibrate trust. Hệ thống biết trust score nhưng **chưa hành động** dựa trên nó.

R4 biến trust thành **hành vi chủ động**: adaptive brief depth, proactive warnings, cross-theme transfer, novel pattern detection → auto-lesson promotion.

## Dependencies

- **R0 (Session Capture)** — `session_logger.py` — log tool calls
- **R1 (Context Assembly)** — `context_assembler.py` — assemble brief + trust score
- **R2 (Passive Learning)** — `learner.py` — extract styles/bindings/context_patterns
- **R3 (Calibration)** — `calibrator.py` — 3 signals → trust adjustment + decay + mining

## Audit: Tại sao plan cũ sai

| Plan cũ đề xuất | Thực tế đã có | Kết luận |
|---|---|---|
| `pattern_extractor.py` | `learner.py._extract_styles()` + `_extract_bindings()` | **DUPLICATE — xóa** |
| `knowledge_updater.py` | `learner.py._merge_styles()` + `_save_bindings()` | **DUPLICATE — xóa** |
| `post_code_hook.py` | `hooks/post_edit.py._try_auto_learn()` | **DUPLICATE — xóa** |
| Schema: `style_knowledge`, `binding_knowledge` | Đã có trong `schema.sql` | **DUPLICATE — xóa** |
| `task_classifier.py` import | `learner._infer_task_type()` | **WRONG IMPORT** |
| `memory.load_known_bindings()` | Không tồn tại | **PHANTOM DEPENDENCY** |

**Kết luận:** Plan cũ = rewrite R2 dưới tên khác. Không có giá trị mới.

---

## R4 Architecture — 3 Modules Thực Sự Mới

```
agent/reasoning/
├── adaptive_brief.py      # Trust → brief depth adjustment
├── proactive_warnings.py  # Detect risky patterns BEFORE code
├── cross_theme.py         # Transfer learnings across themes
└── novel_detector.py      # Detect + promote novel patterns
```

### Schema mới (thêm vào schema.sql)

```sql
-- R4: Novel patterns Claude uses that Kiwi doesn't know
CREATE TABLE IF NOT EXISTS novel_patterns (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    pattern TEXT NOT NULL,
    pattern_type TEXT NOT NULL,       -- "binding", "style", "structure"
    source_file TEXT,
    theme TEXT,
    task_type TEXT,
    times_seen INTEGER DEFAULT 1,
    first_seen REAL,
    last_seen REAL,
    promoted INTEGER DEFAULT 0,       -- 1 = promoted to lesson suggestion
    UNIQUE(pattern, pattern_type, theme)
);

-- R4: Cross-theme pattern transfer
CREATE TABLE IF NOT EXISTS cross_theme_patterns (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    task_type TEXT NOT NULL,
    structure TEXT,                    -- JSON: layout, sections, components
    themes_applied TEXT,              -- JSON array of theme names
    bindings TEXT,                    -- JSON array of common bindings
    success_count INTEGER DEFAULT 0,
    failure_count INTEGER DEFAULT 0,
    last_updated REAL,
    UNIQUE(task_type)
);

-- R4: Proactive warning history
CREATE TABLE IF NOT EXISTS warnings_issued (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id TEXT,
    task_type TEXT NOT NULL,
    warning_type TEXT NOT NULL,       -- "low_data", "high_failure", "novel_task"
    message TEXT,
    was_useful INTEGER DEFAULT NULL,  -- NULL=unknown, 1=useful, 0=noise
    created_at REAL
);

CREATE INDEX IF NOT EXISTS idx_np_pattern ON novel_patterns(pattern, pattern_type);
CREATE INDEX IF NOT EXISTS idx_np_theme ON novel_patterns(theme);
CREATE INDEX IF NOT EXISTS idx_ctp_task ON cross_theme_patterns(task_type);
CREATE INDEX IF NOT EXISTS idx_wi_task ON warnings_issued(task_type);
```

---

## Module 1: Adaptive Brief Depth (`adaptive_brief.py`)

**Concept:** Trust score → brief verbosity. High trust = minimal brief (save tokens). Low trust = detailed brief (prevent errors).

```python
"""R4 — Adaptive Brief: trust score → brief depth adjustment."""

from dataclasses import dataclass


@dataclass
class BriefConfig:
    max_files: int
    include_spec: bool
    include_examples: bool
    include_warnings: bool
    include_style_hints: bool
    verbosity: str  # "minimal", "standard", "detailed"


# Trust thresholds (calibrated from R3 data)
TRUST_TIERS = {
    "high": {"min": 0.75, "config": BriefConfig(
        max_files=5, include_spec=False, include_examples=False,
        include_warnings=False, include_style_hints=True, verbosity="minimal"
    )},
    "medium": {"min": 0.50, "config": BriefConfig(
        max_files=10, include_spec=True, include_examples=False,
        include_warnings=True, include_style_hints=True, verbosity="standard"
    )},
    "low": {"min": 0.0, "config": BriefConfig(
        max_files=15, include_spec=True, include_examples=True,
        include_warnings=True, include_style_hints=True, verbosity="detailed"
    )},
}


def get_brief_config(trust_score: float) -> BriefConfig:
    """Trust score → BriefConfig. Higher trust = less verbose brief."""
    for tier_name in ("high", "medium", "low"):
        tier = TRUST_TIERS[tier_name]
        if trust_score >= tier["min"]:
            return tier["config"]
    return TRUST_TIERS["low"]["config"]


def apply_adaptive_depth(context, trust_score: float):
    """Mutate AssembledContext based on trust-driven config."""
    config = get_brief_config(trust_score)

    # Trim files_needed
    if len(context.files_needed) > config.max_files:
        context.files_needed = context.files_needed[:config.max_files]

    # Strip spec if trust is high (Claude already knows the pattern)
    if not config.include_spec:
        context.spec = None

    # Strip reference pages if trust is high
    if not config.include_examples:
        context.reference_pages = []

    return config
```

**Integration point:** Called inside `kiwi_reason()` after `compute_trust_score()`, before `format_output()`.

---

## Module 2: Proactive Warnings (`proactive_warnings.py`)

**Concept:** Before Claude codes, detect patterns that historically lead to failure. Warn early instead of catching violations post-edit.

```python
"""R4 — Proactive Warnings: detect risky patterns before code is written."""

import time
from .session_logger import _get_conn


WARNING_TYPES = {
    "low_data": "Kiwi has < 3 sessions for this task_type+theme. Brief may be incomplete — verify files_needed manually.",
    "high_failure": "This task_type has > 40% failure rate (multiple_rewrites or kiwi_violations). Consider reading spec carefully.",
    "novel_task": "No prior sessions match this task. Trust score is baseline only — treat brief as suggestion, not authority.",
    "stale_baseline": "Trust baseline for this task_type hasn't been calibrated in 14+ days. Patterns may have changed.",
}


def check_warnings(task_type: str, theme: str, trust_score: float) -> list[dict]:
    """Pre-code check: return list of warnings if risky patterns detected."""
    warnings = []
    conn = _get_conn()
    if not conn:
        return warnings

    try:
        # Warning 1: Low data
        session_count = conn.execute(
            "SELECT COUNT(*) FROM context_patterns WHERE task_type = ? AND theme = ?",
            (task_type, theme),
        ).fetchone()[0]
        if session_count < 3:
            warnings.append({
                "type": "low_data",
                "message": WARNING_TYPES["low_data"],
                "data": {"sessions": session_count},
            })

        # Warning 2: High failure rate
        cal_events = conn.execute(
            "SELECT signals FROM calibration_events WHERE task_type = ? "
            "ORDER BY created_at DESC LIMIT 10",
            (task_type,),
        ).fetchall()
        if len(cal_events) >= 3:
            import json
            failure_count = 0
            for row in cal_events:
                try:
                    signals = json.loads(row[0])
                    if signals.get("multiple_rewrites") or signals.get("kiwi_violations"):
                        failure_count += 1
                except (json.JSONDecodeError, TypeError):
                    continue
            if failure_count / len(cal_events) > 0.4:
                warnings.append({
                    "type": "high_failure",
                    "message": WARNING_TYPES["high_failure"],
                    "data": {"failure_rate": failure_count / len(cal_events)},
                })

        # Warning 3: Novel task (no data at all)
        any_data = conn.execute(
            "SELECT COUNT(*) FROM context_patterns WHERE task_type = ?",
            (task_type,),
        ).fetchone()[0]
        if any_data == 0:
            warnings.append({
                "type": "novel_task",
                "message": WARNING_TYPES["novel_task"],
            })

        # Warning 4: Stale baseline
        baseline = conn.execute(
            "SELECT last_calibrated FROM trust_baselines WHERE task_type = ?",
            (task_type,),
        ).fetchone()
        if baseline and (time.time() - baseline[0]) > 14 * 86400:
            warnings.append({
                "type": "stale_baseline",
                "message": WARNING_TYPES["stale_baseline"],
            })

        # Save warnings for feedback loop
        if warnings:
            _save_warnings(conn, task_type, warnings)

    except Exception:
        pass

    return warnings


def _save_warnings(conn, task_type: str, warnings: list):
    """Persist warnings for later usefulness tracking."""
    try:
        from .session_logger import get_session_id
        session_id = get_session_id()
    except Exception:
        session_id = "unknown"

    now = time.time()
    for w in warnings:
        conn.execute(
            "INSERT INTO warnings_issued (session_id, task_type, warning_type, message, created_at) "
            "VALUES (?, ?, ?, ?, ?)",
            (session_id, task_type, w["type"], w["message"], now),
        )
    conn.commit()


def mark_warning_useful(warning_id: int, useful: bool):
    """Feedback: was this warning actually useful? Feeds into future suppression."""
    conn = _get_conn()
    if conn:
        conn.execute(
            "UPDATE warnings_issued SET was_useful = ? WHERE id = ?",
            (1 if useful else 0, warning_id),
        )
        conn.commit()
```

**Integration point:** Called inside `kiwi_reason()` after trust score, result included in `KiwiOutput.warnings`.

---

## Module 3: Cross-Theme Transfer (`cross_theme.py`)

**Concept:** When coding theme B for a task_type that theme A already solved successfully, transfer the structural pattern (not style tokens — those are per-theme).

```python
"""R4 — Cross-Theme Transfer: apply structural patterns across themes."""

import json
import time
from pathlib import Path
from .session_logger import _get_conn


def find_transferable_pattern(task_type: str, target_theme: str) -> dict | None:
    """Find a successful pattern from another theme for this task_type."""
    conn = _get_conn()
    if not conn:
        return None

    try:
        row = conn.execute(
            "SELECT structure, themes_applied, bindings, success_count, failure_count "
            "FROM cross_theme_patterns WHERE task_type = ?",
            (task_type,),
        ).fetchone()

        if not row:
            return None

        structure = json.loads(row[0]) if row[0] else {}
        themes_applied = json.loads(row[1]) if row[1] else []
        bindings = json.loads(row[2]) if row[2] else []
        success_count = row[3]
        failure_count = row[4]

        # Only transfer if success rate > 70% and target theme hasn't used it yet
        if success_count < 2:
            return None
        success_rate = success_count / max(success_count + failure_count, 1)
        if success_rate < 0.7:
            return None

        return {
            "task_type": task_type,
            "structure": structure,
            "source_themes": themes_applied,
            "bindings": bindings,
            "confidence": success_rate,
            "is_new_for_theme": target_theme not in themes_applied,
        }
    except Exception:
        return None


def record_pattern_outcome(task_type: str, theme: str, structure: dict,
                           bindings: list, success: bool):
    """After session: record whether the cross-theme pattern worked."""
    conn = _get_conn()
    if not conn:
        return

    try:
        existing = conn.execute(
            "SELECT id, themes_applied, success_count, failure_count FROM cross_theme_patterns "
            "WHERE task_type = ?",
            (task_type,),
        ).fetchone()

        now = time.time()
        if existing:
            themes = json.loads(existing[1]) if existing[1] else []
            if theme not in themes:
                themes.append(theme)

            if success:
                conn.execute(
                    "UPDATE cross_theme_patterns SET themes_applied = ?, "
                    "success_count = success_count + 1, last_updated = ? WHERE id = ?",
                    (json.dumps(themes), now, existing[0]),
                )
            else:
                conn.execute(
                    "UPDATE cross_theme_patterns SET themes_applied = ?, "
                    "failure_count = failure_count + 1, last_updated = ? WHERE id = ?",
                    (json.dumps(themes), now, existing[0]),
                )
        else:
            conn.execute(
                "INSERT INTO cross_theme_patterns "
                "(task_type, structure, themes_applied, bindings, success_count, failure_count, last_updated) "
                "VALUES (?, ?, ?, ?, ?, ?, ?)",
                (task_type, json.dumps(structure), json.dumps([theme]),
                 json.dumps(bindings), 1 if success else 0, 0 if success else 1, now),
            )
        conn.commit()
    except Exception:
        pass
```

**Integration point:** Called in `context_assembler._enrich_files_from_patterns()` — if transferable pattern found, add its source files to `files_needed`.

---

## Module 4: Novel Pattern Detector (`novel_detector.py`)

**Concept:** After each learning cycle, compare extracted bindings/styles against known knowledge. New patterns seen 3+ times across sessions → auto-suggest as Kiwi lesson.

```python
"""R4 — Novel Pattern Detector: find patterns Claude uses that Kiwi doesn't know."""

import json
import time
from .session_logger import _get_conn


def detect_novel_bindings(session_bindings: list, task_type: str, theme: str) -> list:
    """Compare session bindings against known binding_knowledge. Return novel ones."""
    conn = _get_conn()
    if not conn:
        return []

    try:
        known_rows = conn.execute(
            "SELECT binding FROM binding_knowledge WHERE task_type = ? AND times_seen >= 3",
            (task_type,),
        ).fetchall()
        known = {r[0] for r in known_rows}

        novel = [b for b in session_bindings if b not in known]
        return novel
    except Exception:
        return []


def record_novel_pattern(pattern: str, pattern_type: str, theme: str,
                         task_type: str, source_file: str = ""):
    """Record a novel pattern. Increments times_seen if already recorded."""
    conn = _get_conn()
    if not conn:
        return

    now = time.time()
    try:
        existing = conn.execute(
            "SELECT id, times_seen FROM novel_patterns "
            "WHERE pattern = ? AND pattern_type = ? AND theme = ?",
            (pattern, pattern_type, theme),
        ).fetchone()

        if existing:
            conn.execute(
                "UPDATE novel_patterns SET times_seen = times_seen + 1, "
                "last_seen = ?, task_type = ? WHERE id = ?",
                (now, task_type, existing[0]),
            )
        else:
            conn.execute(
                "INSERT INTO novel_patterns "
                "(pattern, pattern_type, source_file, theme, task_type, times_seen, first_seen, last_seen) "
                "VALUES (?, ?, ?, ?, ?, 1, ?, ?)",
                (pattern, pattern_type, source_file, theme, task_type, now, now),
            )

        # FIFO: max 200 novel patterns
        count = conn.execute("SELECT COUNT(*) FROM novel_patterns WHERE promoted = 0").fetchone()[0]
        if count > 200:
            conn.execute(
                "DELETE FROM novel_patterns WHERE id IN ("
                "  SELECT id FROM novel_patterns WHERE promoted = 0 "
                "  ORDER BY last_seen ASC LIMIT ?"
                ")",
                (count - 200,),
            )
        conn.commit()
    except Exception:
        pass


def get_promotable_patterns(min_occurrences: int = 3) -> list[dict]:
    """Find novel patterns seen enough times to suggest as Kiwi lessons."""
    conn = _get_conn()
    if not conn:
        return []

    try:
        rows = conn.execute(
            "SELECT id, pattern, pattern_type, theme, task_type, times_seen, first_seen "
            "FROM novel_patterns "
            "WHERE promoted = 0 AND times_seen >= ? "
            "ORDER BY times_seen DESC LIMIT 10",
            (min_occurrences,),
        ).fetchall()

        return [{
            "id": r[0], "pattern": r[1], "type": r[2], "theme": r[3],
            "task_type": r[4], "times_seen": r[5], "first_seen": r[6],
        } for r in rows]
    except Exception:
        return []


def promote_pattern(pattern_id: int):
    """Mark pattern as promoted (lesson suggestion created)."""
    conn = _get_conn()
    if conn:
        conn.execute("UPDATE novel_patterns SET promoted = 1 WHERE id = ?", (pattern_id,))
        conn.commit()
```

**Integration point:** Called at end of `learner.learn_from_session()` — after extracting bindings, check for novelty and record.

---

## Integration: Modified `__init__.py`

```python
"""Kiwi Reasoning Layer — R4: Active Intelligence."""

from .context_assembler import assemble_context, AssembledContext
from .trust_scorer import compute_trust_score
from .output import format_output, KiwiOutput


def kiwi_reason(task: str, theme_path: str) -> KiwiOutput:
    """Task → Brief + Trust Score + Adaptive Depth + Warnings. 0 LLM token. ~50ms."""
    _auto_learn_recent(max_sessions=3)
    context = assemble_context(task, theme_path)
    trust_score, breakdown = compute_trust_score(context, theme_path)

    # R4: Adaptive brief depth
    from .adaptive_brief import apply_adaptive_depth
    brief_config = apply_adaptive_depth(context, trust_score)

    # R4: Proactive warnings
    from .proactive_warnings import check_warnings
    theme_name = context.theme.get('name', 'unknown') if isinstance(context.theme, dict) else 'unknown'
    warnings = check_warnings(context.task_type, theme_name, trust_score)

    # R4: Cross-theme transfer
    from .cross_theme import find_transferable_pattern
    transfer = find_transferable_pattern(context.task_type, theme_name)

    output = format_output(context, trust_score, breakdown)
    output.warnings = warnings
    output.transfer = transfer
    output.brief_config = brief_config

    try:
        from .session_logger import get_session_id, save_brief_output
        save_brief_output(get_session_id(), output)
    except Exception:
        pass

    return output


def _auto_learn_recent(max_sessions: int = 3):
    """Piggyback: learn + calibrate + detect novel patterns from unprocessed sessions."""
    try:
        from .session_logger import get_unprocessed_sessions
        from .learner import learn_from_session
        from .calibrator import calibrate_trust_from_session, decay_stale_baselines
        from .cross_theme import record_pattern_outcome

        sessions = get_unprocessed_sessions(min_writes=1)
        learned_count = 0
        for s in sessions[:max_sessions]:
            result = learn_from_session(s["session_id"])
            calibrate_trust_from_session(s["session_id"])

            # R4: Record cross-theme outcome (success = no kiwi violations)
            if result.get("status") == "learned":
                from .calibrator import _check_post_code_violations
                success = not _check_post_code_violations(s["session_id"])
                # Only record if we have structure data
                # (actual structure extraction happens in learner)

            learned_count += 1

        if learned_count > 0:
            from .session_logger import _get_conn
            conn = _get_conn()
            total = conn.execute(
                "SELECT COUNT(*) FROM sessions WHERE processed = 1"
            ).fetchone()[0]
            if total > 0 and total % 10 == 0:
                from .learner import calibrate_trust_baselines
                calibrate_trust_baselines()
                decay_stale_baselines()
    except Exception:
        pass
```

---

## Integration: Modified `learner.py` (thêm novel detection)

Thêm vào cuối `learn_from_session()`, sau bước extract bindings:

```python
    # 4. R4: Detect novel patterns
    try:
        from .novel_detector import detect_novel_bindings, record_novel_pattern
        for w in theme_writes:
            fp = w["file"]
            if not fp or not Path(fp).exists():
                continue
            content = Path(fp).read_text(encoding="utf-8", errors="ignore")
            bindings = _extract_bindings(content)
            novel = detect_novel_bindings(bindings, task_type, theme)
            for pattern in novel:
                record_novel_pattern(pattern, "binding", theme, task_type, fp)
    except Exception:
        pass
```

---

## Integration: Modified `output.py`

Thêm fields vào `KiwiOutput`:

```python
@dataclass
class KiwiOutput:
    # ... existing fields ...
    warnings: list = field(default_factory=list)      # R4: proactive warnings
    transfer: dict | None = None                       # R4: cross-theme pattern
    brief_config: object = None                        # R4: adaptive depth config
```

---

## Verification Plan

```python
# Test 1: Adaptive brief — high trust = minimal output
from agent.reasoning.adaptive_brief import get_brief_config
config = get_brief_config(0.85)
assert config.verbosity == "minimal"
assert config.max_files == 5
assert config.include_spec == False

config = get_brief_config(0.3)
assert config.verbosity == "detailed"
assert config.max_files == 15
assert config.include_examples == True

# Test 2: Proactive warnings — novel task triggers warning
from agent.reasoning.proactive_warnings import check_warnings
warnings = check_warnings("never_seen_task", "new_theme", 0.5)
assert any(w["type"] == "novel_task" for w in warnings)

# Test 3: Novel detector — unknown binding detected
from agent.reasoning.novel_detector import detect_novel_bindings, record_novel_pattern
novel = detect_novel_bindings(["wz_new_function"], "home_page", "test_theme")
assert "wz_new_function" in novel

# Test 4: Cross-theme — pattern with high success rate transfers
from agent.reasoning.cross_theme import record_pattern_outcome, find_transferable_pattern
record_pattern_outcome("checkout_page", "theme_a", {"layout": "2-col"}, ["wz_cart"], True)
record_pattern_outcome("checkout_page", "theme_a", {"layout": "2-col"}, ["wz_cart"], True)
result = find_transferable_pattern("checkout_page", "theme_b")
assert result is not None
assert result["is_new_for_theme"] == True

# Test 5: E2E — kiwi_reason returns warnings + transfer + config
from agent.reasoning import kiwi_reason
output = kiwi_reason("tạo trang checkout", "themes/new-theme")
assert hasattr(output, 'warnings')
assert hasattr(output, 'brief_config')
```

---

## Constraints

- All R4 modules: failure KHÔNG block coding (try/except wrapper)
- 0 LLM tokens — pure Python + SQLite
- Latency budget: +10ms max on top of R0-R3's ~50ms
- Novel patterns FIFO: max 200 unpromoted
- Warnings FIFO: max 500 (auto-evict oldest)
- Cross-theme transfer: only suggest if success_rate > 70% AND 2+ prior successes
- Adaptive brief: NEVER strip `files_needed` below 3 (minimum useful context)

## Token Impact

| Scenario | R0-R3 output | R4 output | Savings |
|---|---|---|---|
| High trust (>0.75) | Full brief (~800 tokens) | Minimal brief (~300 tokens) | **62%** |
| Medium trust (0.5-0.75) | Full brief (~800 tokens) | Standard brief (~600 tokens) | **25%** |
| Low trust (<0.5) | Full brief (~800 tokens) | Detailed brief (~1000 tokens) | -25% (intentional) |
| Novel task | No warning | Warning + suggestion | +50 tokens (worth it) |

## Migration from R3

1. Add new tables to `schema.sql`
2. Create 4 new files in `agent/reasoning/`
3. Modify `__init__.py` — add R4 imports + calls
4. Modify `learner.py` — add novel detection at end
5. Modify `output.py` — add 3 new fields to KiwiOutput
6. Run full test suite (43 existing + 5 new R4 tests)
7. No breaking changes — all R4 additions are additive + wrapped in try/except
