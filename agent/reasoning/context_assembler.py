"""R1 — Context Assembler: task → structured brief for Claude."""

from dataclasses import dataclass, field
from pathlib import Path
import json
import re
import sqlite3


def _resolve_project_root() -> Path:
    candidate = Path(__file__).resolve().parents[4]
    meta = candidate / '.claude' / 'kiwi' / '_meta.json'
    if meta.exists():
        return candidate
    for i in range(3, 6):
        candidate = Path(__file__).resolve().parents[i]
        meta = candidate / '.claude' / 'kiwi' / '_meta.json'
        if meta.exists():
            return candidate
    return Path(__file__).resolve().parents[4]


PROJECT_ROOT = _resolve_project_root()


@dataclass
class AssembledContext:
    task: str
    task_type: str
    theme: dict
    spec: dict | None
    lessons: list[str]
    bindings: dict
    files_needed: list[str]
    reference_pages: list[str]


PAGE_KEYWORDS = {
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

SPEC_MAP = {
    'checkout_page': '.claude/blueprint/pages/02-cap1-shop/08-checkout.md',
    'cart_page': '.claude/blueprint/pages/02-cap1-shop/07-cart.md',
    'product_page': '.claude/blueprint/pages/02-cap1-shop/03-single-product.md',
    'home_page': '.claude/blueprint/pages/02-cap1-shop/01-home.md',
    'archive_page': '.claude/blueprint/pages/02-cap1-shop/02-archive.md',
    'account_page': '.claude/blueprint/pages/03-cap1-account/09-dashboard.md',
    'login_page': '.claude/blueprint/pages/03-cap1-account/10-login.md',
    'search_page': '.claude/blueprint/pages/02-cap1-shop/06-search.md',
    'thankyou_page': '.claude/blueprint/pages/02-cap1-shop/08-checkout.md',
    'order_page': '.claude/blueprint/pages/03-cap1-account/12-order-detail.md',
    'wishlist_page': '.claude/blueprint/pages/03-cap1-account/14-wishlist.md',
    'dashboard_page': '.claude/blueprint/pages/03-cap1-account/09-dashboard.md',
}

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
    'dashboard_page': {
        'data_source': 'wz_get_current_user()',
        'key_functions': ['wz_get_orders()', 'wz_get_addresses()'],
        'template_vars': ['$user', '$orders', '$addresses'],
    },
    'login_page': {
        'data_source': 'none',
        'key_functions': ['wz_login_url()', 'wz_register_url()'],
        'template_vars': ['$redirect_to', '$errors'],
    },
    'search_page': {
        'data_source': 'wz_search($query)',
        'key_functions': ['wz_get_filters()', 'wz_pagination()'],
        'template_vars': ['$results', '$query', '$filters', '$pagination'],
    },
    'order_page': {
        'data_source': 'wz_get_order($id)',
        'key_functions': ['wz_order_status_label()', 'wz_format_price()'],
        'template_vars': ['$order', '$items', '$status', '$tracking'],
    },
    'wishlist_page': {
        'data_source': 'wz_get_wishlist()',
        'key_functions': ['wz_wishlist_count()', 'wz_add_to_cart_url()'],
        'template_vars': ['$items', '$count'],
    },
    'thankyou_page': {
        'data_source': 'wz_get_order($id)',
        'key_functions': ['wz_order_status_label()'],
        'template_vars': ['$order', '$items'],
    },
}

LESSON_KEYWORDS = {
    'checkout_page': ['checkout', 'form', 'payment', 'validation'],
    'cart_page': ['cart', 'quantity', 'price'],
    'product_page': ['product', 'gallery', 'schema', 'seo'],
    'home_page': ['home', 'hero', 'slider', 'featured'],
    'archive_page': ['archive', 'filter', 'pagination', 'grid'],
    'account_page': ['account', 'dashboard', 'auth'],
    'login_page': ['login', 'auth', 'form', 'validation'],
    'search_page': ['search', 'filter', 'pagination'],
    'fix_css': ['responsive', 'mobile-first', 'overflow', 'breakpoint'],
    'fix_bug': ['guard', 'null-check', 'fatal'],
    'layout_component': ['header', 'footer', 'nav', 'sidebar'],
}

