# Handoff: Kiwi UI Generator V2 — ML Training Task

**Date:** 2026-05-27  
**Status:** 🟡 READY TO START — Infrastructure complete, need to collect data & train  
**Goal:** Achieve 15/15 points in ML System category (currently 5/15)

---

## 🎯 Objective

Train ML classifier to optimize component detection confidence scores, improving auto-apply rate from 67% to 80%+.

**Current State:**
- ✅ Feedback infrastructure working (12 entries logged)
- ✅ Database schema ready
- ✅ Component detection working (8 components detected per demo)
- ❌ 0 labeled samples (need 20+)
- ❌ Classifier not trained

**Target State:**
- ✅ 20+ labeled samples collected
- ✅ ML classifier trained (scikit-learn or simple neural net)
- ✅ Confidence thresholds optimized (precision/recall)
- ✅ A/B test: rule-based vs ML-based
- ✅ 15/15 points in ML System category

---

## 📊 Current Metrics

### Feedback Database
**Location:** `.claude/kiwi/memory/kiwi.db`

**Tables:**
- `generator_feedback` — Generation runs (gen_id, demo_path, theme_name, mode, components_detected, components_applied)
- `component_patterns` — Detected components (gen_id, component_type, html_snippet, confidence, auto_applied, user_accepted)

**Current Data:**
```sql
SELECT COUNT(*) FROM generator_feedback;  -- 12 entries
SELECT COUNT(*) FROM component_patterns WHERE user_accepted IS NOT NULL;  -- 0 labeled
```

**Problem:** `user_accepted` field is NULL for all entries — need user feedback to label data.

### Component Detection Performance
- **Components detected:** 6-8 per demo
- **Auto-apply rate:** 67% (4/6 components with threshold 0.7)
- **Manual review rate:** 33% (2/6 components below threshold)
- **Success rate:** 100% (no crashes, no false positives reported)

---

## 🚀 Implementation Plan

### Phase 1: Data Collection (2-3 hours)

**Goal:** Collect 20+ labeled samples from real user feedback

**Tasks:**
1. **Create feedback UI** (optional — can use CLI)
   - Show generated components to user
   - Ask: "Is this component correct?" (Yes/No)
   - Store answer in `component_patterns.user_accepted`

2. **Generate synthetic demos** (faster alternative)
   - Create 5-10 more synthetic demos (fashion, tech, food, furniture, etc.)
   - Run generator on each demo
   - Manually label components (you know ground truth)
   - Insert labels into database

3. **Use existing test demos**
   - Run generator on `synthetic-demo-1`, `synthetic-demo-2`
   - Manually inspect generated components
   - Label each component as correct/incorrect
   - Update database

**Script to run:**
```powershell
cd .claude/kiwi/generator
python collect_training_data.py --demos synthetic-demo-1,synthetic-demo-2 --label-mode manual
```

**Expected output:**
- 20+ labeled samples in `component_patterns` table
- Mix of positive (correct) and negative (incorrect) examples
- Balanced across component types (hero, button, header, footer, etc.)

### Phase 2: Feature Engineering (1 hour)

**Goal:** Extract features from HTML snippets for ML training

**Features to extract:**
1. **Structural features:**
   - Tag name (div, section, header, footer, button, etc.)
   - Number of children
   - Depth in DOM tree
   - Has ID/class attributes

2. **Content features:**
   - Text length
   - Has images
   - Has links
   - Has form elements

3. **Style features:**
   - Class names (hero, banner, cta, product-card, etc.)
   - Inline styles
   - Tailwind classes

4. **Context features:**
   - Position in page (top, middle, bottom)
   - Siblings count
   - Parent tag name

**Script to create:**
```python
# .claude/kiwi/generator/ml/feature_extractor.py
from bs4 import BeautifulSoup
import numpy as np

class FeatureExtractor:
    def extract_features(self, html_snippet: str) -> np.ndarray:
        soup = BeautifulSoup(html_snippet, 'html.parser')
        root = soup.find()
        
        features = [
            self._tag_name_feature(root),
            self._num_children(root),
            self._depth(root),
            self._has_id(root),
            self._has_class(root),
            self._text_length(root),
            self._has_images(root),
            self._has_links(root),
            self._class_names_feature(root),
            # ... more features
        ]
        
        return np.array(features)
```

### Phase 3: Model Training (1-2 hours)

**Goal:** Train classifier to predict component type and confidence

**Model Options:**

