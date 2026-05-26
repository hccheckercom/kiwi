#!/usr/bin/env python3
"""Extract template from existing theme and generate template file.

Usage:
    python extract_from_theme.py <theme_path> <section> [--page <number>]

Example:
    python extract_from_theme.py themes/funilux order-summary --page 6
"""

import argparse
import json
import re
import sys
from datetime import date
from pathlib import Path

TEMPLATES_DIR = Path(__file__).parent.parent
META_PATH = TEMPLATES_DIR / "_meta.json"
SECTIONS_DIR = TEMPLATES_DIR / "sections"
BLUEPRINT_DIR = Path(__file__).parent.parent.parent.parent / "blueprint" / "pages"


def load_meta() -> dict:
    return json.loads(META_PATH.read_text(encoding="utf-8"))


def save_meta(meta: dict):
    meta["last_updated"] = str(date.today())
    META_PATH.write_text(json.dumps(meta, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def find_php_files(theme_path: Path, section: str) -> list[Path]:
    """Find PHP files matching section name."""
    candidates = []

    # Map section names to likely file patterns
    patterns = {
        "order-summary": ["**/checkout/*summary*.php", "**/checkout/*order*.php"],
        "shipping-form": ["**/checkout/*shipping*.php"],
        "payment-methods": ["**/checkout/*payment*.php"],
        "order-tracking": ["**/account/*tracking*.php"],
        "address-form": ["**/account/*address*.php", "**/checkout/*address*.php"],
        "notification-list": ["**/account/*notification*.php"],
        "coupon-widget": ["**/checkout/*voucher*.php", "**/checkout/*coupon*.php", "**/cart/*voucher*.php"],
        "wishlist-grid": ["**/account/*wishlist*.php"],
        "compare-table": ["**/account/*compare*.php"],
        "faq-accordion": ["**/info/*faq*.php", "**/page/*faq*.php"],
        "policy-content": ["**/info/*policy*.php", "**/page/*policy*.php"],
        "contact-form": ["**/info/*contact*.php", "**/page/*contact*.php"],
        "blog-grid": ["**/blog/*archive*.php", "**/blog/*list*.php"],
        "blog-post": ["**/blog/*single*.php", "**/blog/*post*.php"],
        "brand-grid": ["**/brand/*.php"],
        "wallet-balance": ["**/account/*wallet*.php"],
        "loyalty-points": ["**/account/*loyalty*.php", "**/account/*point*.php"],
        "review-list": ["**/account/*review*.php", "**/product/*review*.php"],
        "review-form": ["**/product/*review*.php"],
        "cart-summary": ["**/cart/*summary*.php", "**/cart/*order-summary*.php"],
        "empty-state": ["**/cart/*empty*.php", "**/account/*empty*.php"],
        "error-page": ["**/404.php", "**/error*.php"],
        "maintenance-page": ["**/maintenance*.php", "**/503*.php"],
        "flash-sale-countdown": ["**/flash-sale*.php", "**/home/*flash*.php"],
        "search-results": ["**/search.php"],
        "search-filters": ["**/search*.php", "**/archive/*filter*.php"],
    }

    search_patterns = patterns.get(section, [f"**/*{section}*.php"])

    for pattern in search_patterns:
        candidates.extend(theme_path.glob(pattern))

    return candidates


def extract_css_from_php(php_content: str) -> str:
    """Extract inline CSS from PHP file."""
    css_blocks = []

    # Find <style> blocks
    style_pattern = r'<style[^>]*>(.*?)</style>'
    matches = re.findall(style_pattern, php_content, re.DOTALL)
    css_blocks.extend(matches)

    return "\n\n".join(css_blocks).strip()


def extract_js_from_php(php_content: str) -> str:
    """Extract inline JS from PHP file."""
    js_blocks = []

    # Find <script> blocks
    script_pattern = r'<script[^>]*>(.*?)</script>'
    matches = re.findall(script_pattern, php_content, re.DOTALL)
    js_blocks.extend(matches)

    return "\n\n".join(js_blocks).strip()


def infer_tags(section: str, php_content: str) -> list[str]:
    """Infer tags from section name and code content."""
    tags = [section]

    # Add tags based on code patterns
    if "wz_component(" in php_content:
        tags.append("wz-component")
    if "responsive" in php_content.lower() or "min-width" in php_content:
        tags.append("responsive")
    if "mobile" in php_content.lower():
        tags.append("mobile-first")
    if "aria-" in php_content:
        tags.append("accessible")
    if "wz_get_products" in php_content or "wz_product" in php_content:
        tags.append("wz-product")
    if "form" in section or "<form" in php_content:
        tags.append("form")
    if "grid" in section or "grid-cols" in php_content:
        tags.append("grid")

    return list(set(tags))


def infer_tokens(php_content: str) -> list[str]:
    """Infer CSS tokens used in code."""
    tokens = []

    # Find var(--token) patterns
    token_pattern = r'var\(--([^)]+)\)'
    matches = re.findall(token_pattern, php_content)
    tokens.extend(matches)

    return list(set(tokens))


def generate_template(
    section: str,
    theme_name: str,
    php_files: list[Path],
    page_number: int = None
) -> str:
    """Generate template markdown content."""
    meta = load_meta()

    if section not in meta["sections"]:
        print(f"ERROR: Unknown section '{section}'. Available: {', '.join(meta['sections'].keys())}", file=sys.stderr)
        sys.exit(1)

    tpl_id = meta["next_id"]
    tpl_name = f"TPL-{tpl_id:03d}"

    # Read PHP files
    php_code = ""
    files_table = []

    for php_file in php_files:
        content = php_file.read_text(encoding="utf-8")
        php_code += f"\n\n<!-- {php_file.name} -->\n{content}"
        files_table.append(f"| {php_file.name} | {php_file.parent.name} template |")

    # Extract CSS and JS
    css_code = extract_css_from_php(php_code)
    js_code = extract_js_from_php(php_code)

    # Infer metadata
    tags = infer_tags(section, php_code)
    tokens = infer_tokens(php_code)

    tags_yaml = "[" + ", ".join(tags) + "]"
    tokens_yaml = "[" + ", ".join(tokens[:10]) + "]" if tokens else "[]"

    features_yaml = "\n  - Extracted from working theme\n  - Mobile-first responsive\n  - Uses design tokens"

    files_table_str = "\n".join(files_table) if files_table else "| TODO | Template file |"

    page_ref = f"\n\nSee: `.claude/blueprint/pages/{page_number:02d}-*.md`" if page_number else ""

    content = f"""---
id: {tpl_name}
section: {section}
title: "{section.replace('-', ' ').title()}"
theme_source: {theme_name}
tags: {tags_yaml}
design_style: minimalist
features:{features_yaml}
responsive: [375, 768, 1024]
tokens_used: {tokens_yaml}
date: {date.today()}
---

## Preview

Extracted from `{theme_name}` theme.{page_ref}

## Files

| File | Role |
|------|------|
{files_table_str}

## Code — PHP

```php
{php_code.strip()}
```

## Code — CSS

```css
{css_code if css_code else "/* No inline CSS — uses design tokens */"}
```

## Code — JS

```js
{js_code if js_code else "// No inline JS"}
```

## Usage Notes

- **Dependencies:** Wezone Commer (`wz_*` functions)
- **Tokens:** {', '.join([f'`--{t}`' for t in tokens[:5]])} {f'+ {len(tokens)-5} more' if len(tokens) > 5 else ''}
- **Breakpoints:** Mobile-first (375px → 768px → 1024px)
- **Extracted from:** {theme_name}
"""

    # Write template file
    section_dir = SECTIONS_DIR / section
    section_dir.mkdir(parents=True, exist_ok=True)
    tpl_path = section_dir / f"{tpl_name}.md"
    tpl_path.write_text(content, encoding="utf-8")

    # Update meta
    meta["next_id"] = tpl_id + 1
    meta["sections"][section]["count"] += 1
    meta["stats"]["total"] += 1
    save_meta(meta)

    return str(tpl_path.relative_to(TEMPLATES_DIR))


def main():
    parser = argparse.ArgumentParser(description="Extract template from theme")
    parser.add_argument("theme_path", help="Path to theme (e.g., themes/funilux)")
    parser.add_argument("section", help="Section name (e.g., order-summary)")
    parser.add_argument("--page", type=int, help="Blueprint page number (optional)")

    args = parser.parse_args()

    theme_path = Path(args.theme_path)
    if not theme_path.exists():
        print(f"ERROR: Theme path not found: {theme_path}", file=sys.stderr)
        sys.exit(1)

    theme_name = theme_path.name

    # Find PHP files
    php_files = find_php_files(theme_path, args.section)

    if not php_files:
        print(f"ERROR: No PHP files found for section '{args.section}' in {theme_path}", file=sys.stderr)
        print(f"Searched patterns: {args.section}*.php", file=sys.stderr)
        sys.exit(1)

    print(f"Found {len(php_files)} file(s):", file=sys.stderr)
    for f in php_files:
        print(f"  - {f.relative_to(theme_path)}", file=sys.stderr)

    # Generate template
    tpl_path = generate_template(args.section, theme_name, php_files, args.page)

    print(f"\nCreated: {tpl_path}")

    # Auto-rebuild index
    import subprocess
    rebuild_script = Path(__file__).parent / "rebuild_index.py"
    try:
        subprocess.run([sys.executable, str(rebuild_script)], cwd=str(TEMPLATES_DIR), timeout=30, check=True)
        print("Index rebuilt.")
    except Exception as e:
        print(f"Warning: Failed to rebuild index: {e}", file=sys.stderr)


if __name__ == "__main__":
    main()