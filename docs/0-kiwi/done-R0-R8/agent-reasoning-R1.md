# Phase R1 — Context Assembly + Trust Score [1 tuần]

## Mục đích

Kiwi nhận task → output structured brief + trust score.
Claude đọc brief → quyết định trust/verify/re-research.

## Dependencies

- **Không phụ thuộc R0** — tất cả memory queries dùng fallback khi chưa có data
- Dùng existing Kiwi lessons, blueprint specs, theme files
- Project root resolved từ `_meta.json` location (không dựa vào CWD)

## Files tạo mới

```
agent/reasoning/
├── context_assembler.py   # đọc files, query lessons, detect patterns
├── trust_scorer.py        # tính trust score 5 dimensions
├── output.py              # format KiwiOutput cho Claude
└── __init__.py
```

## Context Assembler

```python
# File: agent/reasoning/context_assembler.py

from dataclasses import dataclass, field
from pathlib import Path
import json
import re

# Resolve project root from this file's location
PROJECT_ROOT = Path(__file__).resolve().parents[4]  # agent/reasoning/ → .claude/kiwi/ → .claude/ → project

@dataclass
class AssembledContext:
    task: str
    task_type: str                    # inferred: "checkout_page", "fix_css", etc.
    theme: dict                       # name, path, style_patterns
    spec: dict | None                 # blueprint spec nếu tìm được
    lessons: list[str]                # relevant Kiwi lesson IDs
    bindings: dict                    # data bindings cho task type
    files_needed: list[str]           # files Claude nên đọc
    reference_pages: list[str]        # existing pages cùng theme để reference
    
def assemble_context(task: str, theme_path: str) -> AssembledContext:
    """
    Main entry point. Nhận task description + theme path.
    Output: structured context cho brief generation.
    """
    
    # 1. Infer task type
    task_type = infer_task_type_from_description(task)
    
    # 2. Load theme info
    theme = load_theme_info(theme_path)
    
    # 3. Find relevant spec
    spec = find_spec_for_task(task_type)
    
    # 4. Query Kiwi lessons
    lessons = query_relevant_lessons(task_type, theme.get('platform', 'wp'))
    
    # 5. Load data bindings
    bindings = load_bindings_for_task(task_type)
    
    # 6. Determine files needed
    files_needed = determine_files_needed(task_type, theme_path, spec)
    
    # 7. Find reference pages (existing pages cùng theme)
    reference_pages = find_reference_pages(theme_path, task_type)
    
    return AssembledContext(
        task=task,
        task_type=task_type,
        theme=theme,
        spec=spec,
        lessons=lessons,
        bindings=bindings,
        files_needed=files_needed,
        reference_pages=reference_pages,
    )


def infer_task_type_from_description(task: str) -> str:
    """Rule-based task type inference. Không cần LLM."""
    task_lower = task.lower()
    
    page_keywords = {
        'checkout': 'checkout_page',
        'cart': 'cart_page',
        'product': 'product_page',
        'home': 'home_page',
        'archive': 'archive_page',
        'account': 'account_page',
        'login': 'login_page',
        'search': 'search_page',
        'thank': 'thankyou_page',
        'order': 'order_page',
        'wishlist': 'wishlist_page',
        'dashboard': 'dashboard_page',
    }
    
    for keyword, task_type in page_keywords.items():
        if keyword in task_lower:
            return task_type
    
    if any(w in task_lower for w in ['fix css', 'sửa css', 'responsive', 'mobile']):
        return 'fix_css'
    if any(w in task_lower for w in ['fix bug', 'sửa bug', 'fix lỗi']):
        return 'fix_bug'
    if any(w in task_lower for w in ['thêm component', 'add component', 'tạo component']):
        return 'add_component'
    if any(w in task_lower for w in ['header', 'footer', 'sidebar', 'nav']):
        return 'layout_component'
    
    return 'generic'


def load_theme_info(theme_path: str) -> dict:
    """Load theme metadata: name, style patterns, config."""
    path = Path(theme_path)
    if not path.is_absolute():
        path = PROJECT_ROOT / path
    
    info = {'name': path.name, 'path': str(path), 'platform': 'wp'}
    
    config_file = path / 'inc' / 'store-config.php'
    if config_file.exists():
        info['has_config'] = True
    
    info['style_patterns'] = detect_style_patterns(str(path))
    return info


def detect_style_patterns(theme_path: str) -> dict:
    """Extract Tailwind patterns từ existing theme files."""
    patterns = {'spacing': [], 'radius': [], 'container': [], 'colors': []}
    
    path = Path(theme_path)
    if not path.exists():
        return patterns
    
    for php_file in list(path.rglob('*.php'))[:50]:  # cap để tránh scan quá lâu
        try:
            content = php_file.read_text(encoding='utf-8', errors='ignore')
            
            for match in re.findall(r'py-(\d+)\s+md:py-(\d+)', content):
                pat = f"py-{match[0]} md:py-{match[1]}"
                if pat not in patterns['spacing']:
                    patterns['spacing'].append(pat)
            
            for match in re.findall(r'rounded-(\w+)', content):
                val = f"rounded-{match}"
                if val not in patterns['radius']:
                    patterns['radius'].append(val)
            
            for match in re.findall(r'max-w-(\w+)', content):
                val = f"max-w-{match}"
                if val not in patterns['container']:
                    patterns['container'].append(val)
        except:
            continue
    
    return patterns


# --- SPEC MAPPING (complete) ---

SPEC_MAP = {
    'checkout_page': '.claude/blueprint/pages/02-cap1-shop/08-checkout.md',
    'cart_page': '.claude/blueprint/pages/02-cap1-shop/07-cart.md',
    'product_page': '.claude/blueprint/pages/02-cap1-shop/03-single-product.md',
    'home_page': '.claude/blueprint/pages/02-cap1-shop/01-home.md',
    'archive_page': '.claude/blueprint/pages/02-cap1-shop/02-archive.md',
    'account_page': '.claude/blueprint/pages/03-cap1-account/09-dashboard.md',
    'login_page': '.claude/blueprint/pages/03-cap1-account/10-login.md',
    'search_page': '.claude/blueprint/pages/02-cap1-shop/06-search.md',
    'thankyou_page': '.claude/blueprint/pages/02-cap1-shop/08-checkout.md',  # same spec
    'order_page': '.claude/blueprint/pages/03-cap1-account/12-order-detail.md',
    'wishlist_page': '.claude/blueprint/pages/03-cap1-account/14-wishlist.md',
    'dashboard_page': '.claude/blueprint/pages/03-cap1-account/09-dashboard.md',
}

def find_spec_for_task(task_type: str) -> dict | None:
    """Find blueprint spec for task type. Resolves relative to PROJECT_ROOT."""
    spec_rel = SPEC_MAP.get(task_type)
    if not spec_rel:
        return None
    
    spec_path = PROJECT_ROOT / spec_rel
    if spec_path.exists():
        return {'path': str(spec_path), 'rel_path': spec_rel, 'found': True}
    
    return {'path': str(spec_path), 'rel_path': spec_rel, 'found': False}


# --- BINDINGS (v1: static map per task type) ---

BINDINGS_MAP = {
    'checkout_page': {
        'data_source': 'wz_cart()',
        'key_functions': ['wz_get_shipping_methods()', 'wz_get_payment_gateways()'],
        'template_vars': ['$cart_items', '$totals', '$shipping', '$payment'],
    },
    'cart_page': {
        'data_source': 'wz_cart()',
        'key_functions': ['wz_cart_item_count()', 'wz_format_price()'],
        'template_vars': ['$cart_items', '$totals', '$coupon'],
    },
    'product_page': {
        'data_source': 'wz_get_product($id)',
        'key_functions': ['wz_get_related_products()', 'wz_product_gallery()'],
        'template_vars': ['$product', '$gallery', '$related', '$reviews'],
    },
    'home_page': {
        'data_source': 'wz_get_featured_products()',
        'key_functions': ['wz_get_categories()', 'wz_get_flash_sales()'],
        'template_vars': ['$featured', '$categories', '$flash_sale', '$banners'],
    },
    'archive_page': {
        'data_source': 'wz_get_products($args)',
        'key_functions': ['wz_get_filters()', 'wz_pagination()'],
        'template_vars': ['$products', '$filters', '$pagination', '$current_cat'],
    },
    'account_page': {
        'data_source': 'wz_get_current_user()',
        'key_functions': ['wz_get_orders()', 'wz_get_addresses()'],
        'template_vars': ['$user', '$orders', '$addresses'],
    },
}

def load_bindings_for_task(task_type: str) -> dict:
    """Return data bindings cho task type. Static map v1."""
    return BINDINGS_MAP.get(task_type, {})


# --- FILES NEEDED (v1: infer from task type + theme structure) ---

def determine_files_needed(task_type: str, theme_path: str, spec: dict | None) -> list[str]:
    """Determine which files Claude should read before coding."""
    files = []
    path = Path(theme_path)
    if not path.is_absolute():
        path = PROJECT_ROOT / path
    
    # Always need store-config
    config = path / 'inc' / 'store-config.php'
    if config.exists():
        files.append(str(config))
    
    # Spec file
    if spec and spec.get('found'):
        files.append(spec['path'])
    
    # Shared components spec
    shared_spec = PROJECT_ROOT / '.claude/blueprint/pages/01-shared-components.md'
    if shared_spec.exists():
        files.append(str(shared_spec))
    
    # Task-specific files
    page_template_map = {
        'checkout_page': 'wezone-templates/checkout',
        'cart_page': 'wezone-templates/cart',
        'product_page': 'wezone-templates/product',
        'home_page': 'templates/home',
        'archive_page': 'wezone-templates/archive',
        'account_page': 'wezone-templates/account',
        'login_page': 'wezone-templates/account',
        'search_page': 'wezone-templates/search',
    }
    
    template_dir = page_template_map.get(task_type)
    if template_dir:
        tpl_path = path / template_dir
        if tpl_path.exists():
            for f in tpl_path.iterdir():
                if f.suffix == '.php':
                    files.append(str(f))
    
    return files[:15]  # cap to avoid overwhelming


# --- REFERENCE PAGES (v1: find existing pages in same theme) ---

def find_reference_pages(theme_path: str, task_type: str) -> list[str]:
    """Find existing pages in theme that Claude can reference for style consistency."""
    path = Path(theme_path)
    if not path.is_absolute():
        path = PROJECT_ROOT / path
    
    references = []
    
    # Look in wezone-templates/ and templates/ for existing pages
    for tpl_dir in [path / 'wezone-templates', path / 'templates']:
        if not tpl_dir.exists():
            continue
        for php_file in tpl_dir.rglob('*.php'):
            # Skip the target page itself
            if task_type.replace('_page', '') in php_file.stem:
                continue
            references.append(str(php_file))
    
    return references[:5]  # top 5 most relevant


def query_relevant_lessons(task_type: str, platform: str) -> list[str]:
    """Query Kiwi lessons relevant to task type."""
    # Map task types to lesson search keywords
    keyword_map = {
        'checkout_page': ['checkout', 'form', 'payment', 'validation'],
        'cart_page': ['cart', 'quantity', 'price'],
        'product_page': ['product', 'gallery', 'schema', 'seo'],
        'home_page': ['home', 'hero', 'slider', 'featured'],
        'archive_page': ['archive', 'filter', 'pagination', 'grid'],
        'account_page': ['account', 'dashboard', 'auth'],
        'fix_css': ['responsive', 'mobile-first', 'overflow', 'breakpoint'],
        'fix_bug': ['guard', 'null-check', 'fatal'],
        'layout_component': ['header', 'footer', 'nav', 'sidebar'],
    }
    
    keywords = keyword_map.get(task_type, [task_type])
    
    # Search lessons by scanning _meta.json
    try:
        meta_path = PROJECT_ROOT / '.claude' / 'kiwi' / '_meta.json'
        if meta_path.exists():
            meta = json.loads(meta_path.read_text(encoding='utf-8'))
            lessons = []
            for cat, cat_data in meta.get('categories', {}).items():
                for lesson_id in cat_data.get('lessons', []):
                    # Simple keyword match on category name
                    if any(kw in cat.lower() for kw in keywords):
                        lessons.append(lesson_id)
            return lessons[:10]
    except:
        pass
    
    return []
```

