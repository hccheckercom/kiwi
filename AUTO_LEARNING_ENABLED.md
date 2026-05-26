# Kiwi Auto-Learning System — ACTIVATED

**Status:** PRODUCTION ACTIVE  
**Activated:** 2026-05-25  
**Version:** 2.1

---

## System Overview

Kiwi tự động học và hoàn thiện knowledge base từ mọi scan, không cần can thiệp thủ công.

**Current Stats:**
- Total lessons: 509
- Scan history: 10 scans
- Pending suggestions: 56 patterns
- Violations tracked: 0

---

## Auto-Learning Features (ALL ACTIVE)

### 1. Pattern Mining (ACTIVE)
- **Trigger:** Every scan with ≥10 violations
- **Algorithm:** Cluster similar violations → extract regex pattern
- **Threshold:** min_occurrences=3, similarity=0.8
- **Output:** Suggested lessons in database

### 2. Auto-Promotion (ACTIVE)
- **Trigger:** After pattern mining completes
- **Threshold:** confidence ≥ 0.7
- **Action:** Auto-create lesson file + update index
- **No manual approval needed** for high-confidence patterns

### 3. Pattern Refinement (ACTIVE)
- **Trigger:** After fix applied with failure
- **Threshold:** FP rate > 30%
- **Algorithm:** Extract common tokens from FPs → add negative lookahead
- **Action:** Update lesson pattern + track refinement history

### 4. Deduplication (ACTIVE)
- **Trigger:** After 10 new lessons created
- **Threshold:** similarity ≥ 0.9
- **Action:** Merge duplicate lessons → archive old ones

### 5. Single-File Learning (ACTIVE)
- **Trigger:** `kiwi_scan_learn(file="...")` or `--learn` flag
- **Detectors:** 15 built-in (10 PHP + 5 JS/TS)
- **Output:** Instant pattern suggestions from single file

### 6. Global Mining (READY)
- **Trigger:** Manual via `kiwi_mine_global()` or weekly cron
- **Scope:** All projects (wezone-plugins, webstore-vn, themes)
- **Boost:** Cross-project patterns get 1.2-1.5x confidence

---

## Workflow

```
┌─────────────────────────────────────────────────────────────┐
│                    SCAN TRIGGERED                           │
│              (kiwi_scan, kiwi_agent, CLI)                   │
└────────────────────┬────────────────────────────────────────┘
                     │
                     ▼
         ┌───────────────────────┐
         │  Violations ≥ 10?     │
         └───────┬───────────────┘
                 │ YES
                 ▼
    ┌────────────────────────────┐
    │   Pattern Mining           │
    │   (learning/miner.py)      │
    │   - Cluster violations     │
    │   - Extract regex          │
    │   - Calculate confidence   │
    └────────┬───────────────────┘
             │
             ▼
    ┌────────────────────────────┐
    │   Auto-Promotion           │
    │   (learning/loop.py)       │
    │   - Filter confidence≥0.7  │
    │   - Generate lesson file   │
    │   - Update _meta.json      │
    │   - Rebuild index          │
    └────────┬───────────────────┘
             │
             ▼
    ┌────────────────────────────┐
    │   Pattern Refinement       │
    │   (learning/refiner.py)    │
    │   - Check FP rate          │
    │   - Add negative lookahead │
    │   - Test accuracy          │
    └────────┬───────────────────┘
             │
             ▼
    ┌────────────────────────────┐
    │   Deduplication            │
    │   (learning/dedup.py)      │
    │   - Find similar lessons   │
    │   - Merge duplicates       │
    │   - Archive old versions   │
    └────────────────────────────┘
```

---

## Database Schema

All learning data stored in `kiwi.db`:

- **scan_history** — Every scan tracked with metadata
- **violations** — Every violation detected (for pattern mining)
- **suggested_lessons** — Pending pattern suggestions
- **lesson_confidence** — Confidence scores + FP tracking
- **false_positives** — Dismissed violations (for refinement)
- **fix_outcomes** — Fix success/failure (for confidence)
- **pattern_refinements** — Refinement history

