#!/usr/bin/env python3
"""Kiwi Templates — Query and search templates."""

import argparse
import re
import sys
from pathlib import Path

import yaml

TEMPLATES_DIR = Path(__file__).parent.parent
SECTIONS_DIR = TEMPLATES_DIR / "sections"


def parse_frontmatter(filepath: Path) -> dict:
    text = filepath.read_text(encoding="utf-8")
    match = re.match(r"^---\s*\n(.*?)\n---", text, re.DOTALL)
    if not match:
        return {}
    try:
        return yaml.safe_load(match.group(1)) or {}
    except Exception as e:
        import sys
        print(f"WARNING: YAML parse failed, falling back to line parser: {e}", file=sys.stderr)
        lines = match.group(1).splitlines()
        meta = {}
        for line in lines:
            if ":" in line:
                key, val = line.split(":", 1)
                meta[key.strip()] = val.strip().strip('"').strip("'")
        return meta


def load_all_templates() -> list:
    templates = []
    for md in sorted(SECTIONS_DIR.rglob("TPL-*.md")):
        fm = parse_frontmatter(md)
        if fm:
            fm["_path"] = str(md)
            templates.append(fm)
    return templates


def filter_templates(templates: list, section: str = None, tag: str = None,
                     keyword: str = None, style: str = None, theme: str = None) -> list:
    results = templates

    if section:
        results = [t for t in results if t.get("section") == section]

    if tag:
        tag_lower = tag.lower()
        results = [t for t in results if tag_lower in [x.lower() for x in t.get("tags", [])]]

    if style:
        style_lower = style.lower()
        results = [t for t in results if t.get("design_style", "").lower() == style_lower]

    if theme:
        theme_lower = theme.lower()
        results = [t for t in results if theme_lower in t.get("theme_source", "").lower()]

    if keyword:
        kw_lower = keyword.lower()
        def matches(t):
            features = t.get("features", [])
            features_str = " ".join(str(f) for f in features) if features else ""
            tags = t.get("tags", [])
            tags_str = " ".join(str(x) for x in tags) if tags else ""
            searchable = " ".join([
                t.get("title", ""),
                tags_str,
                features_str,
                t.get("section", ""),
                t.get("theme_source", ""),
            ]).lower()
            return kw_lower in searchable
        results = [t for t in results if matches(t)]

    return results


def format_list(templates: list, section_label: str = None) -> str:
    if not templates:
        return "Không tìm thấy template nào."

    label = section_label or "Tất cả"
    lines = [f"\nKiwi Templates — {label} ({len(templates)} mẫu):\n"]

    for i, t in enumerate(templates, 1):
        features = t.get("features", [])
        title = t.get("title", "Chưa đặt tên")
        tpl_id = t.get("id", "???")
        theme = t.get("theme_source", "")
        features_str = "; ".join(str(f) for f in features[:4]) if features else ""
        lines.append(f"  {i}. [{tpl_id}] {title}")
        lines.append(f"     Nguồn: {theme}")
        if features_str:
            lines.append(f"     Tính năng: {features_str}")

    lines.append("")
    lines.append("Chọn số để xem chi tiết code.")
    return "\n".join(lines)


def format_detail(template: dict) -> str:
    path = Path(template["_path"])
    content = path.read_text(encoding="utf-8")
    features = template.get("features", [])
    features_str = "\n".join(f"  - {f}" for f in features) if features else "  (chưa có)"
    return (
        f"\n{'=' * 60}\n"
        f"  [{template.get('id')}] {template.get('title')}\n"
        f"  Nguồn: {template.get('theme_source')} | Phong cách: {template.get('design_style')}\n"
        f"  Tính năng:\n{features_str}\n"
        f"{'=' * 60}\n\n{content}"
    )


def main():
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    parser = argparse.ArgumentParser(description="Query Kiwi Templates")
    parser.add_argument("section", nargs="?", help="Section type to filter (header, hero, etc.)")
    parser.add_argument("--tag", help="Filter by tag")
    parser.add_argument("--keyword", "-k", help="Full-text keyword search")
    parser.add_argument("--style", help="Filter by design style")
    parser.add_argument("--theme", help="Filter by source theme")
    parser.add_argument("--detail", type=int, help="Show full detail for template number N")
    parser.add_argument("--list-sections", action="store_true", help="List available sections")

    args = parser.parse_args()

    if args.list_sections:
        import json
        meta_path = TEMPLATES_DIR / "_meta.json"
        meta = json.loads(meta_path.read_text(encoding="utf-8"))
        print("\nAvailable sections:")
        for name, info in sorted(meta["sections"].items()):
            print(f"  {name:<15} ({info['count']} templates) — {info['desc']}")
        return

    templates = load_all_templates()
    filtered = filter_templates(
        templates,
        section=args.section,
        tag=args.tag,
        keyword=args.keyword,
        style=args.style,
        theme=args.theme,
    )

    if args.detail:
        if args.detail < 1 or args.detail > len(filtered):
            print(f"ERROR: Invalid number. Range: 1-{len(filtered)}", file=sys.stderr)
            sys.exit(1)
        print(format_detail(filtered[args.detail - 1]))
    else:
        label = args.section.capitalize() if args.section else None
        print(format_list(filtered, label))


if __name__ == "__main__":
    main()