## Trust Scorer

```python
# File: agent/reasoning/trust_scorer.py

import time
from pathlib import Path

def compute_trust_score(context, theme_path: str) -> tuple[float, dict]:
    """
    Tính trust score 5 dimensions. Pure Python, 0 LLM token.
    Returns: (score, breakdown)
    
    NOTE: Không import từ R0. Khi R0 data available → upgrade functions.
    """
    scores = {}
    
    # 1. Spec coverage (most impactful — có spec = biết chính xác cần gì)
    scores['spec_found'] = 1.0 if (context.spec and context.spec.get('found')) else 0.3
    
    # 2. Theme maturity (theme có nhiều files = đã code nhiều = style rõ ràng)
    scores['theme_maturity'] = _check_theme_maturity(theme_path)
    
    # 3. Bindings available (có data bindings = biết dùng function nào)
    scores['bindings'] = 1.0 if context.bindings else 0.4
    
    # 4. Reference pages available (có pages khác để tham khảo style)
    scores['references'] = min(len(context.reference_pages) / 3, 1.0)
    
    # 5. Lesson coverage (có lessons liên quan = biết anti-patterns)
    scores['lessons'] = min(len(context.lessons) / 5, 1.0)
    
    # Weighted average
    weights = {
        'spec_found': 0.30,
        'theme_maturity': 0.20,
        'bindings': 0.20,
        'references': 0.15,
        'lessons': 0.15,
    }
    trust = sum(scores[k] * weights[k] for k in scores)
    
    return trust, scores


def _check_theme_maturity(theme_path: str) -> float:
    """Theme có bao nhiêu PHP files? Nhiều = mature = style rõ."""
    from .context_assembler import PROJECT_ROOT
    
    path = Path(theme_path)
    if not path.is_absolute():
        path = PROJECT_ROOT / path
    
    if not path.exists():
        return 0.0
    
    php_count = len(list(path.rglob('*.php')))
    
    if php_count >= 30:
        return 1.0
    elif php_count >= 15:
        return 0.8
    elif php_count >= 5:
        return 0.5
    else:
        return 0.2
```

