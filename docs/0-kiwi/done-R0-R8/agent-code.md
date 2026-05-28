# Kiwi Generator — Kế hoạch tái kiến trúc toàn diện

## Context

Kiwi Generator hiện tại (58/100) có nền tảng tốt nhưng 3 vấn đề cốt lõi khiến nó không dùng được trong thực tế:
1. **Dual code path**: G0FoundationGenerator (Python f-string) vs Jinja2 templates — cùng tạo ra 16 files nhưng 2 bộ code riêng biệt, drift không tránh khỏi
2. **Component → PHP vô nghĩa**: `_replace_hardcoded_text` biến mọi text thành `wz_config("key")` giống nhau, icon bị convert sai, không có data binding thực tế
3. **Validator có lỗ hổng**: Layer 3 (Kiwi scan) bị bỏ qua, hex color trong PHP không bị check, G1 generator tự vi phạm GATE

**Mục tiêu cuối cùng**: Kiwi là agent tự tiến hóa — mỗi lần Claude fix lỗi trong generated code → Kiwi tự học → lần sau generate ít lỗi hơn → vòng lặp vô tận → cuối cùng Kiwi tự generate hoàn chỉnh 50 trang Wezone WordPress mà không cần Claude.

**Nền tảng**: 100% Wezone Core WordPress (wz_* functions, không WooCommerce). 50 trang theo blueprint (Cấp 1 + 2 + 3).

---

## Kiến trúc mục tiêu

```
Demo HTML + DESIGN.md (optional)
        ↓
  [LAYER 1] Token Extraction (giữ nguyên — đã tốt)
  DesignTokenExtractor → colors, typography, spacing
        ↓
  [LAYER 2] Blueprint-Driven Generation (THAY MỚI HOÀN TOÀN)
  2 pipelines riêng biệt, share templates:
  ├─ NewThemePipeline: Blueprint spec + industry DNA → generate
  └─ CloneThemePipeline: Demo HTML → extract tokens → apply lên blueprint templates
        ↓
  [LAYER 3] Validation (FIX lỗ hổng)
  - Bật lại Layer 3 (Kiwi scan) trong validate_all()
  - Thêm check hex color trong PHP files
  - Validator tự động fix violations trước khi write
        ↓
  [LAYER 4] Learning Loop (XÂY MỚI — suggest-only mode đầu tiên)
  - Mỗi lần Claude fix generated code → auto-extract lesson candidate
  - Candidate vào queue chờ review (KHÔNG auto-create cho đến khi có 50+ approved)
  - Generator đọc approved lessons trước khi generate → tránh lỗi cũ
        ↓
  [LAYER 5] Template Auto-Improvement (CHỈ BẬT SAU KHI LAYER 4 STABLE)
  - Template patches qua staging pipeline trước khi commit
  - Auto-revert nếu quality score giảm
        ↓
  Output: themes/{slug}/ — 50 trang hoàn chỉnh, 0 CRITICAL violations
```

---

## Quyết định kiến trúc

### 1. Xóa dual code path — Jinja2 là source of truth duy nhất

Lý do:
- Templates là text files → dễ đọc, dễ diff, dễ version control
- Kiwi có thể tự cải thiện templates (edit .j2 files) mà không cần sửa Python code
- `G0FoundationGenerator` và `G1PagesGenerator` bị xóa hoàn toàn

### 2. KHÔNG merge thành 1 god orchestrator

Lý do:
- "New theme" (no demo) và "Clone theme" (has demo) là 2 use cases khác nhau
- Cả hai share Jinja2 templates + data_bindings + validator
- Nhưng pipeline khác nhau: token extraction vs industry DNA lookup

Cấu trúc:
```
generator/
├── pipelines/
│   ├── base.py          # Shared: render templates, validate, write
│   ├── new_theme.py     # Input: input_spec + industry → generate
│   └── clone_theme.py   # Input: demo_path → extract tokens → generate
├── data_bindings.py     # Component → wz_* function mapping
├── validator.py         # 5-layer validation (fix lỗ hổng)
├── learning/
│   ├── fix_extractor.py # Extract lesson candidates từ diffs
│   └── improver.py      # Template auto-patch (Phase 5 only)
├── templates/
│   ├── foundation/      # G0: 16 files
│   └── pages/           # G1: 50 page templates
└── memory/
    └── generation_history  # SQLite table tracking
```

---

## Dependency order (BẮT BUỘC tuân thủ)

