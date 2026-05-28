# Phase R6 — Graduated Autonomy [1 tuần]

## Audit Status (2026-05-28)

| Check | Result |
|-------|--------|
| R0-R5 modules | 12 files, all healthy |
| SQLite tables | 13 (schema.sql) |
| Tests | 51 passed, 4.98s |
| LLM cost | 0 |
| Latency | ~50ms (throttled, WAL) |
| Closed loop | Observe → Learn → Calibrate → Act → Self-Improve ✓ |

### Issues Found in Original Plan (Fixed Below)

1. `code_drafter.py` imported from `.memory` — module doesn't exist → use `_get_conn()` from `session_logger`
2. `approval_tracker.py` called undefined `get_trust_baseline()` → use `_get_trust_baseline` from `calibrator`
3. Plan referenced `adjust_trust_baseline` → actual function is `_set_trust_baseline` in `calibrator.py`
4. No Windows path normalization in file reads → add `Path().resolve()` handling
5. Missing safety guard: must Kiwi-scan generated code before output
6. `determine_output_level` used `brief.content.get('target')` → actual field is `context.task_type` via `KiwiOutput.content['target']` (correct, but needs null-safety)

---

## Mục đích

Khi trust tăng, Kiwi output **nhiều hơn brief** — tiến tới draft code.
Đây là evolution tự nhiên: Level 3 brief đã gần như là spec đầy đủ → chỉ cần thêm 1 bước render code.

## Dependencies

- **R1 (Context Assembly)** — cần brief output ✓
- **R3 (Trust Calibration)** — cần trust score ổn định ✓
- **R5 (Brief Quality)** — cần distilled rules + cross-theme patterns ✓
- **Existing: cross_theme.py** — structure + bindings data ✓

## Files tạo mới

```
agent/reasoning/
├── autonomy.py            # graduated output based on trust
├── code_drafter.py        # generate draft code từ brief + cross-theme data
├── approval_tracker.py    # track Claude's approval/rejection of drafts
└── test_r6.py             # tests for all R6 modules
```

## Schema Addition (append to schema.sql)

```sql
-- R6: Draft outcome tracking for graduated autonomy
CREATE TABLE IF NOT EXISTS draft_outcomes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id TEXT,
    task_type TEXT NOT NULL,
    level TEXT NOT NULL,
    outcome TEXT NOT NULL,
    changes_made INTEGER DEFAULT 0,
    created_at REAL
);

CREATE INDEX IF NOT EXISTS idx_do_task ON draft_outcomes(task_type, level);
```

---

## 4 Levels of Output

```
Trust < 0.6   → BRIEF ONLY
                Claude nhận context, tự code từ đầu.
                Output: KiwiOutput (brief + trust_score)

Trust 0.6-0.85 → BRIEF + CODE SKELETON
                 Claude nhận brief + skeleton (structure, sections, placeholders).
                 Claude fill in logic + style.
                 Output: KiwiOutput + skeleton code

Trust 0.85-0.95 → DRAFT CODE
                  Claude nhận near-complete code. Chỉ review + adjust.
                  Output: KiwiOutput + draft file content

Trust > 0.95  → READY-TO-APPLY
                Claude chỉ approve hoặc reject.
                Output: KiwiOutput + final code + apply instruction
```

---

## Module 1: autonomy.py