## Output Formatter

```python
# File: agent/reasoning/output.py

from dataclasses import dataclass, field

@dataclass
class KiwiOutput:
    content: dict
    trust_score: float
    trust_breakdown: dict
    recommendation: str = "re_research"
    verify_hint: str = ""

def format_output(context, trust_score: float, trust_breakdown: dict) -> KiwiOutput:
    """Format assembled context into KiwiOutput for Claude."""
    
    if trust_score >= 0.85:
        recommendation = "trust"
    elif trust_score >= 0.6:
        recommendation = "verify_partial"
    else:
        recommendation = "re_research"
    
    content = {
        'target': context.task_type,
        'files_needed': context.files_needed,
        'spec': context.spec,
        'lessons': context.lessons[:5],
        'data_bindings': context.bindings,
        'style_pattern': _summarize_style(context.theme.get('style_patterns', {})),
        'reference_pages': context.reference_pages[:3],
    }
    
    verify_hint = _generate_verify_hint(trust_breakdown)
    
    return KiwiOutput(
        content=content,
        trust_score=trust_score,
        trust_breakdown=trust_breakdown,
        recommendation=recommendation,
        verify_hint=verify_hint,
    )

def _summarize_style(patterns: dict) -> str:
    parts = []
    if patterns.get('spacing'):
        parts.append(patterns['spacing'][0])
    if patterns.get('radius'):
        parts.append(patterns['radius'][0])
    if patterns.get('container'):
        parts.append(patterns['container'][0])
    return ', '.join(parts) if parts else 'unknown'

def _generate_verify_hint(breakdown: dict) -> str:
    lowest = min(breakdown, key=breakdown.get)
    hints = {
        'spec_found': 'No spec found — verify requirements with user',
        'theme_maturity': 'Theme is new — no existing style to reference, verify design choices',
        'bindings': 'No data bindings known — verify which wz_* functions to use',
        'references': 'No reference pages in theme — verify layout/spacing consistency',
        'lessons': 'Few relevant lessons — verify anti-patterns manually',
    }
    return hints.get(lowest, '')
```