PAGE_TEMPLATE_MAP = {
    'checkout_page': 'wezone-templates/checkout',
    'cart_page': 'wezone-templates/cart',
    'product_page': 'wezone-templates/product',
    'home_page': 'templates/home',
    'archive_page': 'wezone-templates/archive',
    'account_page': 'wezone-templates/account',
    'login_page': 'wezone-templates/account',
    'search_page': 'wezone-templates/search',
    'order_page': 'wezone-templates/account',
    'wishlist_page': 'wezone-templates/account',
    'dashboard_page': 'wezone-templates/account',
    'thankyou_page': 'wezone-templates/checkout',
}


def assemble_context(task: str, theme_path: str) -> AssembledContext:
    try:
        task_type = infer_task_type(task)
        theme = load_theme_info(theme_path)
        spec = find_spec(task_type)
        lessons = query_lessons(task_type, theme.get('platform', 'wp'))
        bindings = _merge_bindings(task_type, theme.get('name', 'unknown'))
        files_needed = determine_files_needed(task_type, theme_path, spec)
        files_needed = _enrich_files_from_patterns(task_type, theme.get('name', 'unknown'), files_needed)
        reference_pages = find_reference_pages(theme_path, task_type)
        theme['style_patterns'] = _enrich_styles_from_db(theme.get('name', 'unknown'), theme.get('style_patterns', {}))
    except Exception:
        task_type = infer_task_type(task)
        return AssembledContext(
            task=task, task_type=task_type,
            theme={'name': Path(theme_path).name, 'path': theme_path, 'platform': 'wp'},
            spec=None, lessons=[], bindings={},
            files_needed=[], reference_pages=[],
        )

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


def infer_task_type(task: str) -> str:
    task_lower = task.lower()

    for keyword, task_type in PAGE_KEYWORDS.items():
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
    path = Path(theme_path)
    if not path.is_absolute():
        path = PROJECT_ROOT / path

    info = {'name': path.name, 'path': str(path), 'platform': 'wp'}

    if (path / 'inc' / 'store-config.php').exists():
        info['has_config'] = True

    info['style_patterns'] = detect_style_patterns(path)
    return info


def detect_style_patterns(path: Path) -> dict:
    patterns = {'spacing': [], 'radius': [], 'container': []}

    if not path.exists():
        return patterns

    for php_file in list(path.rglob('*.php'))[:50]:
        try:
            content = php_file.read_text(encoding='utf-8', errors='ignore')

            for m in re.findall(r'py-(\d+)\s+md:py-(\d+)', content):
                val = f"py-{m[0]} md:py-{m[1]}"
                if val not in patterns['spacing']:
                    patterns['spacing'].append(val)

            for m in re.findall(r'rounded-(\w+)', content):
                val = f"rounded-{m}"
                if val not in patterns['radius']:
                    patterns['radius'].append(val)

            for m in re.findall(r'max-w-(\w+)', content):
                val = f"max-w-{m}"
                if val not in patterns['container']:
                    patterns['container'].append(val)
        except Exception:
            continue

    return patterns


def find_spec(task_type: str) -> dict | None:
    spec_rel = SPEC_MAP.get(task_type)
    if not spec_rel:
        return None

    spec_path = PROJECT_ROOT / spec_rel
    return {
        'path': str(spec_path),
        'rel_path': spec_rel,
        'found': spec_path.exists(),
    }