```python
"""R6 — Graduated Autonomy: trust score → output level → code generation."""

from dataclasses import dataclass, field
from pathlib import Path

from .output import KiwiOutput


@dataclass
class GraduatedOutput:
    brief: KiwiOutput
    level: str  # "brief_only", "skeleton", "draft", "ready"
    code: str | None = None
    confidence: float = 0.0
    apply_instruction: str = ""
    changes_from_reference: list = field(default_factory=list)


COMPLEXITY_PENALTY = {
    'checkout_page': 0.05,
    'account_page': 0.05,
    'product_page': 0.03,
    'cart_page': 0.03,
    'order_page': 0.03,
    'fix_css': 0.0,
    'add_component': 0.0,
    'hero_component': 0.0,
    'header_component': 0.0,
    'footer_component': 0.0,
}


def determine_output_level(trust_score: float, task_type: str) -> str:
    penalty = COMPLEXITY_PENALTY.get(task_type, 0.02)
    effective_trust = trust_score - penalty

    if effective_trust >= 0.95:
        return "ready"
    elif effective_trust >= 0.85:
        return "draft"
    elif effective_trust >= 0.6:
        return "skeleton"
    return "brief_only"


def generate_graduated_output(brief: KiwiOutput, theme_path: str) -> GraduatedOutput:
    task_type = brief.content.get('target', 'generic')
    level = determine_output_level(brief.trust_score, task_type)

    # Safety: check approval history before attempting higher levels
    if level in ("draft", "ready"):
        from .approval_tracker import should_attempt_level
        if not should_attempt_level(task_type, level):
            level = "skeleton" if level == "draft" else "draft"

    output = GraduatedOutput(brief=brief, level=level)

    if level == "brief_only":
        return output

    from .code_drafter import generate_skeleton, generate_draft, generate_final

    if level == "skeleton":
        output.code = generate_skeleton(brief, theme_path)
        output.confidence = brief.trust_score * 0.7
    elif level == "draft":
        draft = generate_draft(brief, theme_path)
        output.code = draft['code']
        output.confidence = brief.trust_score * 0.9
        output.changes_from_reference = draft.get('changes', [])
    elif level == "ready":
        final = generate_final(brief, theme_path)
        output.code = final['code']
        output.confidence = brief.trust_score
        output.apply_instruction = f"Write to: {final['target_path']}"
        output.changes_from_reference = final.get('changes', [])

    # Safety guard: if code has CRITICAL violations, fallback to brief_only
    if output.code:
        from .code_drafter import _check_code_quality
        if not _check_code_quality(output.code):
            output.level = "brief_only"
            output.code = None
            output.confidence = 0.0

    return output
```

---

## Module 2: code_drafter.py

