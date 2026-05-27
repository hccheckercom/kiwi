#!/usr/bin/env python3
"""Convert Kiwi lessons to Semgrep format.

Usage:
    python tools/convert_to_semgrep.py --category php-security --dry-run
    python tools/convert_to_semgrep.py --category php-security --apply
    python tools/convert_to_semgrep.py --lesson LES-031 --apply
"""

import argparse
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from scanner.converters.semgrep_converter import lesson_to_semgrep_rule
from scanner.loader import load_patterns, get_lesson_content


def convert_lesson_file(lesson_path: Path, dry_run: bool = True) -> dict:
    """Convert a single lesson file to Semgrep format.

    Returns:
        dict with keys: success, lesson_id, convertible, reason, changes
    """
    try:
        with open(lesson_path, "r", encoding="utf-8") as f:
            content = f.read()
    except (OSError, IOError) as e:
        return {
            "success": False,
            "lesson_id": lesson_path.stem,
            "convertible": False,
            "reason": f"Failed to read file: {e}",
            "changes": None
        }

    # Parse frontmatter
    if not content.startswith("---"):
        return {
            "success": False,
            "lesson_id": lesson_path.stem,
            "convertible": False,
            "reason": "No frontmatter found",
            "changes": None
        }

    parts = content.split("---", 2)
    if len(parts) < 3:
        return {
            "success": False,
            "lesson_id": lesson_path.stem,
            "convertible": False,
            "reason": "Invalid frontmatter format",
            "changes": None
        }

    import yaml
    try:
        fm = yaml.safe_load(parts[1])
    except yaml.YAMLError as e:
        return {
            "success": False,
            "lesson_id": lesson_path.stem,
            "convertible": False,
            "reason": f"YAML parse error: {e}",
            "changes": None
        }

    lesson_id = fm.get("id", lesson_path.stem)
    scan = fm.get("scan", {})

    # Handle case where scan is a string (e.g., "block", "manual")
    if isinstance(scan, str):
        return {
            "success": True,
            "lesson_id": lesson_id,
            "convertible": False,
            "reason": f"Scan is string: '{scan}'",
            "changes": None
        }

    scan_type = scan.get("type", "presence")

    # Check if already Semgrep
    if scan_type == "semgrep":
        return {
            "success": True,
            "lesson_id": lesson_id,
            "convertible": False,
            "reason": "Already Semgrep format",
            "changes": None
        }

    # Check if convertible
    if scan_type not in ("presence", "cross-check", "cross_check"):
        return {
            "success": True,
            "lesson_id": lesson_id,
            "convertible": False,
            "reason": f"Scan type '{scan_type}' not convertible",
            "changes": None
        }

    # Try to convert
    rule = lesson_to_semgrep_rule(fm)
    if rule is None:
        return {
            "success": True,
            "lesson_id": lesson_id,
            "convertible": False,
            "reason": "Pattern not convertible to Semgrep",
            "changes": None
        }

    # Build new frontmatter
    new_scan = {
        "type": "semgrep",
        "pattern": rule.get("pattern") or rule.get("patterns"),
        "languages": rule.get("languages", ["php"]),
        "regex_fallback": scan.get("pattern", "")
    }

    # Copy other scan fields
    for key in ("scope", "exclude", "exclude_path", "pre_check", "exclude_line",
                "scope_mode", "max_per_file", "skip_empty_scope", "context_guard"):
        if key in scan:
            new_scan[key] = scan[key]

    fm["scan"] = new_scan

    # Rebuild file content
    new_content = "---\n"
    new_content += yaml.dump(fm, allow_unicode=True, sort_keys=False)
    new_content += "---\n"
    new_content += parts[2]

    changes = {
        "old_type": scan_type,
        "new_type": "semgrep",
        "old_pattern": scan.get("pattern", ""),
        "new_pattern": new_scan["pattern"],
        "regex_fallback": new_scan["regex_fallback"]
    }

    if not dry_run:
        try:
            with open(lesson_path, "w", encoding="utf-8") as f:
                f.write(new_content)
        except (OSError, IOError) as e:
            return {
                "success": False,
                "lesson_id": lesson_id,
                "convertible": True,
                "reason": f"Failed to write file: {e}",
                "changes": changes
            }

    return {
        "success": True,
        "lesson_id": lesson_id,
        "convertible": True,
        "reason": "Converted successfully",
        "changes": changes
    }