## Public API

```python
# File: agent/reasoning/__init__.py

from .context_assembler import assemble_context
from .trust_scorer import compute_trust_score
from .output import format_output, KiwiOutput

def kiwi_reason(task: str, theme_path: str) -> KiwiOutput:
    """
    Main entry point. Task → Brief + Trust Score.
    0 LLM token. ~50ms execution.
    """
    context = assemble_context(task, theme_path)
    trust_score, breakdown = compute_trust_score(context, theme_path)
    output = format_output(context, trust_score, breakdown)
    return output
```

## Verification

```python
output = kiwi_reason("Tạo trang checkout", "themes/sfvn")
assert output.trust_score >= 0
assert output.trust_score <= 1.0
assert output.recommendation in ("trust", "verify_partial", "re_research")
assert 'files_needed' in output.content
assert 'lessons' in output.content

# Nếu không có spec → trust thấp hơn
output_no_spec = kiwi_reason("Tạo trang xyz-unknown", "themes/sfvn")
assert output_no_spec.trust_score < output.trust_score
```

## Integration với MCP

Sau khi R1 hoàn thành → expose qua MCP tool mới:

```python
# Trong mcp_server.py — thêm tool
@tool("kiwi_reason")
def handle_kiwi_reason(task: str, theme_path: str) -> dict:
    output = kiwi_reason(task, theme_path)
    return asdict(output)
```

