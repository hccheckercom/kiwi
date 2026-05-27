# Prompt cho Session Tiếp Theo: Kiwi 95→96/100

Tiếp tục nâng cấp Kiwi từ 95/100 lên 96/100.

## Current Status (Verified)
- **Score**: 95/100 (Tier 5)
- **Rollback safety**: 5/5 ✅ COMPLETE
- **Test verification**: ✅ Integrated into agent loop
- **Multi-file rollback**: ✅ Production-tested
- **History tracking**: ✅ Tracked in confidence.db
- **562 lessons**, 26 test files, 95% AST accuracy

## What's Done ✅ (Session 2026-05-27)

### Step 1: Test Verification Integration
- Fixed `test_verifier.py` cho cross-platform (shell=True)
- Fixed project_root detection trong fixer.py
- Memory-based rollback (lưu original_content, restore khi test fail)
- Agent loop enables rollback for non-dry-run
- **Result**: Rollback trigger đúng khi test fail

### Step 2: Multi-File Rollback Production-Tested
- Implemented `BatchRollback` class
- Apply multiple fixes → test once → rollback ALL if fail
- All-or-nothing guarantee verified với 3 files
- **Result**: Batch mode hoạt động đúng

### Step 3: Rollback History Tracking
- Schema: `rollback_count`, `last_rollback_at` columns added
- Functions: `record_rollback()`, `get_rollback_stats()`, `get_high_rollback_lessons()`
- Integration với fixer.py complete
- DB migrated successfully
- **Result**: Rollback events tracked in confidence.db

## Task: Nâng Cấp 95→96/100 (+1 điểm)

### Option 1: Optimize Fix Patterns (RECOMMENDED - High Impact)

**Goal**: Reduce false positives trong top 20 lessons

**Approach**:
1. Query lessons với highest false positive rate:
   ```python
   from memory.confidence import get_confidence_overview
   lessons = get_confidence_overview(min_fps=3)
   # Identify top 20 noisy lessons
   ```

2. For each noisy lesson:
   - Read lesson file
   - Analyze false positive patterns
   - Refine regex pattern để exclude false positives
   - Add context-aware checks
   - Test với known false positives

3. Measure improvement:
   - Re-scan projects
   - Compare false positive rate before/after
   - Target: Reduce FP rate by 30%+

**Estimated gain**: +1 point (high confidence)

**Files to work with**:
- `.claude/kiwi/lessons/{category}/LES-XXX.md` - Lesson files
- `.claude/kiwi/memory/confidence.py` - Confidence scoring
- `.claude/kiwi/scanner/checkers/` - Pattern checkers

---

### Option 2: Expand AST Coverage (Medium Impact)

**Goal**: Add 5 more AST-based checks, improve accuracy to 97%+

**Approach**:
1. Identify patterns that would benefit from AST:
   - Complex control flow checks
   - Variable scope analysis
   - Function call context

2. Implement new AST checks:
   - Add to `.claude/kiwi/ast/php_ast_checker.py`
   - Write tests in `.claude/kiwi/ast/test_ast_checker.py`
   - Integrate into scanner

3. Measure improvement:
   - Run AST test suite
   - Target: 95% → 97% accuracy

**Estimated gain**: +0.5 point

**Files to work with**:
- `.claude/kiwi/ast/php_ast_checker.py` - AST checker
- `.claude/kiwi/ast/test_ast_checker.py` - AST tests

---

### Option 3: Improve Confidence Scoring (Medium Impact)

**Goal**: Factor in rollback rate, time-decay, recent fixes

**Approach**:
1. Update confidence formula:
   ```python
   # Current: confidence = base_confidence * 0.7 + fix_rate * 0.3
   # New: Add rollback penalty + time decay
   confidence = (
       base_confidence * 0.6 +
       fix_rate * 0.2 +
       (1 - rollback_rate) * 0.1 +
       time_decay_factor * 0.1
   )
   ```

2. Implement time decay:
   - Recent violations weighted higher
   - Old violations decay over time

3. Test new scoring:
   - Recalculate all lesson confidence
   - Verify noisy lessons get demoted

**Estimated gain**: +0.5 point

**Files to work with**:
- `.claude/kiwi/memory/confidence.py` - Confidence scoring
- `.claude/kiwi/memory/rollback_tracking.py` - Rollback stats

---

## Recommended Next Steps

**Start with Option 1** (Optimize Fix Patterns) vì:
- Highest impact (+1 point)
- Directly improves user experience (fewer false positives)
- Builds on rollback tracking data we just added
- Clear success metrics

**Workflow**:
1. Query top 20 noisy lessons từ confidence.db
2. For each lesson:
   - Analyze false positive patterns
   - Refine regex/checks
   - Test improvements
3. Measure overall FP reduction
4. Update score assessment

## Reference Files

**Handoff Report**: `.claude/kiwi/HANDOFF-ROLLBACK-INTEGRATION-2026-05-27.md`

**Key Files**:
- `.claude/kiwi/HONEST-RE-ASSESSMENT-2026-05-27.md` - Current assessment (95/100)
- `.claude/kiwi/memory/confidence.py` - Confidence scoring
- `.claude/kiwi/memory/rollback_tracking.py` - Rollback history
- `.claude/kiwi/scanner/fixer.py` - Auto-fix engine with rollback
- `.claude/kiwi/rollback/batch_rollback.py` - Batch rollback manager

**Test Files**:
- `test_rollback_cross_platform.py` - Single-file rollback test
- `test_batch_production.py` - Multi-file rollback test
- `test_rollback_history.py` - History tracking test

## Success Criteria

**For 96/100**:
- False positive rate reduced by 30%+ in top 20 lessons
- OR 5 new AST checks added with 97%+ accuracy
- OR Confidence scoring improved with rollback penalty + time decay
- All existing tests still passing
- Score assessment updated with evidence

## Commands to Start

```bash
# Check current confidence stats
cd .claude/kiwi
python -c "from memory.confidence import get_confidence_overview; print(get_confidence_overview(min_fps=3))"

# Check rollback stats
python -c "from memory.rollback_tracking import get_high_rollback_lessons; print(get_high_rollback_lessons(min_rollbacks=2))"

# Run existing tests
python test_rollback_cross_platform.py
python test_batch_production.py
python test_rollback_history.py
```

---

**Bắt đầu với**: "Tiếp tục nâng cấp Kiwi lên 96/100. Bắt đầu với Option 1: Optimize fix patterns để reduce false positives."
