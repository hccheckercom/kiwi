"""Classify 740 lessons into Universal vs Wezone-specific.

Usage:
    python tools/classify_lessons.py [--dry-run] [--output report.json]

3-layer classification:
  Layer 1: Categories guaranteed non-WP (python, react, fastapi, etc.) → universal
  Layer 2: Keyword scan on all remaining lessons
  Layer 3: Ambiguous → review_needed
"""

import json
import re
import sys
from pathlib import Path

KIWI_DIR = Path(__file__).resolve().parent.parent
LESSONS_DIR = KIWI_DIR / "lessons"

# No guaranteed universal categories — always run keyword scan
# Even "pure" categories like python/react can have Wezone examples mixed in
GUARANTEED_UNIVERSAL_CATEGORIES = set()

# Categories that are 100% Wezone-specific by definition
WEZONE_CATEGORIES = {
    "wezone-api",  # All 109 lessons are wz_* patterns
    "loyalty",     # Wezone loyalty program
}

# Layer 2: Keywords that mark a lesson as Wezone-specific
WEZONE_KEYWORDS = [
    # Wezone Commer API
    "wz_", "wezone", "wezone_is_active", "wezone-commer",
    "wz_config", "wz_bulk_insert", "wz_get_product",
    "wz_cart", "wz_order", "wz_product", "wz_get_",
    "WezoneCommer",
    # Wezone brand / domains
    "Wezone.vn", "wezone.vn", "demo.wezone.vn",
    "WeZone\\", "Wezone\\",
    "WEZONE_",
    # Wezone data patterns
    "$product['", '$product["',
    "store-config.php", "store_config",
    # Wezone theme names
    "sfvn-", "trunganh-", "funilux-",
    # Wezone architecture
    "wz-component", "wz_component",
    "Plugin.php",
    "mu-plugins",
    "wezone-plugins",
]

WEZONE_REGEXES = [
    re.compile(r"\bwz_\w+"),
    re.compile(r"\bwezone_\w+"),
    re.compile(r"\$product\[['\"]"),
    re.compile(r"wz-[a-z]+-"),
]

# Keywords that indicate generic WP (not Wezone-specific)
# These should NOT trigger Wezone classification
WP_GENERIC_KEYWORDS = [
    "wp_enqueue", "add_action", "add_filter", "wp_nonce",
    "esc_html", "esc_attr", "sanitize_", "wp_kses",
    "get_post_meta", "update_post_meta", "WP_Query",
]


def classify_lesson(path: Path, category: str) -> tuple:
    """Returns (classification, reason)."""
    # Layer 1: guaranteed categories
    if category in GUARANTEED_UNIVERSAL_CATEGORIES:
        return ("universal", f"category:{category} guaranteed universal")
    if category in WEZONE_CATEGORIES:
        return ("wezone", f"category:{category} is wezone-only")

    # Layer 2: keyword + regex scan on file content
    try:
        content = path.read_text(encoding="utf-8", errors="ignore")
    except OSError:
        return ("review", "cannot read file")

    content_lower = content.lower()
    for keyword in WEZONE_KEYWORDS:
        if keyword.lower() in content_lower:
            return ("wezone", f"keyword:{keyword}")

    for regex in WEZONE_REGEXES:
        if regex.search(content):
            return ("wezone", f"regex:{regex.pattern}")

    # If it's in a PHP/WP category but has no Wezone markers → universal
    return ("universal", "no wezone markers found")


def main():
    output_file = "classification_report.json"
    dry_run = "--dry-run" in sys.argv

    for i, arg in enumerate(sys.argv):
        if arg == "--output" and i + 1 < len(sys.argv):
            output_file = sys.argv[i + 1]

    report = {"universal": [], "wezone": [], "review": []}
    category_stats = {}

    for category_dir in sorted(LESSONS_DIR.iterdir()):
        if not category_dir.is_dir():
            continue
        category = category_dir.name
        cat_counts = {"universal": 0, "wezone": 0, "review": 0}

        for lesson_file in sorted(category_dir.glob("*.md")):
            classification, reason = classify_lesson(lesson_file, category)
            report[classification].append({
                "file": str(lesson_file.relative_to(LESSONS_DIR)),
                "category": category,
                "id": lesson_file.stem,
                "reason": reason,
            })
            cat_counts[classification] += 1

        category_stats[category] = cat_counts

    # Summary
    total = len(report["universal"]) + len(report["wezone"]) + len(report["review"])
    print(f"\n{'='*60}")
    print(f"CLASSIFICATION REPORT")
    print(f"{'='*60}")
    print(f"Total lessons:  {total}")
    print(f"Universal:      {len(report['universal'])} ({100*len(report['universal'])//total}%)")
    print(f"Wezone:         {len(report['wezone'])} ({100*len(report['wezone'])//total}%)")
    print(f"Review needed:  {len(report['review'])}")
    print(f"{'='*60}\n")

    # Per-category breakdown
    print(f"{'Category':<25} {'Universal':>10} {'Wezone':>10} {'Review':>10}")
    print(f"{'-'*55}")
    for cat in sorted(category_stats.keys()):
        s = category_stats[cat]
        print(f"{cat:<25} {s['universal']:>10} {s['wezone']:>10} {s['review']:>10}")

    # Save report
    if not dry_run:
        output_path = KIWI_DIR / "tools" / output_file
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump({
                "summary": {
                    "total": total,
                    "universal": len(report["universal"]),
                    "wezone": len(report["wezone"]),
                    "review": len(report["review"]),
                },
                "category_stats": category_stats,
                "lessons": report,
            }, f, indent=2, ensure_ascii=False)
        print(f"\nReport saved to: {output_path}")
    else:
        print("\n[DRY RUN — no file written]")

    # List review-needed lessons
    if report["review"]:
        print(f"\n--- REVIEW NEEDED ({len(report['review'])}) ---")
        for item in report["review"]:
            print(f"  {item['file']}: {item['reason']}")


if __name__ == "__main__":
    main()