---

## Manual Controls

### Review Pending Suggestions
```python
from learning.generator import review_suggestions
suggestions = review_suggestions(status='pending')
```

### Approve Suggestion
```python
from learning.generator import approve_suggestion
approve_suggestion(suggestion_id=123)
```

### Reject Suggestion
```python
from learning.generator import reject_suggestion
reject_suggestion(suggestion_id=123, reason="Too noisy")
```

### Run Global Mining
```python
from learning.global_miner import mine_patterns_global
patterns = mine_patterns_global(min_projects=2, lookback_days=30)
```

### Find Duplicates
```python
from learning.dedup import find_duplicate_lessons, merge_lessons
clusters = find_duplicate_lessons(similarity_threshold=0.9)
for cluster in clusters:
    merge_lessons(cluster)
```

---

## Monitoring

### Check Learning Stats
```bash
cd .claude/kiwi
python -c "
from memory.db import get_connection
conn = get_connection()

# Scan history
cursor = conn.execute('SELECT COUNT(*) FROM scan_history')
print(f'Total scans: {cursor.fetchone()[0]}')

# Violations tracked
cursor = conn.execute('SELECT COUNT(*) FROM violations')
print(f'Violations tracked: {cursor.fetchone()[0]}')

# Pending suggestions
cursor = conn.execute('SELECT COUNT(*) FROM suggested_lessons WHERE status=\"pending\"')
print(f'Pending suggestions: {cursor.fetchone()[0]}')

# Auto-promoted
cursor = conn.execute('SELECT COUNT(*) FROM suggested_lessons WHERE status=\"approved\"')
print(f'Auto-promoted: {cursor.fetchone()[0]}')

conn.close()
"
```

### Check Confidence Scores
```bash
python -c "
from memory.confidence import get_all_confidence
scores = get_all_confidence()
print(f'Lessons with confidence tracking: {len(scores)}')
for s in scores[:5]:
    print(f'  {s[\"lesson_id\"]}: {s[\"confidence\"]:.2f} ({s[\"total_hits\"]} hits, {s[\"false_positive_count\"]} FPs)')
"
```

---

## Success Metrics

Target for v2.5 (95%+ self-learning):

- ✅ Pattern refinement auto-triggers when FP rate > 30%
- ✅ Duplicate lessons auto-merge (0 duplicates)
- ⏳ Cross-project patterns promoted with confidence boost
- ⏳ Flow-based violations detected (not just line-by-line)
- ⏳ False positive rate < 5% (currently ~15%)
- ⏳ 50+ universal patterns mined from multiple projects
- ⏳ Contextual lessons learned from fix outcomes

**Current self-learning rate:** ~75-80%  
**Target:** 95%+

---

## Next Steps

1. **Let it run** — system will learn from every scan automatically
2. **Review 56 pending suggestions** — approve high-confidence patterns
3. **Enable global mining** — run weekly to learn cross-project patterns
4. **Monitor confidence scores** — track which lessons are noisy
5. **Phase 3-4 implementation** — semantic understanding + flow analysis

---

## Troubleshooting

### No patterns mined after scan
- Check violations count: must be ≥10
- Check `_trigger_learning()` in agent/loop.py
- Check database: `SELECT * FROM violations ORDER BY detected_at DESC LIMIT 10`

### Patterns not auto-promoting
- Check confidence threshold: must be ≥0.7
- Check `promote_high_confidence_lessons()` in learning/loop.py
- Check database: `SELECT * FROM suggested_lessons WHERE status='pending'`

### Refinement not triggering
- Check FP rate: must be >30%
- Check `refine_noisy_pattern()` in learning/refiner.py
- Check database: `SELECT * FROM lesson_confidence WHERE confidence < 0.5`

---

**Kiwi is now self-improving. Every scan makes it smarter.**