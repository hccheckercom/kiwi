# Kiwi UI Generator V2 — Production Test Results

**Session Date:** 2026-05-27  
**Test Objective:** Validate generator with real demos, collect feedback, train ML classifier

---

## Task 1: Test Generator with Real Demos

### Test Setup
Created 3 synthetic demos with embedded tailwind config:
- **Demo 1:** Fashion Store (Inter font, blue/purple colors)
- **Demo 2:** Tech Store (Roboto font, blue/green colors)  
- **Demo 3:** Beauty Shop (Poppins font, purple/pink colors)

All demos had identical structure:
- `code.html` with `<script id="tailwind-config">` containing `tailwind.config`
- Proper UTF-8 encoding
- Header, hero, footer sections

### Test Results

| Demo | Status | Gen ID | Files | Components Detected | Components Applied | Manual Review |
|------|--------|--------|-------|---------------------|-------------------|---------------|
| Fashion | ✅ SUCCESS | e536d07d | 7 | 6 | 4 | 2 |
| Tech | ❌ FAILED | - | - | - | - | - |
| Beauty | ❌ FAILED | - | - | - | - | - |

**Success Rate:** 1/3 (33%)

### Failure Analysis

**Demos 2 and 3 failed with identical error:**
```
WARNING: Failed to parse tailwind.config: Expecting ',' delimiter: line 10 column 18
WARNING: Missing or empty token category: colors
WARNING: Missing or empty token category: typography
WARNING: Missing or empty token category: spacing
WARNING: Missing or empty token category: borderRadius
FAILED: Design token validation failed
```

**Root Cause Investigation:**
1. All 3 demos have identical HTML structure
2. Demo 1 succeeded, demos 2 and 3 failed with same error
3. File sizes similar (1036-1041 bytes)
4. All have proper `id="tailwind-config"` attribute
5. All have valid `tailwind.config = {...};` syntax

**Suspected Issues:**
- Token extractor may have state/caching bug
- `_normalize_js_object()` method may not handle all cases consistently
- Regex extraction in `token_extractor.py:84` uses `$` anchor which may fail with trailing whitespace

### Demo 1 Success Details

**Generation Report:**
- Gen ID: `e536d07d`
- Mode: `foundation`
- Confidence threshold: `0.7`
- Backup created: `.claude/kiwi/generator/.backups/e536d07d_20260527_140450`

**Files Created (7):**
1. `themes/test-theme-1/store-config.php`
2. `themes/test-theme-1/tailwind.config.js`
3. `themes/test-theme-1/src/main.css`
4. `themes/test-theme-1/functions.php`
5. `themes/test-theme-1/style.css`
6. `themes/test-theme-1/Plugin.php`
7. (1 more foundation file)

**Components Detected (6):**
- Header
- Hero
- Footer
- (3 more components)

**Components Applied (4):**
- Auto-applied with confidence >= 0.7

**Manual Review Required (2):**
- Components with confidence < 0.7

**Warnings:**
- Failed to parse tailwind.config (JSON delimiter issue)
- Missing borderRadius tokens
- Only 1 color found (expected 30+)
- Only 1 typography scale found (expected 5+)
- Failed to log feedback: 'html' key error

---

## Task 2: Train ML Classifier

**Status:** ⏸️ BLOCKED

**Reason:** Insufficient feedback data
- Need: 10+ feedback entries
- Have: 1 successful generation (no feedback logged due to 'html' key error)

**Blocker:** Feedback logging failed with error: `'html'`
- Suggests missing key in feedback data structure
- Prevents collecting training data for ML classifier

**Next Steps:**
1. Fix feedback logging bug in `demo_orchestrator.py`
2. Generate 10+ successful themes
3. Collect feedback for each generation
4. Run `retrain_classifier(force=True)`

---

## Task 3: Test Full Mode End-to-End

**Status:** ⏸️ NOT STARTED

**Reason:** Foundation mode issues must be resolved first
- Only 33% success rate in foundation mode
- Token extraction failing inconsistently
- Feedback logging broken

**Planned Steps:**
1. Fix token extraction consistency
2. Fix feedback logging
3. Test full mode (G0 + G1) with working demo
4. Run Kiwi scan on generated theme
5. Verify 0 CRITICAL violations

---

## Known Issues

### 1. Token Extraction Inconsistency (P0)
**Impact:** 67% failure rate  
**Symptoms:**
- Demo 1 succeeds, demos 2 and 3 fail with identical structure
- Error: "Expecting ',' delimiter: line 10 column 18"
- Suggests state/caching issue in token extractor

**Potential Fixes:**
- Review `_normalize_js_object()` method in `token_extractor.py`
- Fix regex in line 84 (remove `$` anchor or handle trailing whitespace)
- Add better error messages showing what was extracted

### 2. Feedback Logging Failure (P0)
**Impact:** Cannot collect training data for ML classifier  
**Error:** `'html'` key missing  
**Location:** `demo_orchestrator.py` feedback logging

**Potential Fixes:**
- Check feedback data structure in `memory/db.py`
- Ensure all required keys are present before logging
- Add try/except with better error handling

### 3. Token Validation Too Strict (P1)
**Impact:** Warnings for minimal demos  
**Symptoms:**
- "Only 1 colors found (expected 30+)"
- "Only 1 typography scales found (expected 5+)"

**Recommendation:**
- Reduce thresholds for minimal demos
- Or make these warnings non-blocking

---

## Metrics Summary

### Generator Performance
- Total generations attempted: 3
- Successful generations: 1
- Success rate: 33%
- Files created per success: 7
- Components detected per success: 6
- Auto-apply rate: 67% (4/6 components)

### ML Classifier
- Training data collected: 0 (feedback logging failed)
- Target: 10+ feedback entries
- Status: Blocked

### Component Detection
- Total components detected: 6
- Total components applied: 4
- Component types: header, hero, footer, (3 more)

---

## Recommendations

### Immediate (P0)
1. **Fix token extraction consistency**
   - Debug why identical structure fails for demos 2 and 3
   - Add unit tests for `_normalize_js_object()`
   - Improve error messages to show extracted content

2. **Fix feedback logging**
   - Identify missing 'html' key requirement
   - Add proper error handling
   - Test feedback collection end-to-end

### Short-term (P1)
3. **Improve token validation**
   - Adjust thresholds for minimal demos
   - Make warnings non-blocking
   - Add "minimal mode" for simple demos

4. **Add integration tests**
   - Test with multiple demos in sequence
   - Verify no state leakage between generations
   - Test feedback logging

### Long-term (P2)
5. **Enhance token extractor**
   - Support multiple tailwind config formats
   - Better JavaScript-to-JSON conversion
   - Fallback to CSS variable extraction

6. **ML classifier improvements**
   - Collect diverse training data
   - Test with different component types
   - Optimize confidence thresholds

---

## Next Session Tasks

1. Debug token extraction failure (demos 2 and 3)
2. Fix feedback logging bug
3. Re-run all 3 demos successfully
4. Collect feedback for 10+ generations
5. Train ML classifier
6. Test full mode (G0 + G1)
7. Run Kiwi scan on generated themes

---

**Session Status:** INCOMPLETE  
**Blockers:** Token extraction inconsistency, feedback logging failure  
**Success Criteria Met:** 1/3 (generator works for 1 demo)  
**Ready for Production:** ❌ NO (33% success rate too low)