#!/usr/bin/env python3
"""Kiwi Templates — Add new template."""

import argparse
import json
import sys
from datetime import date
from pathlib import Path

TEMPLATES_DIR = Path(__file__).parent.parent
META_PATH = TEMPLATES_DIR / "_meta.json"
SECTIONS_DIR = TEMPLATES_DIR / "sections"


def load_meta() -> dict:
    return json.loads(META_PATH.read_text(encoding="utf-8"))


def save_meta(meta: dict):
    meta["last_updated"] = str(date.today())
    META_PATH.write_text(json.dumps(meta, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def main():
    parser = argparse.ArgumentParser(description="Add a new Kiwi Template")
    parser.add_argument("--section", required=True, help="Section type (header, hero, categories, etc.)")
    parser.add_argument("--title", required=True, help="Template title")
    parser.add_argument("--theme", required=True, help="Source theme name")
    parser.add_argument("--tags", default="", help="Comma-separated tags")
    parser.add_argument("--style", default="minimalist", help="Design style (minimalist|bold|classic|modern)")
    parser.add_argument("--features", default="", help="Comma-separated features list")
    parser.add_argument("--tokens", default="", help="Comma-separated CSS tokens used")

    args = parser.parse_args()

    meta = load_meta()

    if args.section not in meta["sections"]:
        print(f"ERROR: Unknown section '{args.section}'. Available: {', '.join(meta['sections'].keys())}", file=sys.stderr)
        sys.exit(1)

    tpl_id = meta["next_id"]
    tpl_name = f"TPL-{tpl_id:03d}"

    section_dir = SECTIONS_DIR / args.section
    section_dir.mkdir(parents=True, exist_ok=True)
    tpl_path = section_dir / f"{tpl_name}.md"

    tags_list = [t.strip() for t in args.tags.split(",") if t.strip()]
    features_list = [f.strip() for f in args.features.split(",") if f.strip()]
    tokens_list = [t.strip() for t in args.tokens.split(",") if t.strip()]

    tags_yaml = "[" + ", ".join(tags_list) + "]" if tags_list else "[]"
    tokens_yaml = "[" + ", ".join(tokens_list) + "]" if tokens_list else "[]"
    features_yaml = ""
    for f in features_list:
        features_yaml += f"\n  - {f}"
    if not features_yaml:
        features_yaml = "\n  - TODO"

    content = f"""---
id: {tpl_name}
section: {args.section}
title: "{args.title}"
theme_source: {args.theme}
tags: {tags_yaml}
design_style: {args.style}
features:{features_yaml}
responsive: [375, 768, 1024]
tokens_used: {tokens_yaml}
date: {date.today()}
---

## Preview

TODO: Mô tả ngắn về visual appearance và behavior.

## Files

| File | Role |
|------|------|
| TODO | Template chính |

## Code — PHP

```php
<!-- TODO: Full PHP code -->
```

## Code — CSS

```css
/* TODO: Full CSS */
```

## Code — JS (optional)

```js
// TODO: JS if needed (remove section if not)
```

## Usage Notes

- TODO: Dependencies, tokens, breakpoints
"""

    tpl_path.write_text(content, encoding="utf-8")

    meta["next_id"] = tpl_id + 1
    meta["sections"][args.section]["count"] += 1
    meta["stats"]["total"] += 1
    save_meta(meta)

    print(f"Created: {tpl_path.relative_to(TEMPLATES_DIR)}")
    print(f"ID: {tpl_name}")

    # Auto-rebuild index
    import subprocess
    rebuild_script = Path(__file__).parent / "rebuild_index.py"
    subprocess.run([sys.executable, str(rebuild_script)], cwd=str(TEMPLATES_DIR), timeout=30)
    print("Index rebuilt.")


if __name__ == "__main__":
    main()