**Option 1: Logistic Regression (simplest)**
```python
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import train_test_split

# Load data
X, y = load_training_data()  # Features, labels

# Split
X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2)

# Train
model = LogisticRegression()
model.fit(X_train, y_train)

# Evaluate
accuracy = model.score(X_test, y_test)
print(f"Accuracy: {accuracy:.2%}")
```

**Option 2: Random Forest (better accuracy)**
```python
from sklearn.ensemble import RandomForestClassifier

model = RandomForestClassifier(n_estimators=100)
model.fit(X_train, y_train)
```

**Option 3: Neural Net (best accuracy, more complex)**
```python
from sklearn.neural_network import MLPClassifier

model = MLPClassifier(hidden_layer_sizes=(64, 32), max_iter=1000)
model.fit(X_train, y_train)
```

**Recommendation:** Start with Logistic Regression, upgrade to Random Forest if accuracy < 80%.

### Phase 4: Confidence Calibration (1 hour)

**Goal:** Convert model predictions to calibrated confidence scores

**Problem:** Raw model probabilities may not be well-calibrated (e.g., 0.9 prediction != 90% accuracy)

**Solution:** Use Platt scaling or isotonic regression
```python
from sklearn.calibration import CalibratedClassifierCV

# Wrap model with calibration
calibrated_model = CalibratedClassifierCV(model, method='sigmoid', cv=5)
calibrated_model.fit(X_train, y_train)

# Now predict_proba() returns calibrated probabilities
confidence = calibrated_model.predict_proba(X_test)[:, 1]
```

### Phase 5: Threshold Optimization (1 hour)

**Goal:** Find optimal confidence threshold for auto-apply

**Metrics:**
- **Precision:** Of components auto-applied, how many are correct?
- **Recall:** Of correct components, how many are auto-applied?
- **F1 Score:** Harmonic mean of precision and recall

**Script:**
```python
from sklearn.metrics import precision_recall_curve, f1_score

# Get predictions
y_pred_proba = model.predict_proba(X_test)[:, 1]

# Try different thresholds
thresholds = np.arange(0.5, 1.0, 0.05)
best_f1 = 0
best_threshold = 0.7

for threshold in thresholds:
    y_pred = (y_pred_proba >= threshold).astype(int)
    f1 = f1_score(y_test, y_pred)
    
    if f1 > best_f1:
        best_f1 = f1
        best_threshold = threshold

print(f"Best threshold: {best_threshold} (F1: {best_f1:.2%})")
```

**Expected result:** Optimal threshold between 0.6-0.8

### Phase 6: Integration (1 hour)

**Goal:** Replace rule-based confidence with ML-based confidence

**Files to modify:**
1. [parsers/component_detector.py](.claude/kiwi/generator/parsers/component_detector.py)
   - Add `use_ml` parameter (default: False for backward compatibility)
   - Load trained model from disk
   - Use model to predict confidence instead of rule-based heuristics

2. [demo_orchestrator.py](.claude/kiwi/generator/demo_orchestrator.py)
   - Add `use_ml_confidence` parameter
   - Pass to component_detector

**Example:**
```python
# component_detector.py
class ComponentDetector:
    def __init__(self, use_ml: bool = False):
        self.use_ml = use_ml
        if use_ml:
            self.model = self._load_model()
    
    def _calculate_confidence(self, element, component_type):
        if self.use_ml:
            features = self.feature_extractor.extract_features(str(element))
            confidence = self.model.predict_proba([features])[0][1]
            return confidence
        else:
            # Fallback to rule-based
            return self._rule_based_confidence(element, component_type)
```

### Phase 7: A/B Testing (1 hour)

**Goal:** Compare rule-based vs ML-based performance

**Test Setup:**
1. Run generator on 5 test demos with `use_ml=False` (rule-based)
2. Run generator on same 5 demos with `use_ml=True` (ML-based)
3. Compare metrics:
   - Auto-apply rate
   - Precision (manual inspection)
   - User satisfaction (if available)

**Script:**
```powershell
# Rule-based
python test_full_mode.py --use-ml false --output results_rule_based.json

# ML-based
python test_full_mode.py --use-ml true --output results_ml_based.json

# Compare
python compare_results.py results_rule_based.json results_ml_based.json
```

**Success Criteria:**
- ML-based auto-apply rate >= 80% (vs 67% rule-based)
- ML-based precision >= 90%
- No increase in false positives

---

## 📁 Files to Create/Modify

