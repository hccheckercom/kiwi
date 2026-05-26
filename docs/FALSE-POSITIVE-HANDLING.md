# False Positive Handling Guide

## Overview

Kiwi scanner có 4 cơ chế để giảm false positives:

1. **No-scan comments** — skip violations đã verify
2. **Context-aware scanning** — detect guards/setup code
3. **Confidence scoring** — auto-demote noisy lessons
4. **Pre-check patterns** — chỉ scan files relevant

---

## 1. No-scan Comments

### Inline ignore (skip 1 violation)

```php
// @kiwi-ignore LES-308
$.get(API_BASE + '/sales', function(response) {
    renderSalesList(response.items || []);
});
```

### File-level ignore (skip toàn bộ file)

Đặt trong **10 dòng đầu** của file:

```php
<?php
/**
 * @kiwi-ignore LES-308
 * @kiwi-ignore LES-345
 */
```

### Ignore all lessons

```php
// @kiwi-ignore all
```

**Khi nào dùng:**
- Đã verify không phải bug thật
- Code có guard/validation ở nơi khác
- Legacy code không thể fix ngay

---

## 2. Context-Aware Scanning

### Context guard trong lesson frontmatter

```yaml
scan:
  type: "presence"
  pattern: "\\$\\.ajax\\(|\\$\\.get\\(|\\$\\.post\\("
  exclude_line: "X-WP-Nonce|beforeSend.*nonce"
  context_guard:
    pattern: "\\$\\.ajaxSetup\\(|var headers\\s*=\\s*\\{[^}]*X-WP-Nonce"
    lines_before: 50
    lines_after: 0
```

**Cách hoạt động:**
- Scanner đọc 50 dòng **trước** violation
- Nếu tìm thấy `$.ajaxSetup()` hoặc `var headers = { X-WP-Nonce }` → skip violation
- Phù hợp cho: nonce setup, guard functions, validation wrappers

### Cross-file guard

```yaml
context_guard:
  pattern: "check_ajax_referer|wp_verify_nonce"
  cross_file: true
  lines_before: 10
```

**Cách hoạt động:**
- Scanner tìm callers của function chứa violation
- Check xem caller có guard pattern không
- Phù hợp cho: template parts được include từ file khác

---

## 3. Confidence Scoring

### Automatic tracking

Mỗi khi scan, Kiwi tự động track:
- `total_hits` — tổng số violations
- `false_positive_count` — số lần dismiss
- `confidence` — 1.0 - (FP / total)

### Auto-demote noisy lessons

```python
if confidence < 0.3:
    effective_severity = "SUGGEST"
elif confidence < 0.5 and original_severity == "HIGH":
    effective_severity = "SUGGEST"
```

**Lessons với confidence < 0.3 tự động giảm severity → ít noise hơn.**

### View confidence scores

```powershell
# Xem lessons noisy nhất
python -c "from memory.confidence import get_noisy_lessons; print(get_noisy_lessons(min_fps=3))"

# Xem confidence của 1 lesson
python -c "from memory.confidence import get_confidence; print(get_confidence('LES-308'))"
```

### Manual dismiss (tăng FP count)

```python
from memory.confidence import update_hit

# Mark as false positive
update_hit('LES-308', is_true_positive=False)

# Mark as true positive
update_hit('LES-308', is_true_positive=True)
```

---

## 4. Pre-check Patterns

### Pre-check trong lesson frontmatter

```yaml
scan:
  type: "absence"
  pattern: "if\\s*\\(\\s*''\\s*===\\s*\\$current_password\\s*\\)"
  scope: "packages/*/src/Api/*Controller.php"
  pre_check: "wp_check_password|change_password|current_password"
```

**Cách hoạt động:**
- Scanner chỉ scan files **chứa** `pre_check` pattern
- Giảm 90% files không liên quan
- Tăng tốc scan 5-10x

### Scope patterns best practices

❌ **SAI — quá rộng:**
```yaml
scope: "**/*Controller.php"  # Match mọi package, báo "NO FILES MATCHING" cho mỗi package
```

✅ **ĐÚNG — cụ thể:**
```yaml
scope: "packages/wezone-core/src/Commerce/Cart/*.php"
```

✅ **ĐÚNG — với pre-check:**
```yaml
scope: "packages/*/src/**/*.php"
pre_check: "setShipping|shipping.*rate"  # Chỉ scan files có shipping logic
```