```python
"""R6 — Code Drafter: generate code at different completeness levels. 0 LLM token."""

import json
import re
from pathlib import Path

from .session_logger import _get_conn
from .output import KiwiOutput


def generate_skeleton(brief: KiwiOutput, theme_path: str) -> str:
    task_type = brief.content.get('target', 'generic')
    style = brief.content.get('style_pattern', '')

    conn = _get_conn()
    row = conn.execute(
        "SELECT structure FROM cross_theme_patterns "
        "WHERE task_type = ? ORDER BY success_count DESC LIMIT 1",
        (task_type,),
    ).fetchone()

    if not row:
        return _generic_skeleton(task_type, style)

    structure = json.loads(row[0]) if row[0] else {}
    sections = structure.get('sections', ['main'])
    layout = structure.get('layout_type', 'single-col')
    components = structure.get('components_used', [])

    skeleton = f"""<?php
/**
 * Template: {task_type}
 * Layout: {layout}
 * Generated by Kiwi R6 (skeleton)
 */

if ( ! function_exists( 'wezone_is_active' ) ) return;
?>

<section class="{style or 'py-8 md:py-12'}">
  <div class="max-w-7xl mx-auto px-4">
"""

    if layout == '2-col':
        skeleton += """    <div class="grid grid-cols-1 md:grid-cols-2 gap-6">
      <div>
        <!-- TODO: main content -->
      </div>
      <div>
        <!-- TODO: sidebar/summary -->
      </div>
    </div>
"""
    elif layout == '3-col':
        skeleton += """    <div class="grid grid-cols-1 md:grid-cols-3 gap-6">
      <!-- TODO: 3 columns -->
    </div>
"""
    else:
        for section in sections[:5]:
            skeleton += f"""    <div>
      <!-- TODO: {section} -->
    </div>

"""

    if components:
        skeleton += "\n    <!-- Components:\n"
        for comp in components:
            skeleton += f"         wz_component('{comp}', [...]);\n"
        skeleton += "    -->\n"

    skeleton += """  </div>
</section>
"""
    return skeleton


def generate_draft(brief: KiwiOutput, theme_path: str) -> dict:
    task_type = brief.content.get('target', 'generic')
    theme_name = Path(theme_path).name

    reference = _find_best_reference(task_type, theme_name, theme_path)
    if not reference:
        skeleton = generate_skeleton(brief, theme_path)
        return {'code': skeleton, 'changes': ['no_reference_found']}

    ref_path = Path(reference['file'])
    if not ref_path.exists():
        skeleton = generate_skeleton(brief, theme_path)
        return {'code': skeleton, 'changes': ['reference_file_missing']}

    ref_code = ref_path.read_text(encoding='utf-8', errors='ignore')

    target_style = _query_style_knowledge(theme_name)
    ref_style = _query_style_knowledge(reference['theme'])

    draft_code = _swap_style_tokens(ref_code, ref_style, target_style)

    changes = []
    for key in target_style:
        if key in ref_style and ref_style[key] != target_style[key]:
            changes.append(f"{key}: {ref_style[key]} -> {target_style[key]}")

    return {'code': draft_code, 'reference': str(ref_path), 'changes': changes}


def generate_final(brief: KiwiOutput, theme_path: str) -> dict:
    draft = generate_draft(brief, theme_path)
    task_type = brief.content.get('target', 'generic')
    target_path = _determine_target_path(task_type, theme_path)
    draft['target_path'] = target_path
    return draft


def _find_best_reference(task_type: str, target_theme: str, theme_path: str) -> dict | None:
    conn = _get_conn()
    row = conn.execute(
        "SELECT themes_applied, structure FROM cross_theme_patterns "
        "WHERE task_type = ? AND success_count >= 3 "
        "ORDER BY success_count DESC LIMIT 1",
        (task_type,),
    ).fetchone()

    if not row:
        return None

    themes = json.loads(row[0]) if row[0] else []
    target_style = _query_style_knowledge(target_theme)

    best_match = None
    best_score = -1.0

    for theme in themes:
        if theme == target_theme:
            continue
        theme_style = _query_style_knowledge(theme)
        score = _compute_style_similarity(target_style, theme_style)
        if score > best_score:
            best_score = score
            best_match = theme

    if not best_match:
        return None

    file_path = _find_task_file(task_type, best_match)
    if not file_path:
        return None

    return {'theme': best_match, 'file': file_path, 'similarity': best_score}


def _query_style_knowledge(theme: str) -> dict:
    conn = _get_conn()
    rows = conn.execute(
        "SELECT pattern_key, value FROM style_knowledge "
        "WHERE theme = ? AND times_seen >= 2",
        (theme,),
    ).fetchall()
    return {r[0]: r[1] for r in rows}


def _compute_style_similarity(style_a: dict, style_b: dict) -> float:
    if not style_a or not style_b:
        return 0.0
    keys = set(list(style_a.keys()) + list(style_b.keys()))
    if not keys:
        return 0.0
    matches = sum(1 for k in keys if style_a.get(k) == style_b.get(k))
    return matches / len(keys)


def _swap_style_tokens(code: str, source_style: dict, target_style: dict) -> str:
    result = code
    for key in target_style:
        if key not in source_style or source_style[key] == target_style[key]:
            continue
        old_val = source_style[key]
        new_val = target_style[key]

        if key == 'radius':
            result = result.replace(f"rounded-{old_val}", f"rounded-{new_val}")
        elif key == 'spacing_base':
            result = re.sub(rf'py-{old_val}(\s)', f'py-{new_val}\\1', result)
        elif key == 'spacing_md':
            result = re.sub(rf'md:py-{old_val}(\s|")', f'md:py-{new_val}\\1', result)
        elif key == 'container':
            result = result.replace(f"max-w-{old_val}", f"max-w-{new_val}")
        elif key == 'shadow':
            result = result.replace(f"shadow-{old_val}", f"shadow-{new_val}")
    return result


def _determine_target_path(task_type: str, theme_path: str) -> str:
    path_map = {
        'checkout_page': 'templates/checkout.php',
        'cart_page': 'templates/cart.php',
        'product_page': 'templates/single-product.php',
        'home_page': 'templates/home.php',
        'archive_page': 'templates/archive.php',
        'account_page': 'templates/account/dashboard.php',
        'login_page': 'templates/account/login.php',
        'search_page': 'templates/search.php',
        'thankyou_page': 'templates/thank-you.php',
    }
    relative = path_map.get(task_type, f'templates/{task_type}.php')
    return str(Path(theme_path) / relative)


def _find_task_file(task_type: str, theme: str) -> str | None:
    """Find the actual file for a task_type in a theme directory."""
    from .context_assembler import PROJECT_ROOT

    theme_dir = PROJECT_ROOT / "themes" / theme
    if not theme_dir.exists():
        return None

    path_map = {
        'checkout_page': 'templates/checkout.php',
        'cart_page': 'templates/cart.php',
        'product_page': 'templates/single-product.php',
        'home_page': 'templates/home.php',
        'archive_page': 'templates/archive.php',
        'account_page': 'templates/account/dashboard.php',
        'login_page': 'templates/account/login.php',
        'search_page': 'templates/search.php',
        'thankyou_page': 'templates/thank-you.php',
        'hero_component': 'template-parts/home/hero.php',
        'header_component': 'template-parts/header.php',
        'footer_component': 'template-parts/footer.php',
    }

    relative = path_map.get(task_type)
    if not relative:
        return None

    candidate = theme_dir / relative
    if candidate.exists():
        return str(candidate)
    return None


def _check_code_quality(code: str) -> bool:
    """Basic quality check on generated code. Returns False if CRITICAL issues found."""
    critical_patterns = [
        r'wc_get_product',       # WooCommerce reference
        r'WC\(\)',               # WooCommerce reference
        r'\$product->',          # Wrong accessor (should be $product['key'])
        r'__\w+--\w+',          # BEM class (forbidden)
    ]
    for pattern in critical_patterns:
        if re.search(pattern, code):
            return False

    if 'wezone_is_active' not in code and '<?php' in code:
        return False

    return True


def _generic_skeleton(task_type: str, style: str) -> str:
    return f"""<?php
/**
 * Template: {task_type}
 * Generated by Kiwi R6 (generic skeleton)
 */

if ( ! function_exists( 'wezone_is_active' ) ) return;
?>

<section class="{style or 'py-8 md:py-12'}">
  <div class="max-w-7xl mx-auto px-4">
    <!-- TODO: implement {task_type} -->
  </div>
</section>
"""
```

