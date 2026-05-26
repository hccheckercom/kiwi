#!/usr/bin/env python3
"""Add a new lesson to Kiwi knowledge base. Supports interactive and non-interactive modes."""

import argparse
import json
import sys
from datetime import date
from pathlib import Path

KIWI_DIR = Path(__file__).parent.parent
META_FILE = KIWI_DIR / "_meta.json"
LESSONS_DIR = KIWI_DIR / "lessons"


def _auto_rebuild():
    """Auto-rebuild README index after adding a lesson."""
    import subprocess
    rebuild_script = Path(__file__).parent / "rebuild_index.py"
    if rebuild_script.exists():
        subprocess.run([sys.executable, str(rebuild_script)], cwd=str(KIWI_DIR), encoding="utf-8", timeout=30)
        print("Index rebuilt.")


def load_meta() -> dict:
    with open(META_FILE, "r", encoding="utf-8-sig") as f:
        return json.load(f)


def save_meta(meta: dict):
    with open(META_FILE, "w", encoding="utf-8") as f:
        json.dump(meta, f, indent=2, ensure_ascii=False)


def build_lesson_content(lesson_id, severity, category, title, scan_type, pattern,
                         scope, exclude, cross_check, cross_check_scope, source, tags,
                         bad_code="", good_code="", why="", grep_hint=""):
    lines = []
    lines.append("---")
    lines.append(f"id: {lesson_id}")
    lines.append(f"severity: {severity}")
    lines.append(f"category: {category}")

    if "'" in title and '"' not in title:
        lines.append(f'title: "{title}"')
    else:
        lines.append(f"title: '{title}'")

    lines.append(f"tags: [{tags}]")
    if source:
        lines.append(f'source: "{source}"')
    lines.append(f"date: {date.today().isoformat()}")
    lines.append("scan:")
    lines.append(f'  type: "{scan_type}"')

    # YAML quoting for pattern: avoid ' inside single-quoted strings
    if "'" in pattern and ("\\" in pattern or '"' in pattern):
        # Has both ' and \ or " — replace ' with \x27 and use single quotes
        safe_pattern = pattern.replace("'", "\\x27")
        lines.append(f"  pattern: '{safe_pattern}'")
    elif "\\" in pattern or '"' in pattern:
        lines.append(f"  pattern: '{pattern}'")
    else:
        lines.append(f'  pattern: "{pattern}"')

    lines.append(f'  scope: "{scope}"')
    if exclude:
        lines.append(f'  exclude: "{exclude}"')
    if cross_check:
        if "\\" in cross_check or '"' in cross_check:
            lines.append(f"  cross_check: '{cross_check}'")
        else:
            lines.append(f'  cross_check: "{cross_check}"')
    if cross_check_scope:
        lines.append(f'  cross_check_scope: "{cross_check_scope}"')
    lines.append("---")
    lines.append("")
    lines.append("## Bad")
    lines.append("```php")
    lines.append(bad_code or "// TODO: add bad example")
    lines.append("```")
    lines.append("")
    lines.append("## Good")
    lines.append("```php")
    lines.append(good_code or "// TODO: add good example")
    lines.append("```")
    lines.append("")
    lines.append("## Why")
    lines.append(why or "TODO: explain why this is a problem")
    lines.append("")
    lines.append("## Grep")
    lines.append(grep_hint or f"`{pattern}` — in `{scope}`")

    return "\n".join(lines) + "\n"


def add_lesson(category, severity, title, scan_type, pattern, scope,
               exclude="", cross_check="", cross_check_scope="",
               source="", tags="theme", bad_code="", good_code="", why="", grep_hint=""):
    """Add a lesson programmatically. Returns (lesson_id, file_path)."""
    meta = load_meta()

    is_feature = category == "feature-suggest"
    if is_feature:
        next_id = meta.get("next_fea_id", 3)
        lesson_id = f"FEA-{next_id:03d}"
        severity = "SUGGEST"
    else:
        next_id = meta.get("next_id", 109)
        lesson_id = f"LES-{next_id:03d}"

    content = build_lesson_content(
        lesson_id, severity, category, title, scan_type, pattern,
        scope, exclude, cross_check, cross_check_scope, source, tags,
        bad_code, good_code, why, grep_hint
    )

    out_dir = LESSONS_DIR / category
    out_dir.mkdir(parents=True, exist_ok=True)
    out_file = out_dir / f"{lesson_id}.md"
    out_file.write_text(content, encoding="utf-8")

    if is_feature:
        meta["next_fea_id"] = next_id + 1
    else:
        meta["next_id"] = next_id + 1
    meta["last_updated"] = date.today().isoformat()
    if category in meta.get("categories", {}):
        meta["categories"][category]["count"] = meta["categories"][category].get("count", 0) + 1
    else:
        meta["categories"][category] = {"count": 1, "desc": ""}
    if "stats" not in meta:
        meta["stats"] = {"total": 0, "critical": 0, "high": 0, "suggest": 0}
    meta["stats"]["total"] = meta["stats"].get("total", 0) + 1
    if severity == "CRITICAL":
        meta["stats"]["critical"] = meta["stats"].get("critical", 0) + 1
    elif severity == "HIGH":
        meta["stats"]["high"] = meta["stats"].get("high", 0) + 1
    elif severity == "SUGGEST":
        meta["stats"]["suggest"] = meta["stats"].get("suggest", 0) + 1
    save_meta(meta)

    return lesson_id, str(out_file)


