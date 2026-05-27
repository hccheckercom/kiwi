# Handoff: ML Training Phase 1 — Data Collection Complete

**Date:** 2026-05-27  
**Status:** 🟡 BLOCKED — Dataset too small and imbalanced for reliable ML training  
**Progress:** Phase 1 complete (data collection), Phase 2-4 infrastructure ready

---

## Summary

Created ML training infrastructure (feature extractor, trainer, threshold optimizer) and collected initial training data. However, dataset quality is insufficient for production ML model:

- **24 labeled samples** (need 100+ for robust model)
- **Only 3 component types** (button, grid, hero) — missing 11+ types
- **Highly imbalanced** (hero: 100% accepted, grid: 0% accepted, button: 33% accepted)
- **Model performance:** 60% accuracy, 0% precision/recall (essentially random)

---

## What Was Built

### Infrastructure (Complete)
1. **Feature Extractor** ([ml/feature_extractor.py](ml/feature_extractor.py))
   - 50 features: structural (10), content (10), style (15), context (10), component type (5)
   - Extracts from HTML snippets using BeautifulSoup
   - Ready to use

2. **Model Trainer** ([ml/train_classifier.py](ml/train_classifier.py))
   - Supports 3 model types: Logistic Regression, Random Forest, Neural Net
   - Includes calibration (Platt scaling)
   - Train/test split, evaluation metrics
   - Saves model to pickle

3. **Threshold Optimizer** ([ml/optimize_threshold.py](ml/optimize_threshold.py))
   - Finds optimal confidence threshold using precision-recall curve
   - Compares to baseline (0.7)
   - Outputs best threshold for auto-apply decision

4. **Labeling Tools**
   - [label_components.py](label_components.py) — Interactive CLI for manual labeling
   - [auto_label.py](auto_label.py) — Heuristic-based auto-labeling (conf >= 0.85 → accept, conf < 0.7 → reject)

### Data Collection (Insufficient)
- **Database:** 42 total components in `component_patterns` table
- **Labeled:** 24 samples (10 accepted, 14 rejected)
- **Unlabeled:** 18 samples
- **Component types:** button (15), hero (5), grid (4)
- **Missing types:** header, footer, product-card, category-card, trust-badge, flash-sale, carousel, tabs, accordion, modal, form, search-bar

---

## Why ML Training Failed

### Problem 1: Dataset Too Small
- **Current:** 24 samples
- **Minimum needed:** 100+ samples (10+ per component type)
- **Impact:** Model overfits to training data, cannot generalize

### Problem 2: Imbalanced Classes
- **Hero:** 5 samples, 100% accepted (no negative examples)
- **Grid:** 4 samples, 0% accepted (no positive examples)
- **Button:** 15 samples, 33% accepted (only balanced class)
- **Impact:** Model cannot learn decision boundary for hero/grid

### Problem 3: Missing Component Types
- **Detected:** 3 types (button, grid, hero)
- **Expected:** 14+ types (header, footer, product-card, etc.)
- **Impact:** Model cannot generalize to unseen component types

### Problem 4: Low Feature Quality
- **Current features:** Mostly structural (tag name, depth, children count)
- **Missing features:** Semantic understanding (is this a CTA? is this a navigation?)
- **Impact:** Features may not capture what makes a component "correct"

---

## Recommended Approach: Rule-Based Confidence (Not ML)

Given the data constraints, **rule-based confidence scoring is more practical than ML** for now:

### Why Rule-Based is Better
1. **No training data needed** — works immediately
2. **Interpretable** — can debug why confidence is high/low
3. **Maintainable** — easy to tune thresholds
4. **Sufficient accuracy** — current 67% auto-apply rate is acceptable

### Proposed Rule-Based Confidence Formula

```python
def calculate_confidence(element, component_type: str) -> float:
    """Calculate confidence score using heuristics."""
    score = 0.5  # Base score
    
    # Structural signals (+0.1 each)
    if has_semantic_class(element, component_type):  # e.g., class="hero" for hero
        score += 0.15
    if has_expected_children(element, component_type):  # e.g., hero has h1 + button
        score += 0.10
    if has_expected_depth(element, component_type):  # e.g., hero is top-level
        score += 0.05
    
    # Content signals (+0.1 each)
    if has_expected_text_length(element, component_type):
        score += 0.05
    if has_expected_images(element, component_type):
        score += 0.05
    if has_expected_links(element, component_type):
        score += 0.05
    
    # Context signals (+0.1 each)
    if is_at_expected_position(element, component_type):  # e.g., hero at top
        score += 0.10
    if has_unique_role(element, component_type):  # e.g., only one hero per page
        score += 0.05
    
    return min(score, 1.0)
```