def determine_files_needed(task_type: str, theme_path: str, spec: dict | None) -> list[str]:
    files = []
    path = Path(theme_path)
    if not path.is_absolute():
        path = PROJECT_ROOT / path

    config = path / 'inc' / 'store-config.php'
    if config.exists():
        files.append(str(config))

    if spec and spec.get('found'):
        files.append(spec['path'])

    shared_spec = PROJECT_ROOT / '.claude/blueprint/pages/01-shared-components.md'
    if shared_spec.exists():
        files.append(str(shared_spec))

    template_dir = PAGE_TEMPLATE_MAP.get(task_type)
    if template_dir:
        tpl_path = path / template_dir
        if tpl_path.exists():
            for f in sorted(tpl_path.iterdir())[:10]:
                if f.suffix == '.php':
                    files.append(str(f))

    return files[:15]


def find_reference_pages(theme_path: str, task_type: str) -> list[str]:
    path = Path(theme_path)
    if not path.is_absolute():
        path = PROJECT_ROOT / path

    references = []
    target_stem = task_type.replace('_page', '')

    for tpl_dir in [path / 'wezone-templates', path / 'templates']:
        if not tpl_dir.exists():
            continue
        for php_file in sorted(tpl_dir.rglob('*.php'))[:20]:
            if target_stem in php_file.stem:
                continue
            references.append(str(php_file))

    return references[:5]


def query_lessons(task_type: str, platform: str) -> list[str]:
    keywords = LESSON_KEYWORDS.get(task_type, [task_type])

    try:
        meta_path = PROJECT_ROOT / '.claude' / 'kiwi' / '_meta.json'
        if not meta_path.exists():
            return []

        meta = json.loads(meta_path.read_text(encoding='utf-8'))
        matched_cats = []

        for cat, cat_data in meta.get('categories', {}).items():
            desc = cat_data.get('desc', '').lower()
            cat_lower = cat.lower()
            score = 0
            for kw in keywords:
                if kw in cat_lower:
                    score += 3
                if kw in desc:
                    score += 1
            if score > 0:
                matched_cats.append((score, cat, cat_data.get('count', 0)))

        matched_cats.sort(key=lambda x: -x[0])
        return [cat for _, cat, _ in matched_cats[:10]]
    except Exception:
        return []


# --- Learned data from DB (R2 closed loop) ---

_DB_PATH = PROJECT_ROOT / '.claude' / 'kiwi' / 'memory' / 'reasoning.db'


def _get_reasoning_conn() -> sqlite3.Connection | None:
    if not _DB_PATH.exists():
        return None
    try:
        conn = sqlite3.connect(str(_DB_PATH), timeout=3)
        conn.execute("PRAGMA journal_mode=WAL")
        return conn
    except sqlite3.Error:
        return None


def _query_learned_styles(theme: str) -> dict:
    """Query style_knowledge for patterns seen >= 3 times."""
    conn = _get_reasoning_conn()
    if not conn:
        return {}
    try:
        rows = conn.execute(
            "SELECT pattern_key, value FROM style_knowledge "
            "WHERE theme = ? AND times_seen >= 3 ORDER BY times_seen DESC",
            (theme,),
        ).fetchall()
        return {r[0]: r[1] for r in rows}
    except sqlite3.Error:
        return {}
    finally:
        conn.close()


def _query_learned_bindings(task_type: str, theme: str) -> list:
    """Query binding_knowledge for bindings seen >= 2 times.

    Filters by THEME only — not task_type. The stored task_type vocabulary
    (e.g. 'header_component', 'dashboard_page') does not match what
    infer_task_type() emits (e.g. 'layout_component'), so a task_type filter
    made this query return [] for almost every real task, leaving
    kiwi_reason's data_bindings permanently empty while kiwi_context (which
    filters by theme only) worked. Blessed conventions sort first.
    """
    conn = _get_reasoning_conn()
    if not conn:
        return []
    try:
        rows = conn.execute(
            "SELECT binding FROM binding_knowledge "
            "WHERE theme = ? AND times_seen >= 2 "
            "ORDER BY blessed DESC, times_seen DESC LIMIT 30",
            (theme,),
        ).fetchall()
        return [r[0] for r in rows]
    except sqlite3.Error:
        return []
    finally:
        conn.close()