def interactive_mode():
    meta = load_meta()
    categories = list(meta.get("categories", {}).keys())

    print("=== KIWI — Add New Lesson ===\n")
    print("Categories:", ", ".join(categories))
    category = input("Category: ").strip()
    if category not in categories:
        confirm = input(f"New category '{category}'. Create? (y/n): ").strip()
        if confirm.lower() != "y":
            return

    is_feature = category == "feature-suggest"
    if is_feature:
        severity = "SUGGEST"
    else:
        sev = input("Severity (CRITICAL/HIGH): ").strip().upper()
        severity = sev if sev in ("CRITICAL", "HIGH") else "HIGH"

    title = input("Title: ").strip()
    print("\nScan pattern config:")
    scan_type = input("Type (presence/absence/cross-check/bom-check) [presence]: ").strip() or "presence"
    pattern = input("Regex pattern: ").strip()
    scope = input("Scope [**/*.php]: ").strip() or "**/*.php"
    exclude = input("Exclude (optional): ").strip()

    cross_check = ""
    cross_check_scope = ""
    if scan_type == "cross-check":
        cross_check = input("Cross-check pattern: ").strip()
        cross_check_scope = input("Cross-check scope (optional): ").strip()

    source = input("Source theme/plugin: ").strip()
    tags = input("Tags (theme/plugin/both) [theme]: ").strip() or "theme"

    lesson_id, filepath = add_lesson(
        category, severity, title, scan_type, pattern, scope,
        exclude, cross_check, cross_check_scope, source, tags
    )

    print(f"\nCreated: {filepath}")
    print(f"ID: {lesson_id}")
    _auto_rebuild()


def main():
    parser = argparse.ArgumentParser(description="Add a new Kiwi lesson")
    parser.add_argument("--category", "-c", help="Lesson category")
    parser.add_argument("--severity", "-s", choices=["CRITICAL", "HIGH", "SUGGEST"], default="HIGH")
    parser.add_argument("--title", "-t", help="Lesson title")
    parser.add_argument("--type", dest="scan_type", default="presence",
                        choices=["presence", "absence", "cross-check", "bom-check"])
    parser.add_argument("--pattern", "-p", help="Regex pattern")
    parser.add_argument("--scope", default="**/*.php", help="File scope")
    parser.add_argument("--exclude", default="", help="Exclude pattern")
    parser.add_argument("--cross-check", default="", help="Cross-check pattern")
    parser.add_argument("--cross-check-scope", default="", help="Cross-check scope")
    parser.add_argument("--source", default="", help="Source theme/plugin")
    parser.add_argument("--tags", default="theme", choices=["theme", "plugin", "both"])
    parser.add_argument("--bad", default="", help="Bad code example")
    parser.add_argument("--good", default="", help="Good code example")
    parser.add_argument("--why", default="", help="Why this is a problem")
    parser.add_argument("--json", action="store_true", help="Output JSON result")

    args = parser.parse_args()

    # If required args provided → non-interactive
    if args.category and args.title and args.pattern:
        lesson_id, filepath = add_lesson(
            category=args.category,
            severity=args.severity,
            title=args.title,
            scan_type=args.scan_type,
            pattern=args.pattern,
            scope=args.scope,
            exclude=args.exclude,
            cross_check=args.cross_check,
            cross_check_scope=args.cross_check_scope,
            source=args.source,
            tags=args.tags,
            bad_code=args.bad,
            good_code=args.good,
            why=args.why,
        )
        if args.json:
            print(json.dumps({"id": lesson_id, "file": filepath}, ensure_ascii=False))
        else:
            print(f"Created: {lesson_id} → {filepath}")
        _auto_rebuild()
    else:
        interactive_mode()


if __name__ == "__main__":
    main()
