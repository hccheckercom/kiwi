#!/usr/bin/env python3
"""Audit Kiwi Templates system integrity."""
import json, re, sys
from pathlib import Path

TEMPLATES_DIR = Path(__file__).parent.parent
SECTIONS_DIR = TEMPLATES_DIR / "sections"
META_PATH = TEMPLATES_DIR / "_meta.json"

def parse_frontmatter(filepath):
    text = filepath.read_text(encoding="utf-8")
    match = re.match(r"^---\s*\n(.*?)\n---", text, re.DOTALL)
    if not match:
        return {}, text
    try:
        import yaml
        fm = yaml.safe_load(match.group(1)) or {}
    except Exception as e:
        import sys
        print(f"[kiwi] audit frontmatter parse error: {e}", file=sys.stderr)
        fm = {}
    return fm, text

def main():
    meta = json.loads(META_PATH.read_text(encoding="utf-8"))
    errors = []
    templates = []

    for md in sorted(SECTIONS_DIR.rglob("TPL-*.md")):
        fm, content = parse_frontmatter(md)
        if not fm:
            errors.append(f"{md.name}: cannot parse frontmatter")
            continue
        fm["_path"] = md
        templates.append(fm)

    print(f"Templates found: {len(templates)}")
    print(f"_meta.json: next_id={meta['next_id']}, total={meta['stats']['total']}")
    print()

    for t in templates:
        tid = t.get("id", "???")
        section = t.get("section", "MISSING")
        title = t.get("title", "MISSING")
        tags = t.get("tags", [])
        features = t.get("features", [])
        path = t["_path"]
        content = path.read_text(encoding="utf-8")
        actual_section = path.parent.name

        if actual_section != section:
            errors.append(f"{tid}: section mismatch - frontmatter='{section}', folder='{actual_section}'")
        if not title or title == "MISSING":
            errors.append(f"{tid}: missing title")
        if not tags:
            errors.append(f"{tid}: missing tags")
        if not features:
            errors.append(f"{tid}: missing features")
        if "## Code" not in content:
            errors.append(f"{tid}: missing '## Code' section")
        if "<?php" not in content:
            errors.append(f"{tid}: missing PHP code")

        print(f"  [{tid}] {actual_section}/{path.name} - OK")
        print(f"         title: {title[:60]}")
        print(f"         tags={len(tags)}, features={len(features)}, size={len(content)} bytes")

    print()

    # Meta consistency
    actual_count = len(templates)
    if meta["stats"]["total"] != actual_count:
        errors.append(f"_meta total={meta['stats']['total']} but actual={actual_count}")

    if templates:
        max_id = max(int(t["id"].split("-")[1]) for t in templates)
        if meta["next_id"] <= max_id:
            errors.append(f"_meta next_id={meta['next_id']} but max existing ID={max_id} (should be > max)")

    for section_name, info in meta["sections"].items():
        actual = sum(1 for t in templates if t.get("section") == section_name)
        if info["count"] != actual:
            errors.append(f"_meta section '{section_name}' count={info['count']} but actual={actual}")

    print("=" * 50)
    if errors:
        print(f"ERRORS ({len(errors)}):")
        for e in errors:
            print(f"  ! {e}")
        sys.exit(1)
    else:
        print("ALL CHECKS PASSED")
        sys.exit(0)

if __name__ == "__main__":
    main()