---

## Module 3: approval_tracker.py

```python
"""R6 — Approval Tracker: track Claude's approval/rejection of drafts."""

import time

from .session_logger import _get_conn
from .calibrator import _get_trust_baseline, _set_trust_baseline


def record_draft_outcome(session_id: str, task_type: str, level: str,
                         outcome: str, changes_made: int = 0):
    """
    Record whether Claude approved/modified/rejected the draft.
    outcome: "approved", "modified", "rejected"
    """
    conn = _get_conn()
    conn.execute(
        "INSERT INTO draft_outcomes "
        "(session_id, task_type, level, outcome, changes_made, created_at) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        (session_id, task_type, level, outcome, changes_made, time.time()),
    )
    conn.commit()

    current = _get_trust_baseline(task_type)
    if outcome == "approved":
        _set_trust_baseline(task_type, min(current + 0.08, 0.95))
    elif outcome == "rejected":
        _set_trust_baseline(task_type, max(current - 0.12, 0.4))


def get_draft_success_rate(task_type: str, level: str) -> float:
    conn = _get_conn()
    row = conn.execute(
        "SELECT "
        "  SUM(CASE WHEN outcome IN ('approved', 'modified') THEN 1 ELSE 0 END), "
        "  COUNT(*) "
        "FROM draft_outcomes WHERE task_type = ? AND level = ?",
        (task_type, level),
    ).fetchone()

    if not row or row[1] == 0:
        return 0.0
    return row[0] / row[1]


def should_attempt_level(task_type: str, level: str) -> bool:
    """Safety: don't attempt level if past drafts were mostly rejected."""
    conn = _get_conn()
    count = conn.execute(
        "SELECT COUNT(*) FROM draft_outcomes WHERE task_type = ? AND level = ?",
        (task_type, level),
    ).fetchone()[0]

    if count < 3:
        return True

    thresholds = {'skeleton': 0.3, 'draft': 0.5, 'ready': 0.7}
    threshold = thresholds.get(level, 0.5)
    return get_draft_success_rate(task_type, level) >= threshold
```

