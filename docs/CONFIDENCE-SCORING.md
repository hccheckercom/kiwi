# Kiwi Confidence Scoring System

Auto-identify noisy lessons and reduce false positives over time.

## Overview

Kiwi tracks every violation you dismiss as a false positive and calculates a confidence score for each lesson. Lessons with low confidence (< 0.5) and multiple false positives (≥ 3) are automatically demoted in severity.

**Impact:**
- First scan: May have many false positives
- After 5-10 scans + dismissals: Noisy lessons auto-demoted
- **Expected final FP rate: <10%** (from 98.4% baseline)

## Workflow

### 1. Scan project
```javascript
kiwi_scan({ path: "wezone-plugins" })
```

### 2. Dismiss false positives
When you find a violation that's not a real bug:

```javascript
kiwi_dismiss({
  lesson_id: "LES-308",
  file: "assets/js/admin.js",
  reason: "Global nonce setup via $.ajaxSetup() at line 10",
  scope: "file"  // or "project" or "global"
})
```

**Scopes:**
- `file` — Only this file (default)
- `project` — All files in this project
- `global` — All projects (use sparingly)

### 3. Check confidence scores
```javascript
// View specific lesson
kiwi_confidence({ lesson_id: "LES-308" })

// View all noisy lessons (≥3 false positives)
kiwi_confidence({ min_fps: 3 })

// View overview of all tracked lessons
kiwi_confidence()
```

**Output example:**
```
Noisy Lessons (≥3 false positives):

  LES-445  conf=0.45 hits=20 TP=9 FP=11 ⚠️ AUTO-DEMOTED: HIGH → SUGGEST
  LES-308  conf=0.92 hits=25 TP=23 FP=2 ✓ High confidence
```

## Auto-Demotion Rules

Lessons are auto-demoted when:
- Confidence < 0.5 (more false positives than true positives)
- False positive count ≥ 3 (avoid premature demotion)

**Severity changes:**
- CRITICAL → HIGH
- HIGH → SUGGEST
- SUGGEST → (filtered out in default scans)

## Confidence Formula

```
confidence = true_positives / (true_positives + false_positives)
```

**Factors:**
- Base confidence: 1.0 - (FP / total_hits)
- Fix success rate: Weighted 30% if auto-fix data available
- Final: `base * 0.7 + fix_rate * 0.3`

## Database Schema

Located at `.claude/kiwi/kiwi.db` (SQLite):

**Tables:**
- `lesson_confidence` — Confidence scores per lesson
- `false_positives` — Dismissed violations
- `scan_history` — Scan execution logs
- `fix_outcomes` — Auto-fix success/failure tracking

## CLI Usage

```powershell
# View confidence scores
$env:PYTHONUTF8=1; cd .claude/kiwi
python -c "from memory.confidence import get_noisy_lessons; print(get_noisy_lessons())"

# Dismiss via Python
python -c "from memory.db import dismiss_violation; from memory.confidence import update_hit, recalculate_confidence; dismiss_violation('LES-308', 'file.php', reason='...'); update_hit('LES-308', False); recalculate_confidence('LES-308')"
```

## Best Practices

1. **Be specific in dismiss reasons** — helps future debugging
2. **Use `file` scope by default** — only escalate to `project`/`global` if pattern is consistently wrong
3. **Check confidence after 5+ scans** — need data to see trends
4. **Review auto-demoted lessons** — may need pattern refinement instead of demotion

## Integration with Scanner

Confidence scores are automatically tracked during:
- `kiwi_scan()` — Records violations
- `kiwi_agent()` — Tracks fix outcomes
- `kiwi_check()` — Post-edit validation

No manual tracking needed — just use `kiwi_dismiss()` when you find false positives.

## Troubleshooting

**Q: Lesson still shows CRITICAL after dismissing 5 times**
A: Check confidence with `kiwi_confidence({ lesson_id: "LES-XXX" })`. Auto-demotion only triggers when confidence < 0.5 AND FP ≥ 3. If you have 5 FP but also 10 TP, confidence = 0.67 → no demotion.

**Q: How to reset confidence for a lesson?**
A: Delete from SQLite:
```sql
DELETE FROM lesson_confidence WHERE lesson_id = 'LES-XXX';
DELETE FROM false_positives WHERE lesson_id = 'LES-XXX';
```

**Q: Can I manually demote a lesson?**
A: Yes, edit the lesson file's `severity:` field. But confidence scoring is better — it adapts over time.

## Related

- [ROADMAP.md](../ROADMAP.md) — Hướng 3 implementation details
- [memory/confidence.py](../memory/confidence.py) — Core scoring logic
- [memory/db.py](../memory/db.py) — Database operations