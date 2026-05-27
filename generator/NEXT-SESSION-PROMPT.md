# Next Session: Kiwi UI Generator V2 — Production Validation

## 🎯 Session Objectives

Continue production validation of Kiwi UI Generator V2 after successful integration test fixes.

**Previous session completed:**
- ✅ Fixed 6 bugs in integration tests (6/6 passing)
- ✅ Verified rollback system (4/5 passing)
- ✅ Collected initial metrics (93.1% auto-apply rate)

**This session goals:**
1. **Collect user feedback on real demos** — Test generator with actual theme demos
2. **Train ML classifier** — Once 10+ feedback entries collected
3. **Test full mode end-to-end** — Verify G0 + G1 generation pipeline

---

## 📋 Task Breakdown

### Task 1: Test Generator with Real Demos (P0)

**Goal:** Generate themes from 3 real demo folders, collect feedback data.

**Steps:**
1. **Identify 3 demo folders** with complete structure:
   - Must have: `code.html`, `DESIGN.md`, `screen.png`
   - Prefer: Different industries (beauty, tech, fashion)
   - Check: `themes/*/demos/demo*` or create test demos

2. **Run generator in foundation mode** for each demo:
   ```python
   from generator.demo_orchestrator import DemoThemeGenerator
   
   generator = DemoThemeGenerator()
   
   # Demo 1
   report1 = generator.generate_from_demo(
       demo_path="themes/sfvn/demos/demo1",
       theme_name="test-demo-1",
       mode="foundation",
       confidence_threshold=0.7
   )
   
   # Demo 2
   report2 = generator.generate_from_demo(
       demo_path="themes/trunganh/demos/demo1",
       theme_name="test-demo-2",
       mode="foundation",
       confidence_threshold=0.7
   )
   
   # Demo 3
   report3 = generator.generate_from_demo(
       demo_path="themes/funilux/demos/demo1",
       theme_name="test-demo-3",
       mode="foundation",
       confidence_threshold=0.7
   )
   ```

3. **Review generated output** for each theme:
   - Check `themes/test-demo-*/store-config.php` — tokens extracted correctly?
   - Check `themes/test-demo-*/tailwind.config.js` — Tailwind config valid?
   - Check `themes/test-demo-*/src/main.css` — CSS variables present?
   - Check `themes/test-demo-*/templates/` — PHP templates generated?

4. **Provide feedback** via MCP tool:
   ```python
   from memory.db import update_generator_feedback
   
   # For each generation
   update_generator_feedback(
       gen_id=report1["gen_id"],
       accepted=True,  # or False if issues found
       corrections="Optional: describe what was wrong"
   )
   ```

5. **Document findings** in `generator/TEST-RESULTS.md`:
   - Which demos worked well?
   - Which components were detected correctly?
   - Which components needed manual review?
   - Any patterns in failures?

**Success criteria:**
- 3 themes generated successfully
- Feedback logged for all 3 generations
- Test results documented

---

### Task 2: Train ML Classifier (P0)

**Goal:** Retrain component detection classifier with collected feedback.

**Prerequisites:**
- 10+ feedback entries in database (from Task 1 + previous tests)

**Steps:**
1. **Check feedback count**:
   ```python
   from memory.db import get_generator_feedback
   
   feedback = get_generator_feedback()
   print(f"Total feedback entries: {len(feedback)}")
   
   accepted = sum(1 for f in feedback if f.get('accepted') == 1)
   rejected = sum(1 for f in feedback if f.get('accepted') == 0)
   print(f"Accepted: {accepted}, Rejected: {rejected}")
   ```

2. **If < 10 entries:** Generate more test themes or create synthetic feedback
3. **If >= 10 entries:** Run classifier retraining:
   ```python
   from generator.ml.classifier import retrain_classifier
   
   results = retrain_classifier(force=True)
   print(f"Training complete:")
   print(f"  Accuracy: {results['accuracy']:.2%}")
   print(f"  Precision: {results['precision']:.2%}")
   print(f"  Recall: {results['recall']:.2%}")
   ```

4. **Analyze confidence thresholds**:
   ```python
   from generator.ml.classifier import analyze_confidence_thresholds
   
   analysis = analyze_confidence_thresholds()
   print(f"Recommended threshold: {analysis['recommended_threshold']}")
   ```

5. **Update default threshold** if needed in `demo_orchestrator.py`

**Success criteria:**
- Classifier retrained with 10+ feedback entries
- Accuracy >= 80%
- Optimal confidence threshold identified

---

### Task 3: Test Full Mode End-to-End (P0)

**Goal:** Verify complete G0 + G1 generation pipeline.

**Steps:**
1. **Run generator in full mode**:
   ```python
   from generator.demo_orchestrator import DemoThemeGenerator
   
   generator = DemoThemeGenerator()
   
   report = generator.generate_from_demo(
       demo_path="themes/sfvn/demos/demo1",
       theme_name="test-full-mode",
       mode="full",
       confidence_threshold=0.7
   )
   ```