```
memory/db.py (thêm generation_history table)
    ↓
data_bindings.py (không dependency)
    ↓
templates/foundation/*.j2 (fix hardcoded colors, thêm guards)
    ↓
validator.py (bật layer 3, thêm hex check — cần templates đúng để test)
    ↓
pipelines/base.py (cần validator + templates)
    ↓
pipelines/new_theme.py (cần base)
pipelines/clone_theme.py (cần base + token extractor)
    ↓
templates/pages/*.j2 (cần data_bindings + validator để validate)
    ↓
learning/fix_extractor.py (cần generation_history table)
    ↓
learning/improver.py (cần fix_extractor stable + staging pipeline)
```

---

## Các phase thực hiện

### Phase 1 — Fix foundation (ưu tiên cao nhất) [2-3 ngày]

**1.1 Thêm `generation_history` table vào memory/db.py**
- Columns: id, theme_slug, file_path, generated_at, violations_at_gen, fix_count, quality_score
- Cần xong trước vì Phase 2+ ghi vào đây

**1.2 Fix Jinja2 templates — G0 Foundation (16 files)**
- Tất cả templates phải dùng CSS vars, không hardcode hex
- `header.php.j2`: `style="color: var(--wz-primary)"` thay vì `style="color: {{ primary_color }}"`
- Thêm template còn thiếu: `footer.php.j2`, `inc/cart.php.j2`
- Đảm bảo tất cả PHP files có `wz_config()` guard ở đầu

**1.3 Fix Validator — bật đầy đủ 5 layers**
- `validate_all()` phải gọi `validate_with_kiwi()` (layer 3)
- Thêm check: hex color trong PHP files (không chỉ check px)
- Thêm check: `wz_config()` guard missing
- Thêm check: dead links (`href="#"`)
- Thêm error handling: nếu Kiwi scan fail → log warning, không crash generator

**1.4 Tạo `data_bindings.py`**
- Dict mapping component type → wz_* functions
- Product card → `$product['name']`, `$product['price']`, `wz_get_permalink($product)`
- Category → `$category['name']`, `wz_get_category_link($category)`
- Config → `wz_config('hero.title')`, `wz_config('phone')`
- Static → PHP array hardcoded (trust badges, USP bar)

**1.5 Tạo `pipelines/base.py` + xóa old orchestrators**
- Base pipeline: render templates → validate → write
- Xóa: `converters/g0_foundation_generator.py`, `converters/g1_pages_generator.py`
- Xóa: `orchestrator.py`, `demo_orchestrator.py`
- Tạo: `pipelines/new_theme.py`, `pipelines/clone_theme.py`

**Verification Phase 1:**
```powershell
# Generate theme từ input spec (new_theme pipeline)
python -m generator.pipelines.new_theme --theme "Test Shop" --primary "#e91e63" --secondary "#9c27b0" --font "Inter"
# Expected: 16 G0 files, 0 CRITICAL violations
$env:PYTHONUTF8=1; python -m scanner.cli --theme themes/test-shop --severity CRITICAL
```

---

### Phase 2a — Blueprint Pages: Cấp 1 Shop (8 trang) [3-4 ngày]

**GATE**: Phase 2a là validation gate. Nếu 8 trang đầu không đạt 0 CRITICAL → DỪNG, fix architecture trước khi scale.

**2a.1 Page template engine**
- Đọc `.claude/blueprint/pages/02-cap1-shop/*.md` → parse sections, data sources, acceptance criteria
- Generate PHP từ spec + data_bindings, không từ HTML parsing
- Mỗi section trong spec → 1 template part PHP

**2a.2 Tạo 8 page templates (Cấp 1 Shop)**
- front-page, archive, single-product, search, cart, checkout, thank-you, order-failed
- Mỗi template dùng `data_bindings.py` cho đúng data source
- Validate từng file ngay sau generate

**2a.3 Error handling cho blueprint spec**
- Nếu page spec thiếu section expected → log warning + skip section (không crash)
- Nếu data_bindings không có mapping cho component type → fallback `wz_config()` + log

**Verification Phase 2a:**
```powershell
# Generate 8 trang Cấp 1 Shop
python -m generator.pipelines.new_theme --theme "Test Shop" --pages cap1-shop
# Expected: 8 page files + template-parts, 0 CRITICAL, 0 hardcoded hex, 0 dead links
$env:PYTHONUTF8=1; python -m scanner.cli --theme themes/test-shop --severity ALL
```

