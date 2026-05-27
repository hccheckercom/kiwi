# Kiwi UI Generator V2 — Session Handoff

**Session Date:** 2026-05-27  
**Status:** INCOMPLETE — Blockers identified, needs continuation  
**Next Session Priority:** Fix token extraction consistency + feedback logging

---

## Session Summary

Attempted production validation of Kiwi UI Generator V2 by testing with 3 synthetic demos. **Result: 1/3 success (33%)** — generator works but has critical reliability issues.

### What Was Accomplished

✅ **Created test infrastructure:**
- 3 synthetic demos with proper structure (Fashion, Tech, Beauty)
- All demos have embedded `tailwind.config` in `<script id="tailwind-config">`
- Proper UTF-8 encoding, identical HTML structure

✅ **Successful generation (Demo 1 - Fashion Store):**
- Gen ID: `e536d07d`
- 7 files created (store-config.php, tailwind.config.js, main.css, etc.)
- 6 components detected (header, hero, footer, +3)
- 4 components auto-applied (67% auto-apply rate)
- 2 components flagged for manual review
- Backup created: `.claude/kiwi/generator/.backups/e536d07d_20260527_140450`

✅ **Documented findings:**
- [TEST-RESULTS.md](.claude/kiwi/generator/TEST-RESULTS.md) — detailed test report
- Identified 3 critical blockers (P0) and 2 improvements (P1)

### What Failed

❌ **Demos 2 and 3 failed with identical error:**
```
WARNING: Failed to parse tailwind.config: Expecting ',' delimiter: line 10 column 18
WARNING: Missing or empty token category: colors/typography/spacing/borderRadius
FAILED: Design token validation failed
```

❌ **Feedback logging broken:**
```
Warning: Failed to log feedback: 'html'
```
- Prevents collecting ML training data
- Blocks Task 2 (train ML classifier)

---

## Critical Blockers (Must Fix Next Session)

### 1. Token Extraction Inconsistency (P0)
**Impact:** 67% failure rate  
**Symptoms:**
- Demo 1 succeeds, demos 2 & 3 fail with identical structure
- All 3 demos have same HTML format, proper encoding, same line count
- Error suggests JSON parsing issue in `_normalize_js_object()`