def _query_context_patterns(task_type: str, theme: str) -> list:
    """Query files commonly read before writing for this task_type+theme."""
    conn = _get_reasoning_conn()
    if not conn:
        return []
    try:
        rows = conn.execute(
            "SELECT files_read FROM context_patterns "
            "WHERE task_type = ? AND theme = ? ORDER BY created_at DESC LIMIT 5",
            (task_type, theme),
        ).fetchall()
        if not rows:
            return []

        from collections import Counter
        file_counts = Counter()
        for row in rows:
            try:
                files = json.loads(row[0])
                file_counts.update(files)
            except (json.JSONDecodeError, TypeError):
                continue

        # Files that appear in >= 2 of the last 5 sessions (or 60% if more data)
        threshold = max(2, int(len(rows) * 0.6))
        return [f for f, count in file_counts.most_common(10) if count >= threshold]
    except sqlite3.Error:
        return []
    finally:
        conn.close()


def _merge_bindings(task_type: str, theme: str) -> dict:
    """Merge hardcoded BINDINGS_MAP with learned bindings from DB."""
    base = dict(BINDINGS_MAP.get(task_type, {}))
    learned = _query_learned_bindings(task_type, theme)
    if learned:
        existing_funcs = base.get('key_functions', [])
        new_funcs = [b for b in learned if b not in existing_funcs and '(' in b]
        if new_funcs:
            base['key_functions'] = existing_funcs + new_funcs[:5]
        base['_learned_bindings'] = learned
    return base


def _enrich_styles_from_db(theme: str, static_patterns: dict) -> dict:
    """Merge static file-scan patterns with DB learned patterns."""
    learned = _query_learned_styles(theme)
    if not learned:
        return static_patterns

    enriched = dict(static_patterns)
    style_to_pattern_key = {
        'spacing_base': 'spacing',
        'spacing_md': 'spacing',
        'radius': 'radius',
        'container': 'container',
        'shadow': 'shadow',
        'grid_cols': 'grid',
    }

    for db_key, value in learned.items():
        pattern_key = style_to_pattern_key.get(db_key, db_key)
        if pattern_key not in enriched:
            enriched[pattern_key] = []
        learned_val = f"{db_key}:{value}"
        if learned_val not in enriched[pattern_key]:
            enriched[pattern_key].insert(0, learned_val)

    return enriched


def _enrich_files_from_patterns(task_type: str, theme: str, files_needed: list) -> list:
    """Add commonly-read files from past sessions + mined patterns."""
    # Source 1: context_patterns table (R2)
    pattern_files = _query_context_patterns(task_type, theme)

    # Source 2: mined suggestions (R3)
    mined_files = _query_mined_suggestions(task_type)

    existing = set(files_needed)
    for f in pattern_files + mined_files:
        if f not in existing and Path(f).exists():
            files_needed.append(f)
            if len(files_needed) >= 20:
                break
    return files_needed


def _query_mined_suggestions(task_type: str) -> list:
    """Query pre-mined file suggestions from calibrator."""
    conn = _get_reasoning_conn()
    if not conn:
        return []
    try:
        # Check if context_patterns has enough data for this task_type
        count = conn.execute(
            "SELECT COUNT(*) FROM context_patterns WHERE task_type = ?",
            (task_type,),
        ).fetchone()[0]
        if count < 5:
            return []

        rows = conn.execute(
            "SELECT files_read FROM context_patterns "
            "WHERE task_type = ? ORDER BY created_at DESC LIMIT 20",
            (task_type,),
        ).fetchall()
        if not rows:
            return []

        from collections import Counter
        file_counts = Counter()
        for row in rows:
            try:
                files = json.loads(row[0])
                file_counts.update(files)
            except (json.JSONDecodeError, TypeError):
                continue

        threshold = max(3, int(len(rows) * 0.6))
        return [f for f, c in file_counts.most_common(10) if c >= threshold]
    except sqlite3.Error:
        return []
    finally:
        conn.close()