**Exit criteria Phase 2a:**
- [ ] 8 pages generate thành công
- [ ] 0 CRITICAL violations
- [ ] 0 hardcoded hex trong PHP
- [ ] Data bindings đúng (product dùng `$product['name']`, không dùng `wz_config("product.name")`)
- [ ] Mỗi page < 300 dòng
- [ ] Mobile-first (min-width media queries)

---

### Phase 2b — Remaining 42 pages [1-2 tuần]

**Chỉ bắt đầu sau khi Phase 2a đạt exit criteria.**

**2b.1 Cấp 1 Account (6 trang)**
- register, login, verify-email, forgot-password, 404, maintenance

**2b.2 Cấp 1 GMC (5 trang)**
- shipping, returns, privacy, terms, contact

**2b.3 Cấp 2 (20 trang)**
- dashboard, profile, orders, wishlist, addresses, reviews, coupons, etc.

**2b.4 Cấp 3 (11 trang)**
- flash-sale, blog, loyalty, referral, compare, etc.

**Verification Phase 2b:**
```powershell
# Generate full 50 trang
python -m generator.pipelines.new_theme --theme "Test Shop" --pages all
# Expected: 50 page templates, 0 CRITICAL, 0 dead links, 0 hardcoded hex
```

---

### Phase 3 — Learning Loop: Suggest-Only Mode [chạy song song với 2b]

**⚠️ QUAN TRỌNG: Phase 3 bắt đầu ở mode "suggest only" — KHÔNG auto-create lessons.**

**3.1 Fix Extractor**
- File: `generator/learning/fix_extractor.py`
- Input: file trước khi fix + file sau khi fix (diff)
- Output: lesson candidate với pattern (bad code) + fix (good code) + why
- Trigger: PostToolUse hook sau mỗi lần Edit/Write file trong `themes/`

**3.2 Lesson candidate queue**
- Candidates vào `suggested_lessons` table trong SQLite
- Mỗi candidate có: pattern, fix, source_file, confidence_score, created_at
- KHÔNG tự động tạo lesson file — chờ user review qua `kiwi_review_suggestions`

**3.3 Confidence scoring**
- Confidence dựa trên:
  - Pattern clarity (regex-able? → +0.3)
  - Frequency (seen 3+ times? → +0.2)
  - Consistency (same fix mỗi lần? → +0.3)
  - No contradictions (không conflict với existing lessons? → +0.2)
- Threshold hiển thị cho user: confidence ≥ 0.5

**3.4 Generator đọc APPROVED lessons trước khi generate**
- Chỉ đọc lessons đã được approve (status = "approved" trong DB)
- Inject vào Jinja2 context như `{{ kiwi_rules }}`
- Template có thể reference để tránh lỗi đã biết

**Transition criteria sang auto-mode:**
- [ ] ≥ 50 lessons đã manually approved
- [ ] False positive rate < 10% (từ kiwi_confidence)
- [ ] Không có lesson nào bị reject trong 20 suggestions gần nhất

**Verification Phase 3:**
```powershell
# Simulate: fix một file → check lesson candidate được tạo
python -m generator.learning.fix_extractor --before before.php --after after.php
# Expected: lesson candidate trong suggested_lessons table, confidence score hợp lý
```

---

### Phase 4 — Learning Loop: Auto Mode [chỉ sau transition criteria đạt]

**4.1 Auto-create lessons**
- Khi confidence ≥ 0.8 VÀ pattern seen ≥ 3 times → tự động tạo lesson file
- Lesson mới phải qua 5 scans không có false positive trước khi dùng trong generation
- Quarantine period: 7 ngày — nếu bị dismiss trong 7 ngày → auto-disable

**4.2 Generation quality tracking**
- Mỗi lần generate → log vào `generation_history` table
- Track: violations_at_generation, violations_after_claude_fix, fix_count
- Metric: "generation quality score" = 1 - (fix_count / total_sections)

**4.3 Feedback loop**
- File/section có fix rate cao → generator tự động thêm validation chặt hơn cho section đó
- Sau 10 generations → `kiwi_retrain_classifier` tự trigger

---

### Phase 5 — Template Auto-Improvement [chỉ sau Phase 4 stable ≥ 2 tuần]

**⚠️ RỦI RO CAO: Code tự sửa code. Safety mechanisms bắt buộc.**