---

## Integration với __init__.py

```python
# Add to kiwi_reason() return path:
def kiwi_reason(task: str, theme_path: str, include_code: bool = False) -> KiwiOutput:
    """..."""
    # ... existing R5 code ...
    output = format_output(context, trust_score, breakdown)
    # ... existing warnings/transfer/brief_config ...

    # R6: Graduated autonomy
    if include_code and trust_score >= 0.6:
        try:
            from .autonomy import generate_graduated_output
            graduated = generate_graduated_output(output, theme_path)
            output.graduated = graduated
        except Exception:
            pass

    return output
```

---

## Integration với MCP (kiwi_reason tool)

```python
# In mcp_server.py — extend kiwi_reason response:
if hasattr(output, 'graduated') and output.graduated:
    result['autonomy_level'] = output.graduated.level
    result['code'] = output.graduated.code
    result['confidence'] = output.graduated.confidence
    result['apply_instruction'] = output.graduated.apply_instruction
```

---

## Token Savings by Level

| Level | Claude tokens | Savings vs baseline | When |
|-------|--------------|--------------------|----|
| brief_only | 5000-8000 | 50-70% | Trust < 0.6 |
| skeleton | 3000-5000 | 70-80% | Trust 0.6-0.85 |
| draft | 1500-3000 | 80-90% | Trust 0.85-0.95 |
| ready | 500-1000 | 94-97% | Trust > 0.95 |

---

## Safety Guards

1. **KHÔNG auto-apply code.** Luôn cần Claude review.
2. **Kiwi quality check** trên generated code trước khi output (xem `_check_code_quality`).
3. **Demotion on rejection:** 3 rejections liên tiếp → demote level.
4. **Approval history gate:** `should_attempt_level()` blocks levels with < threshold success rate.
5. **Trust cap:** Even "ready" level capped at 0.95 trust (never 1.0).

---

## Implementation Steps

### Step 1: Schema migration
- Append `draft_outcomes` table to `schema.sql`
- Add migration in `session_logger._migrate()`

### Step 2: Create `autonomy.py`
- `determine_output_level()` — pure function, easy to test
- `generate_graduated_output()` — orchestrator with safety guards

### Step 3: Create `code_drafter.py`
- `generate_skeleton()` — uses cross_theme_patterns structure
- `generate_draft()` — reference lookup + style swap
- `generate_final()` — draft + target path
- `_check_code_quality()` — CRITICAL pattern detection

### Step 4: Create `approval_tracker.py`
- `record_draft_outcome()` — feeds back into trust calibration
- `should_attempt_level()` — safety gate

### Step 5: Integrate into `__init__.py`
- Add `include_code` param to `kiwi_reason()`
- Add `graduated` field to `KiwiOutput`

### Step 6: Write `test_r6.py`
- Test level determination (trust thresholds + complexity penalty)
- Test skeleton generation (with/without cross-theme data)
- Test draft generation (reference found/not found)
- Test quality check (CRITICAL patterns blocked)
- Test approval tracker (demotion logic)
- Test safety guards (rejection → level demotion)

### Step 7: Integration test
- End-to-end: kiwi_reason with include_code=True
- Verify graduated output attached to KiwiOutput

---

## Verification Assertions

```python
# Level determination
assert determine_output_level(0.5, 'checkout_page') == 'brief_only'
assert determine_output_level(0.7, 'fix_css') == 'skeleton'
assert determine_output_level(0.9, 'fix_css') == 'draft'
assert determine_output_level(0.96, 'fix_css') == 'ready'

# Complex tasks need higher trust
assert determine_output_level(0.9, 'checkout_page') == 'skeleton'  # 0.9 - 0.05 = 0.85 → skeleton
assert determine_output_level(0.95, 'checkout_page') == 'draft'    # 0.95 - 0.05 = 0.90 → draft

# Quality check blocks bad code
assert _check_code_quality("<?php wc_get_product(1); ?>") == False
assert _check_code_quality("<?php if(!function_exists('wezone_is_active')) return; ?>") == True

# Skeleton always has guard
skeleton = generate_skeleton(brief, 'themes/test')
assert 'wezone_is_active' in skeleton
```
