"""Copy universal lessons to plugins/generic/lessons/ based on classification report.

Usage:
    python tools/copy_universal_lessons.py [--dry-run]
"""

import json
import shutil
import sys
from pathlib import Path

KIWI_DIR = Path(__file__).resolve().parent.parent
LESSONS_DIR = KIWI_DIR / "lessons"
GENERIC_LESSONS_DIR = KIWI_DIR / "plugins" / "generic" / "lessons"
REPORT_PATH = KIWI_DIR / "tools" / "classification_report.json"


def main():
    dry_run = "--dry-run" in sys.argv

    if not REPORT_PATH.exists():
        print("ERROR: classification_report.json not found. Run classify_lessons.py first.")
        sys.exit(1)

    with open(REPORT_PATH, "r", encoding="utf-8") as f:
        report = json.load(f)

    universal_lessons = report["lessons"]["universal"]
    print(f"Copying {len(universal_lessons)} universal lessons...")

    if not dry_run:
        if GENERIC_LESSONS_DIR.exists():
            shutil.rmtree(GENERIC_LESSONS_DIR)
        GENERIC_LESSONS_DIR.mkdir(parents=True, exist_ok=True)

    categories_created = set()
    copied = 0

    for item in universal_lessons:
        src = LESSONS_DIR / item["file"]
        dst = GENERIC_LESSONS_DIR / item["file"]

        if not src.exists():
            print(f"  SKIP (missing): {item['file']}")
            continue

        category = item["category"]
        if category not in categories_created:
            if not dry_run:
                (GENERIC_LESSONS_DIR / category).mkdir(parents=True, exist_ok=True)
            categories_created.add(category)

        if not dry_run:
            shutil.copy2(src, dst)
        copied += 1

    print(f"\nDone: {copied} lessons copied to {len(categories_created)} categories")
    print(f"Target: {GENERIC_LESSONS_DIR}")

    if dry_run:
        print("[DRY RUN — no files written]")
    else:
        # Generate manifest
        manifest = {
            "name": "generic",
            "version": "1.0.0",
            "description": f"Universal code quality — {copied} lessons for any project",
            "author": "Kiwi",
            "languages": ["php", "js", "ts", "python", "css"],
            "frameworks": [],
            "platforms": ["wp", "nextjs", "python"],
            "scope_types": ["theme", "plugin", "app"],
            "checkers": ["presence", "absence", "cross-check", "bom-check"],
            "lessons_count": copied,
            "categories": len(categories_created),
        }
        manifest_path = GENERIC_LESSONS_DIR.parent / "manifest.json"
        with open(manifest_path, "w", encoding="utf-8") as f:
            json.dump(manifest, f, indent=2, ensure_ascii=False)
        print(f"Manifest written: {manifest_path}")


if __name__ == "__main__":
    main()