**5.1 Staging pipeline (BẮT BUỘC)**
- Template patch → generate test theme → validate 0 CRITICAL → mới commit
- Nếu validation fail → patch bị reject, log reason
- Mỗi patch là 1 git commit riêng → dễ revert

**5.2 Auto-revert mechanism**
- Track quality score trước và sau mỗi template patch
- Nếu quality score giảm > 5% sau patch → auto-revert commit
- Alert user khi auto-revert xảy ra

**5.3 Template improvement logic**
- Khi một template bị fix ≥ 3 lần với cùng pattern → propose patch
- Patch phải pass staging pipeline trước khi apply
- Maximum 1 patch per template per day (rate limit)

**5.4 Rollback strategy**
- Git history cho tất cả templates
- `git log --oneline generator/templates/` → trace mọi thay đổi
- Manual rollback: `git revert <commit>` cho bất kỳ patch nào

---

## Files cần tạo/sửa

### Xóa (không còn cần)
- `generator/converters/g0_foundation_generator.py`
- `generator/converters/g1_pages_generator.py`
- `generator/orchestrator.py`
- `generator/demo_orchestrator.py`

### Tạo mới
- `generator/pipelines/__init__.py`
- `generator/pipelines/base.py` — shared render + validate + write
- `generator/pipelines/new_theme.py` — input_spec + industry → generate
- `generator/pipelines/clone_theme.py` — demo_path → extract → generate
- `generator/data_bindings.py` — component → wz_* function mapping
- `generator/learning/__init__.py`
- `generator/learning/fix_extractor.py` — extract lesson candidates từ diffs
- `generator/learning/improver.py` — template auto-patch (Phase 5 only)

### Sửa
- `generator/validator.py` — bật layer 3, thêm hex check trong PHP, error handling
- `generator/templates/foundation/*.j2` — fix hardcoded colors, thêm guards
- `generator/templates/pages/*.j2` — tạo đủ 50 page templates (Phase 2a: 8, Phase 2b: 42)
- `memory/db.py` — thêm `generation_history` table + `suggested_lessons` table
- `mcp_server.py` — update `kiwi_generate_theme` tool để dùng new pipelines

---

## Performance budget

| Operation | Target | Max acceptable |
|-----------|--------|----------------|
| G0 Foundation (16 files) | < 30s | 60s |
| Single page generate + validate | < 10s | 20s |
| Full 50 pages | < 5 min | 10 min |
| Kiwi scan (layer 3) per file | < 2s | 5s |
| Fix extractor (per diff) | < 3s | 10s |

Nếu vượt max acceptable → profile và optimize trước khi tiếp tục.

---

## Compatibility với MCP tools hiện tại

| Tool | Thay đổi |
|------|----------|
| `kiwi_generate_theme` | Update: gọi `pipelines/new_theme.py` thay vì old orchestrator |
| `kiwi_generate_from_demo` | Update: gọi `pipelines/clone_theme.py` thay vì demo_orchestrator |
| `kiwi_check` | Không đổi |
| `kiwi_scan` | Không đổi |
| `kiwi_feedback` | Update: feed vào fix_extractor nếu có corrections |

**Migration path**: Giữ old orchestrators hoạt động cho đến khi new pipelines pass Phase 1 verification. Sau đó xóa old code + update MCP tools trong 1 commit.

---

## Metric & Exit Criteria cuối cùng

| Metric | Target |
|--------|--------|
| Generation quality score | ≥ 0.9 (≤ 10% sections cần Claude fix) |
| CRITICAL violations sau generate | 0 |
| Lesson count (auto-created) | Tăng theo thời gian |
| Template patch success rate | ≥ 90% (pass staging) |
| False positive rate (learning) | < 10% |

---

## Roadmap đến autonomy

| Giai đoạn | Trigger chuyển tiếp | Mô tả |
|-----------|---------------------|--------|
| 1 (hiện tại) | — | Claude generate + fix, Kiwi học (suggest-only) |
| 2 | 50+ approved lessons, quality ≥ 0.85 | Kiwi generate, Claude review + fix ít hơn |
| 3 | quality ≥ 0.95, auto-lessons stable 1 tháng | Kiwi generate + self-validate, Claude approve |
| 4 | quality ≥ 0.98, 0 revert trong 3 tháng | Kiwi fully autonomous, Claude là fallback |

Mỗi transition cần đạt trigger criteria + user explicit approval. Không tự động chuyển giai đoạn.