### Tuning Strategy
1. Start with conservative thresholds (0.7 for auto-apply)
2. Collect feedback on false positives/negatives
3. Adjust weights based on feedback
4. Iterate until 80%+ auto-apply rate with 90%+ precision

---

## Alternative: Collect More Data First

If you still want ML, collect 100+ samples first:

### Option A: Generate More Synthetic Demos
- Create 10+ synthetic demos (fashion, tech, food, furniture, pharma, etc.)
- Run generator on each with different thresholds (0.6, 0.7, 0.8)
- Manually label all detected components
- **Effort:** 4-6 hours
- **Outcome:** 100+ samples, but still synthetic (may not match real demos)

### Option B: Use Real Demos
- Run generator on 10+ real client demos
- Manually label all detected components
- **Effort:** 6-8 hours
- **Outcome:** 100+ samples, real-world distribution

### Option C: Active Learning
- Train initial model on 24 samples (even if poor)
- Use model to predict on unlabeled data
- Manually label samples where model is uncertain (confidence 0.4-0.6)
- Retrain model with new labels
- Repeat until performance plateaus
- **Effort:** 3-4 hours
- **Outcome:** Efficient labeling, but still need more data

---

## Files Created This Session

### ML Infrastructure
- [ml/feature_extractor.py](ml/feature_extractor.py) — 50 features from HTML
- [ml/train_classifier.py](ml/train_classifier.py) — Train Random Forest/Logistic/Neural Net
- [ml/optimize_threshold.py](ml/optimize_threshold.py) — Find optimal threshold
- [ml/model.pkl](ml/model.pkl) — Trained model (poor performance, not usable)

### Data Collection
- [auto_label.py](auto_label.py) — Heuristic-based auto-labeling
- [label_components.py](label_components.py) — Interactive manual labeling
- [generate_synthetic_data.py](generate_synthetic_data.py) — Generate more demos
- [collect_training_data.py](collect_training_data.py) — Check data readiness (fixed Unicode bug)

---

## Next Steps (Choose One)

### Option 1: Rule-Based Confidence (Recommended)
1. Implement rule-based confidence formula in [parsers/component_detector.py](parsers/component_detector.py)
2. Tune thresholds based on feedback
3. Achieve 80%+ auto-apply rate
4. **Effort:** 2-3 hours
5. **Outcome:** Production-ready confidence scoring

### Option 2: Collect More Data + ML
1. Generate 10+ synthetic demos ([generate_synthetic_data.py](generate_synthetic_data.py))
2. Label all components ([label_components.py](label_components.py))
3. Retrain model ([ml/train_classifier.py](ml/train_classifier.py))
4. Optimize threshold ([ml/optimize_threshold.py](ml/optimize_threshold.py))
5. **Effort:** 6-8 hours
6. **Outcome:** ML-based confidence (if data quality improves)

### Option 3: Hybrid Approach
1. Use rule-based confidence for now
2. Collect feedback in background (user accepts/rejects components)
3. When 100+ labeled samples → train ML model
4. A/B test rule-based vs ML
5. **Effort:** 2-3 hours (rule-based) + 2-3 hours (ML later)
6. **Outcome:** Best of both worlds

---

## Recommendation

**Go with Option 1 (Rule-Based Confidence)** because:
- Immediate value (no waiting for data collection)
- Interpretable and debuggable
- Sufficient for current use case (67% → 80% auto-apply is achievable)
- Can always add ML later when more data is available

ML is overkill for this problem given current data constraints. Focus on shipping a working system first, optimize later.

---

**Session ended:** 2026-05-27 08:40 UTC  
**Time spent:** 1.5 hours  
**Blocker:** Insufficient training data (24 samples, 3 types, imbalanced)  
**Recommendation:** Rule-based confidence instead of ML