2. **Verify G0 Foundation files** (16 files):
   - `store-config.php`
   - `tailwind.config.js`
   - `src/main.css`
   - `functions.php`
   - `style.css`
   - `Plugin.php`
   - `templates/header.php`
   - `templates/footer.php`
   - ... (8 more foundation files)

3. **Verify G1 Pages files** (11 files):
   - `templates/home.php`
   - `templates/archive.php`
   - `templates/single.php`
   - `template-parts/hero.php`
   - `template-parts/product-grid.php`
   - ... (6 more page files)

4. **Run Kiwi scan** on generated theme:
   ```powershell
   cd .claude/kiwi
   python -m scanner.cli --theme ../../themes/test-full-mode --platform wp --severity CRITICAL
   ```

5. **Verify 0 CRITICAL violations**

6. **Test theme activation** (if LocalWP available):
   - Copy theme to LocalWP site
   - Activate theme
   - Check homepage renders
   - Check no PHP errors in logs

**Success criteria:**
- Full mode generates 27 files (16 G0 + 11 G1)
- 0 CRITICAL violations in Kiwi scan
- Theme activates without errors

---

## 📊 Expected Metrics After This Session

### Generator Performance
- Total generations: 6+ (3 previous + 3 new)
- Acceptance rate: Target 80%+
- Auto-apply rate: Target 90%+

### ML Classifier
- Training accuracy: Target 80%+
- Precision: Target 85%+
- Recall: Target 75%+

### Component Detection
- Total components detected: 50+
- Total components applied: 45+
- Component types covered: hero, header, footer, product-card, product-grid, categories, flash-sale

---

## 🚨 Known Issues to Watch

### From Previous Session
1. **Test timing issue** — `test_list_backups` fails when backups created in same second
   - Impact: Low (test-only)
   - Fix: Add 1-second delay between backups in test

### Potential Issues This Session
1. **Missing demo folders** — Real themes may not have `demos/demo1/` structure
   - Mitigation: Create test demos manually if needed
   - Structure: `code.html`, `DESIGN.md`, `screen.png`

2. **Insufficient feedback data** — May not reach 10 entries for ML training
   - Mitigation: Generate synthetic feedback or create more test themes

3. **Full mode not implemented** — G1 generation may be incomplete
   - Mitigation: Check `demo_orchestrator.py` for full mode implementation
   - If missing: Implement G1 page generation

---

## 📁 Key Files

### Generator Core
- [demo_orchestrator.py](demo_orchestrator.py) — Main orchestrator
- [parsers/token_extractor.py](parsers/token_extractor.py) — Token extraction
- [parsers/component_detector.py](parsers/component_detector.py) — Component detection
- [converters/store_config_generator.py](converters/store_config_generator.py) — Config generation
- [converters/html_to_php.py](converters/html_to_php.py) — HTML → PHP conversion

### ML System
- [ml/classifier.py](ml/classifier.py) — Component classifier
- [ml/trainer.py](ml/trainer.py) — Training pipeline

### Database
- [../memory/db.py](../memory/db.py) — Feedback storage

### Tests
- [tests/test_integration.py](tests/test_integration.py) — Integration tests (6/6 passing)
- [tests/test_rollback.py](tests/test_rollback.py) — Rollback tests (4/5 passing)

---

## 🎓 Context from Previous Session

### Bugs Fixed
1. Import path errors (relative imports failing in tests)
2. API signature mismatch (`use_cache` parameter removed)
3. DB cleanup issue (UNIQUE constraint on gen_id)
4. Path separator mismatch (Windows backslashes vs forward slashes)
5. Path variable shadowing (`Path` imported twice)
6. Syntax error (duplicate `try:` statement)

### Test Results
- Integration tests: 6/6 passing ✅
- Rollback tests: 4/5 passing ✅ (1 timing issue)

### Production Metrics
- Total generations: 3
- Components detected: 29
- Components applied: 27
- Auto-apply rate: 93.1%

---

## 🚀 How to Start This Session

**Copy-paste this prompt to Claude:**

```
Continue Kiwi UI Generator V2 production validation.

Previous session: Fixed integration tests (6/6 passing), verified rollback system.

This session tasks:
1. Test generator with 3 real demos, collect feedback
2. Train ML classifier once 10+ feedback entries collected
3. Test full mode (G0 + G1) end-to-end

Read NEXT-SESSION-PROMPT.md for detailed steps.
```

---

## ✅ Session Complete Checklist

- [ ] 3 real demos tested with generator
- [ ] Feedback logged for all generations
- [ ] Test results documented in TEST-RESULTS.md
- [ ] ML classifier retrained (if 10+ feedback entries)
- [ ] Confidence threshold optimized
- [ ] Full mode tested end-to-end
- [ ] 0 CRITICAL violations in generated themes
- [ ] Handoff document updated with findings

---

**Session prepared:** 2026-05-27 06:48 UTC  
**Previous handoff:** [HANDOFF-KIWI-UI-GEN-V2-PRODUCTION-TEST-2026-05-27.md](../../docs/HANDOFF-KIWI-UI-GEN-V2-PRODUCTION-TEST-2026-05-27.md)