## Quan hệ với kiwi_context

- `kiwi_context` (hiện tại): trả text-based rules + snippets cho Claude đọc trực tiếp
- `kiwi_reason` (mới): trả structured data + trust score → Claude tự quyết trust/verify
- **Không replace** — `kiwi_reason` augment `kiwi_context`:
  1. Claude gọi `kiwi_reason` → nhận brief + trust score
  2. Nếu trust < 0.6 → Claude gọi thêm `kiwi_context` để lấy full rules
  3. Nếu trust >= 0.85 → Claude dùng brief trực tiếp, skip `kiwi_context`
  4. Nếu 0.6-0.85 → Claude dùng brief + verify specific dimensions

## Changes từ v0 plan

| Issue | v0 | v1 (fixed) |
|-------|-----|------------|
| Missing functions | Undefined stubs | Full implementations with static maps |
| R0 dependency | Import from session_query, memory | Removed — fallback values, no imports |
| Path resolution | Relative to CWD | Relative to PROJECT_ROOT (from __file__) |
| Freshness logic | Penalize recently-modified files | Removed — assembler reads live, no cache to go stale |
| Incomplete spec map | 7 entries | 12 entries (all task types covered) |
| Trust dimensions | freshness, experience, accuracy, spec, consistency | spec, maturity, bindings, references, lessons |
| kiwi_context relation | Unclear | Explicit: augment, not replace |