**Root Cause Hypothesis:**
- Token extractor may have state/caching between runs
- Regex in [token_extractor.py:84](D:\projects\wezone\.claude\kiwi\generator\parsers\token_extractor.py#L84) uses `$` anchor which may fail with trailing whitespace
- `_normalize_js_object()` may not handle all JavaScript object notation consistently

**Files to Debug:**
- [parsers/token_extractor.py](D:\projects\wezone\.claude\kiwi\generator\parsers\token_extractor.py) — lines 84, 210-228
- [parsers/token_extractor.py:extract_from_html](D:\projects\wezone\.claude\kiwi\generator\parsers\token_extractor.py#L58-L111)

**Test Demos Location:**
- `themes/synthetic-demo-1/` — ✅ WORKS
- `themes/synthetic-demo-2/` — ❌ FAILS
- `themes/synthetic-demo-3/` — ❌ FAILS

### 2. Feedback Logging Failure (P0)
**Impact:** Cannot collect ML training data  
**Error:** `'html'` key missing  
**Location:** [demo_orchestrator.py](D:\projects\wezone\.claude\kiwi\generator\demo_orchestrator.py) feedback logging section

**What to Check:**
- Feedback data structure in [memory/db.py](D:\projects\wezone\.claude\kiwi\memory\db.py)
- What keys are required for `update_generator_feedback()`
- Add try/except with better error handling

**Why This Matters:**
- Need 10+ feedback entries to train ML classifier
- Currently 0 entries due to this bug
- Blocks entire ML training pipeline (Task 2)

---

## Next Session Tasks (Priority Order)

### Task 1: Fix Token Extraction (P0)
**Goal:** Achieve 100% success rate on identical demo structures

**Steps:**
1. **Debug the difference between demo 1 (success) and demos 2/3 (fail):**
   ```python
   # Compare what token_extractor.py actually extracts from each demo
   from generator.parsers.token_extractor import DesignTokenExtractor
   extractor = DesignTokenExtractor()
   
   for i in [1, 2, 3]:
       print(f"\n=== Demo {i} ===")
       tokens = extractor.extract_from_demo(f'themes/synthetic-demo-{i}')
       print(f"Colors: {tokens.get('colors', {})}")
       print(f"Typography: {tokens.get('typography', {})}")
   ```

2. **Fix `_normalize_js_object()` method:**
   - Add unit tests for JavaScript → JSON conversion
   - Handle edge cases: trailing commas, single quotes in arrays, etc.
   - Test with all 3 demo configs

3. **Fix regex extraction:**
   - Remove `$` anchor or handle trailing whitespace
   - Add better error messages showing what was extracted

4. **Verify fix:**
   - Re-run all 3 demos
   - All should succeed with similar component detection rates

### Task 2: Fix Feedback Logging (P0)
**Goal:** Enable ML training data collection

**Steps:**
1. **Find the feedback logging code:**
   ```bash
   grep -n "Failed to log feedback" .claude/kiwi/generator/demo_orchestrator.py
   ```

2. **Check required keys:**
   - Read [memory/db.py](D:\projects\wezone\.claude\kiwi\memory\db.py)
   - Find `update_generator_feedback()` signature
   - Identify what 'html' key should contain

3. **Fix the logging:**
   - Add missing 'html' key to feedback data
   - Add proper error handling
   - Test feedback collection end-to-end

4. **Verify fix:**
   - Generate 1 theme
   - Check feedback logged successfully
   - Query feedback count: `get_generator_feedback()`

### Task 3: Collect Training Data (P1)
**Goal:** Get 10+ feedback entries for ML classifier

**Steps:**
1. **Generate 10 themes from synthetic demos:**
   - Use all 3 demos multiple times
   - Vary confidence thresholds (0.6, 0.7, 0.8)
   - Test different modes (tokens-only, foundation)

2. **Provide feedback for each generation:**
   ```python
   from memory.db import update_generator_feedback
   
   update_generator_feedback(
       gen_id="...",
       accepted=True,  # or False
       corrections="Optional: what was wrong"
   )
   ```

3. **Verify data collection:**
   ```python
   from memory.db import get_generator_feedback
   feedback = get_generator_feedback()
   print(f"Total entries: {len(feedback)}")
   ```

### Task 4: Train ML Classifier (P1)
**Goal:** Improve component detection accuracy

**Prerequisites:** 10+ feedback entries collected

**Steps:**
1. **Check feedback count:**
   ```python
   from memory.db import get_generator_feedback
   feedback = get_generator_feedback()
   print(f"Ready to train: {len(feedback) >= 10}")
   ```

2. **Run training:**
   ```python
   from generator.ml.classifier import retrain_classifier
   
   results = retrain_classifier(force=True)
   print(f"Accuracy: {results['accuracy']:.2%}")
   print(f"Precision: {results['precision']:.2%}")
   print(f"Recall: {results['recall']:.2%}")
   ```

3. **Analyze thresholds:**
   ```python
   from generator.ml.classifier import analyze_confidence_thresholds
   
   analysis = analyze_confidence_thresholds()
   print(f"Recommended threshold: {analysis['recommended_threshold']}")
   ```

4. **Update default threshold** in [demo_orchestrator.py](D:\projects\wezone\.claude\kiwi\generator\demo_orchestrator.py) if needed

### Task 5: Test Full Mode (P1)
**Goal:** Verify G0 + G1 generation pipeline

**Prerequisites:** Foundation mode working reliably (100% success rate)

**Steps:**
1. **Run full mode generation:**
   ```python
   from generator.demo_orchestrator import DemoThemeGenerator
   
   generator = DemoThemeGenerator()
   report = generator.generate_from_demo(
       demo_path='themes/synthetic-demo-1',
       theme_name='test-full-mode',
       mode='full',
       confidence_threshold=0.7
   )
   ```

2. **Verify file counts:**
   - G0 Foundation: 16 files expected
   - G1 Pages: 11 files expected
   - Total: 27 files

3. **Run Kiwi scan:**
   ```powershell
   cd .claude/kiwi
   python -m scanner.cli --theme ../../themes/test-full-mode --platform wp --severity CRITICAL
   ```

4. **Verify 0 CRITICAL violations**

5. **Test theme activation** (if LocalWP available):
   - Copy to LocalWP site
   - Activate theme
   - Check homepage renders
   - Check PHP error logs

---

## Key Files Reference

### Generator Core
- [demo_orchestrator.py](D:\projects\wezone\.claude\kiwi\generator\demo_orchestrator.py) — Main orchestrator, feedback logging
- [parsers/token_extractor.py](D:\projects\wezone\.claude\kiwi\generator\parsers\token_extractor.py) — Token extraction (BUGGY)
- [parsers/component_detector.py](D:\projects\wezone\.claude\kiwi\generator\parsers\component_detector.py) — Component detection
- [converters/store_config_generator.py](D:\projects\wezone\.claude\kiwi\generator\converters\store_config_generator.py) — Config generation
- [converters/html_to_php.py](D:\projects\wezone\.claude\kiwi\generator\converters\html_to_php.py) — HTML → PHP conversion

### ML System
- [ml/classifier.py](D:\projects\wezone\.claude\kiwi\generator\ml\classifier.py) — Component classifier
- [ml/trainer.py](D:\projects\wezone\.claude\kiwi\generator\ml\trainer.py) — Training pipeline

### Database
- [../memory/db.py](D:\projects\wezone\.claude\kiwi\memory\db.py) — Feedback storage

### Tests
- [tests/test_integration.py](D:\projects\wezone\.claude\kiwi\generator\tests\test_integration.py) — Integration tests (6/6 passing)
- [tests/test_rollback.py](D:\projects\wezone\.claude\kiwi\generator\tests\test_rollback.py) — Rollback tests (4/5 passing)

### Documentation
- [TEST-RESULTS.md](D:\projects\wezone\.claude\kiwi\generator\TEST-RESULTS.md) — Detailed test report from this session
- [NEXT-SESSION-PROMPT.md](D:\projects\wezone\.claude\kiwi\generator\NEXT-SESSION-PROMPT.md) — Original session plan

---

## Test Data

### Synthetic Demos (Ready to Use)
All 3 demos are in `themes/synthetic-demo-{1,2,3}/`:
- **Demo 1 (Fashion Store):** Blue/purple colors, Inter font — ✅ WORKS
- **Demo 2 (Tech Store):** Blue/green colors, Roboto font — ❌ FAILS
- **Demo 3 (Beauty Shop):** Purple/pink colors, Poppins font — ❌ FAILS

Each demo has:
- `code.html` with embedded `<script id="tailwind-config">`
- Proper UTF-8 encoding
- Header, hero, footer sections
- ~1040 bytes, 36 lines

### Generated Themes
- `themes/test-theme-1/` — Generated from demo 1 (Fashion Store)
  - 7 files created
  - Backup: `.claude/kiwi/generator/.backups/e536d07d_20260527_140450`

---

## Known Issues Summary

| Issue | Priority | Impact | Status |
|-------|----------|--------|--------|
| Token extraction inconsistency | P0 | 67% failure rate | 🔴 BLOCKING |
| Feedback logging broken | P0 | Cannot train ML | 🔴 BLOCKING |
| Token validation too strict | P1 | Noisy warnings | 🟡 MINOR |
| Test timing issue | P2 | 1 test fails | 🟢 LOW |

---

## Success Criteria for Next Session

✅ **Minimum (Must Have):**
- [ ] Token extraction works for all 3 demos (100% success rate)
- [ ] Feedback logging fixed and tested
- [ ] 3/3 demos generate successfully

✅ **Target (Should Have):**
- [ ] 10+ feedback entries collected
- [ ] ML classifier trained with 80%+ accuracy
- [ ] Optimal confidence threshold identified

✅ **Stretch (Nice to Have):**
- [ ] Full mode (G0 + G1) tested end-to-end
- [ ] 0 CRITICAL violations in generated themes
- [ ] Theme activation tested in LocalWP

---

## Quick Start Commands for Next Session

```bash
# 1. Debug token extraction
python -c "
import sys
sys.path.insert(0, '.claude/kiwi')
from generator.parsers.token_extractor import DesignTokenExtractor
extractor = DesignTokenExtractor()
for i in [1,2,3]:
    print(f'\n=== Demo {i} ===')
    tokens = extractor.extract_from_demo(f'themes/synthetic-demo-{i}')
    print(f'Colors: {len(tokens.get(\"colors\", {}))}')
    print(f'Typography: {len(tokens.get(\"typography\", {}))}')
"

# 2. Test all 3 demos
python -c "
import sys
sys.path.insert(0, '.claude/kiwi')
from generator.demo_orchestrator import DemoThemeGenerator
generator = DemoThemeGenerator()
for i, label in [(1,'Fashion'), (2,'Tech'), (3,'Beauty')]:
    print(f'\n=== {label} ===')
    report = generator.generate_from_demo(
        demo_path=f'themes/synthetic-demo-{i}',
        theme_name=f'test-theme-{i}',
        mode='foundation',
        confidence_threshold=0.7
    )
    print('SUCCESS' if 'error' not in report else f'FAILED: {report[\"error\"]}')
"

# 3. Check feedback count
python -c "
import sys
sys.path.insert(0, '.claude/kiwi')
from memory.db import get_generator_feedback
feedback = get_generator_feedback()
print(f'Feedback entries: {len(feedback)}')
print(f'Ready to train: {len(feedback) >= 10}')
"
```

---

## Context for Next Session

**What the generator does:**
- Extracts design tokens from demo HTML (embedded tailwind.config)
- Detects UI components (header, hero, footer, product-card, etc.)
- Generates WordPress theme files (store-config.php, tailwind.config.js, templates)
- Uses ML classifier to auto-apply high-confidence components
- Flags low-confidence components for manual review

**Current state:**
- Foundation mode partially working (33% success rate)
- Full mode not tested yet
- ML classifier not trained (no feedback data)
- Integration tests passing (6/6)
- Rollback system working (4/5 tests passing)

**Why this matters:**
- Generator will save 65-75% token cost vs manual theme creation
- Enables rapid theme prototyping from HTML demos
- Reduces human error in theme scaffolding
- ML classifier improves over time with feedback

---

**Session prepared:** 2026-05-27 07:06 UTC  
**Previous session:** [HANDOFF-KIWI-UI-GEN-V2-PRODUCTION-TEST-2026-05-27.md](D:\projects\wezone\docs\HANDOFF-KIWI-UI-GEN-V2-PRODUCTION-TEST-2026-05-27.md)  
**Test results:** [TEST-RESULTS.md](D:\projects\wezone\.claude\kiwi\generator\TEST-RESULTS.md)
