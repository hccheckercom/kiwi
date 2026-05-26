#!/usr/bin/env python3
"""Kiwi Templates — Rebuild README.md index (self-healing).

Only requirement: TPL-*.md files exist with valid frontmatter.
This script auto-fixes everything else:
- _meta.json counts, next_id, total
- New sections auto-added to _meta.json
- README.md regenerated
"""

import json
import re
import sys
from datetime import date
from pathlib import Path

TEMPLATES_DIR = Path(__file__).parent.parent
META_PATH = TEMPLATES_DIR / "_meta.json"
SECTIONS_DIR = TEMPLATES_DIR / "sections"
README_PATH = TEMPLATES_DIR / "README.md"


def parse_frontmatter(filepath: Path) -> dict:
    text = filepath.read_text(encoding="utf-8")
    match = re.match(r"^---\s*\n(.*?)\n---", text, re.DOTALL)
    if not match:
        return {}
    lines = match.group(1).splitlines()
    meta = {}
    for line in lines:
        if ":" in line and not line.startswith(" ") and not line.startswith("-"):
            key, val = line.split(":", 1)
            val = val.strip().strip('"').strip("'")
            if val.startswith("[") and val.endswith("]"):
                val = [x.strip() for x in val[1:-1].split(",") if x.strip()]
            meta[key.strip()] = val
    return meta


def main():
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    meta = json.loads(META_PATH.read_text(encoding="utf-8"))
    templates_by_section = {}
    total = 0
    max_id = 0

    for md in sorted(SECTIONS_DIR.rglob("TPL-*.md")):
        fm = parse_frontmatter(md)
        if not fm:
            continue
        section = fm.get("section", md.parent.name)
        if section not in templates_by_section:
            templates_by_section[section] = []
        templates_by_section[section].append(fm)
        total += 1

        tpl_id = fm.get("id", "")
        if tpl_id.startswith("TPL-"):
            try:
                num = int(tpl_id.split("-")[1])
                max_id = max(max_id, num)
            except (ValueError, IndexError):
                pass

    # Auto-add new sections discovered from files
    for section_name in templates_by_section:
        if section_name not in meta["sections"]:
            meta["sections"][section_name] = {"count": 0, "desc": section_name.replace("-", " ").title()}

    # Auto-fix all counts
    for section_name in meta["sections"]:
        meta["sections"][section_name]["count"] = len(templates_by_section.get(section_name, []))

    # Auto-fix total and next_id
    meta["stats"]["total"] = total
    if max_id >= meta.get("next_id", 0):
        meta["next_id"] = max_id + 1

    # Generate README
    lines = [
        "# Kiwi Templates — Feature Library Index\n",
        "> Auto-generated. Do NOT edit manually. Run `python tools/rebuild_index.py`.\n",
        f"**Total: {total}**\n",
    ]

    if total == 0:
        lines.append("No templates yet. Use `python tools/add.py` to add templates.\n")
    else:
        for section_name in sorted(meta["sections"].keys()):
            tpls = templates_by_section.get(section_name, [])
            if not tpls:
                continue
            desc = meta["sections"][section_name]["desc"]
            lines.append(f"\n## {section_name} ({len(tpls)})\n")
            lines.append(f"_{desc}_\n")
            lines.append("| ID | Title | Theme | Tags | Style |")
            lines.append("|-----|-------|-------|------|-------|")
            for t in tpls:
                tpl_id = t.get("id", "?")
                title = t.get("title", "Untitled")
                theme = t.get("theme_source", "")
                tags = ", ".join(t.get("tags", [])) if isinstance(t.get("tags"), list) else str(t.get("tags", ""))
                style = t.get("design_style", "")
                lines.append(f"| {tpl_id} | {title} | {theme} | {tags} | {style} |")

    lines.append("")
    README_PATH.write_text("\n".join(lines), encoding="utf-8")

    # Save updated meta
    meta["last_updated"] = str(date.today())
    META_PATH.write_text(json.dumps(meta, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    print(f"README.md rebuilt: {total} templates across {len(templates_by_section)} sections.")


if __name__ == "__main__":
    main()