def convert_category(category: str, dry_run: bool = True) -> dict:
    """Convert all lessons in a category.

    Returns:
        dict with keys: total, converted, skipped, failed, results
    """
    lessons_dir = Path(__file__).parent.parent / "lessons" / category

    if not lessons_dir.exists():
        print(f"ERROR: Category directory not found: {lessons_dir}")
        return {"total": 0, "converted": 0, "skipped": 0, "failed": 0, "results": []}

    results = []
    total = 0
    converted = 0
    skipped = 0
    failed = 0

    for lesson_file in sorted(lessons_dir.glob("LES-*.md")):
        total += 1
        result = convert_lesson_file(lesson_file, dry_run)
        results.append(result)

        if not result["success"]:
            failed += 1
        elif result["convertible"]:
            converted += 1
        else:
            skipped += 1

    return {
        "total": total,
        "converted": converted,
        "skipped": skipped,
        "failed": failed,
        "results": results
    }


def main():
    parser = argparse.ArgumentParser(description="Convert Kiwi lessons to Semgrep format")
    parser.add_argument("--category", help="Category to convert (e.g., php-security)")
    parser.add_argument("--lesson", help="Single lesson ID to convert (e.g., LES-031)")
    parser.add_argument("--dry-run", action="store_true", default=True,
                        help="Preview changes without writing (default)")
    parser.add_argument("--apply", action="store_true",
                        help="Apply changes to files")
    parser.add_argument("--verbose", action="store_true",
                        help="Show detailed conversion info")

    args = parser.parse_args()

    if not args.category and not args.lesson:
        print("ERROR: Specify --category or --lesson")
        sys.exit(2)

    dry_run = not args.apply
    mode = "DRY-RUN" if dry_run else "APPLY"

    print(f"=== Kiwi Lesson -> Semgrep Converter ({mode}) ===\n")

    if args.lesson:
        # Convert single lesson
        lessons_dir = Path(__file__).parent.parent / "lessons"
        lesson_file = None

        # Search for lesson file
        for md_file in lessons_dir.rglob(f"{args.lesson}.md"):
            lesson_file = md_file
            break

        if not lesson_file:
            print(f"ERROR: Lesson {args.lesson} not found")
            sys.exit(2)

        print(f"Converting: {lesson_file.relative_to(lessons_dir.parent)}")
        result = convert_lesson_file(lesson_file, dry_run)

        print(f"\nResult: {result['reason']}")

        if result["convertible"] and result["changes"]:
            changes = result["changes"]
            print(f"\nChanges:")
            print(f"  Type: {changes['old_type']} → {changes['new_type']}")
            print(f"  Old pattern: {changes['old_pattern'][:80]}...")
            print(f"  New pattern: {changes['new_pattern']}")
            print(f"  Fallback: {changes['regex_fallback'][:80]}...")

        sys.exit(0 if result["success"] else 1)

    # Convert category
    print(f"Category: {args.category}")
    summary = convert_category(args.category, dry_run)

    print(f"\n=== Summary ===")
    print(f"Total lessons: {summary['total']}")
    print(f"Converted: {summary['converted']}")
    print(f"Skipped: {summary['skipped']}")
    print(f"Failed: {summary['failed']}")

    if args.verbose:
        print(f"\n=== Details ===")
        for result in summary["results"]:
            status = "✓" if result["success"] else "✗"
            convertible = "CONV" if result["convertible"] else "SKIP"
            print(f"{status} {result['lesson_id']:15} {convertible:6} {result['reason']}")

            if result["convertible"] and result["changes"] and args.verbose:
                changes = result["changes"]
                print(f"   Old: {changes['old_pattern'][:60]}...")
                print(f"   New: {changes['new_pattern']}")

    if dry_run and summary["converted"] > 0:
        print(f"\n💡 Run with --apply to write changes")

    sys.exit(0 if summary["failed"] == 0 else 1)


if __name__ == "__main__":
    main()