---

## Workflow Giảm False Positives

### Bước 1: Scan + phân tích

```powershell
cd .claude/kiwi
python -m scanner.cli --theme ../../wezone-plugins --severity CRITICAL --json > scan.json
```

### Bước 2: Xác định false positives

Đọc violations, check từng file:
- Có guard/validation ở nơi khác?
- Scope pattern quá rộng?
- Context guard thiếu?

### Bước 3: Fix lessons

**Nếu có guard code:**
```yaml
# Thêm context_guard
context_guard:
  pattern: "function_exists.*wezone_is_active"
  lines_before: 10
```

**Nếu scope quá rộng:**
```yaml
# Cải thiện scope + pre-check
scope: "packages/wezone-core/src/**/*.php"
pre_check: "relevant_function|relevant_pattern"
```

**Nếu không thể fix lesson:**
```php
// Thêm @kiwi-ignore vào code
// @kiwi-ignore LES-XXX
```

### Bước 4: Re-scan để verify

```powershell
python -m scanner.cli --theme ../../wezone-plugins --severity CRITICAL
```

### Bước 5: Update confidence scores

```python
from memory.confidence import update_hit

# Mark false positives
for lesson_id in ['LES-308', 'LES-330', 'LES-357']:
    update_hit(lesson_id, is_true_positive=False)
```

---

## Examples

### Example 1: Nonce setup ở đầu file

**Before:**
```javascript
// flash-sale-admin.js
const API_BASE = '/wp-json/wezone/v1/flash-sale';

// Setup AJAX with nonce (line 12)
$.ajaxSetup({
    beforeSend: function(xhr) {
        xhr.setRequestHeader('X-WP-Nonce', wezoneFlashSaleAdmin.nonce);
    }
});

// Line 39 — báo violation vì không có inline nonce
$.get(API_BASE + '/sales', function(response) {
    renderSalesList(response.items || []);
});
```

**Fix lesson:**
```yaml
context_guard:
  pattern: "\\$\\.ajaxSetup\\("
  lines_before: 50  # Tăng từ 30 → 50 để detect setup xa hơn
```

### Example 2: Scope mismatch

**Before:**
```yaml
scope: "**/*Controller.php"  # Match mọi package
```

**Scanner output:**
```
[packages/wezone-analytics] [NO FILES MATCHING: **/*Controller.php]
[packages/wezone-backup] [NO FILES MATCHING: **/*Controller.php]
...
```

**Fix:**
```yaml
scope: "packages/*/src/Api/*Controller.php"  # Match cấu trúc thật
pre_check: "change_password|wp_check_password"  # Chỉ scan files có password logic
```

### Example 3: Text field vs JSON payload

**Before:**
```yaml
pattern: "sanitize_textarea_field.*\\$_POST"
scope: "**/*.php"
```

**False positives:**
```php
// Theme — text message thật, KHÔNG phải JSON
$message = sanitize_textarea_field( wp_unslash( $_POST['message'] ?? '' ) );
```

**Fix:**
```yaml
scope: "packages/**/*.php"  # Chỉ scan plugins
exclude: "themes/**/*.php"  # Bỏ qua themes
exclude_line: "message|note|description|address|content"  # Bỏ qua text fields
```

---

## Metrics

### False positive rate trước khi cải thiện

```
Total violations: 439 (57 CRITICAL, 261 HIGH, 121 SUGGEST)
False positive rate: ~90% (51/57 CRITICAL)
```

### Sau khi áp dụng 4 cơ chế

**Target:**
- False positive rate < 30%
- Scan time giảm 50% (nhờ pre-check)
- Confidence scoring tự động demote noisy lessons

---

## Best Practices

1. **Luôn thêm pre-check** khi scope rộng
2. **Context guard cho setup code** (nonce, guards, validation)
3. **Exclude patterns cho known safe cases** (text fields, comments)
4. **Track confidence scores** — lessons < 0.5 cần review
5. **Document false positives** — thêm @kiwi-ignore + comment giải thích

---

## Related

- [Scanner Architecture](SCANNER-ARCHITECTURE.md)
- [Lesson Frontmatter Spec](LESSON-SPEC.md)
- [Confidence Scoring API](../memory/confidence.py)