### New Files
1. `.claude/kiwi/generator/ml/feature_extractor.py` — Extract features from HTML
2. `.claude/kiwi/generator/ml/train_classifier.py` — Train ML model
3. `.claude/kiwi/generator/ml/calibrate_confidence.py` — Calibrate probabilities
4. `.claude/kiwi/generator/ml/optimize_threshold.py` — Find optimal threshold
5. `.claude/kiwi/generator/ml/model.pkl` — Trained model (pickle)
6. `.claude/kiwi/generator/compare_results.py` — A/B test comparison

### Modified Files
1. [parsers/component_detector.py](.claude/kiwi/generator/parsers/component_detector.py) — Add ML mode
2. [demo_orchestrator.py](.claude/kiwi/generator/demo_orchestrator.py) — Add `use_ml_confidence` param
3. [collect_training_data.py](.claude/kiwi/generator/collect_training_data.py) — Add labeling UI

---

## 🐛 Known Challenges

### 1. Small Dataset (P0)
**Problem:** 20 samples may not be enough for robust ML model  
**Solution:** Generate more synthetic demos, or use data augmentation (rotate, flip, crop HTML snippets)

### 2. Imbalanced Classes (P1)
**Problem:** Some component types (hero, button) are common, others (carousel, tabs) are rare  
**Solution:** Use class weights in model training, or oversample rare classes

### 3. Overfitting (P1)
**Problem:** Model may memorize training data instead of learning patterns  
**Solution:** Use cross-validation, regularization, or ensemble methods

### 4. Feature Engineering (P2)
**Problem:** Hard to extract good features from HTML  
**Solution:** Use pre-trained embeddings (BERT, GPT) or hand-craft domain-specific features

---

## 📊 Success Metrics

### Before ML Training (Current)
- Auto-apply rate: 67%
- Manual review rate: 33%
- Precision: Unknown (no labeled data)
- ML System score: 5/15

### After ML Training (Target)
- Auto-apply rate: 80%+
- Manual review rate: 20%
- Precision: 90%+
- ML System score: 15/15

---

## 🚀 Quick Start Commands

```powershell
# 1. Check ML readiness
cd .claude/kiwi/generator
python check_ml_readiness.py

# 2. Collect training data (manual labeling)
python collect_training_data.py --demos synthetic-demo-1,synthetic-demo-2 --label-mode manual

# 3. Train classifier
python ml/train_classifier.py --model logistic --output ml/model.pkl

# 4. Optimize threshold
python ml/optimize_threshold.py --model ml/model.pkl --output ml/best_threshold.txt

# 5. Test ML mode
python test_full_mode.py --use-ml true

# 6. A/B test
python compare_results.py results_rule_based.json results_ml_based.json
```

---

## 📚 References

### Existing Files
- [check_ml_readiness.py](.claude/kiwi/generator/check_ml_readiness.py) — Check if ready to train
- [collect_training_data.py](.claude/kiwi/generator/collect_training_data.py) — Collect labeled samples
- [parsers/component_detector.py](.claude/kiwi/generator/parsers/component_detector.py) — Component detection logic
- [demo_orchestrator.py](.claude/kiwi/generator/demo_orchestrator.py) — Main orchestrator

### Documentation
- [HANDOFF-PHASE3-COMPLETE-2026-05-27.md](.claude/kiwi/generator/HANDOFF-PHASE3-COMPLETE-2026-05-27.md) — Phase 3 completion
- [README.md](.claude/kiwi/generator/README.md) — Main documentation

### External Resources
- [scikit-learn Logistic Regression](https://scikit-learn.org/stable/modules/generated/sklearn.linear_model.LogisticRegression.html)
- [scikit-learn Random Forest](https://scikit-learn.org/stable/modules/generated/sklearn.ensemble.RandomForestClassifier.html)
- [scikit-learn Calibration](https://scikit-learn.org/stable/modules/calibration.html)
- [Precision-Recall Curve](https://scikit-learn.org/stable/modules/generated/sklearn.metrics.precision_recall_curve.html)

---

## 💡 Tips for Next Session

1. **Start with synthetic data** — Faster than waiting for real user feedback
2. **Keep it simple** — Logistic Regression is often good enough
3. **Focus on precision** — False positives are worse than false negatives (user can always manually apply)
4. **Calibrate confidence** — Raw probabilities are often overconfident
5. **A/B test thoroughly** — Don't deploy ML model without comparing to baseline

---

**Session prepared:** 2026-05-27 08:35 UTC  
**Estimated time:** 8-10 hours total  
**Difficulty:** Medium (ML basics + feature engineering)  
**Blocker:** Need 20+ labeled samples before training
