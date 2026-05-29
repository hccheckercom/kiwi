"""Tag Wezone-context lessons with `requires:`/`conflicts:` frontmatter (Fix 4).

Category-level ONLY — deliberately conservative to stay validatable (plan R4):
  wezone-api, loyalty        -> requires: wezone-commerce
  woocommerce-migration      -> conflicts: woocommerce

Why category-level and not fuzzy keyword matching:
  Over-tagging a UNIVERSAL lesson silently removes it from non-Wezone projects,
  and the Wezone-theme regression guard CANNOT catch that (a Wezone theme has the
  `wezone-commerce` cap, so its scan is identical no matter how much we tag). The
  only safe-and-validatable unit is a whole category that is Wezone-only by
  definition. Ambiguous categories (css-tokens, file-structure, feature-suggest)
  are left universal on purpose.

Safety properties (both verified by tests/regression_stack_filter.py):
  - On a Wezone project: every tagged lesson still loads (project has the cap),
    so violations are IDENTICAL to baseline. requires:/conflicts: cannot regress.
  - On a non-Wezone project: tagged lessons are filtered out, removing the
    "you're missing wz_*" / "don't use WC()" false-positive classes.

Frontmatter is edited TEXTUALLY (one inserted line) to preserve the exact,
carefully-quoted regex patterns; a YAML round-trip would reformat them.

Usage:
    python tools/classify_requires.py            # dry-run
    python tools/classify_requires.py --apply      # write frontmatter lines
"""
import re
import sys
from collections import Counter
from pathlib import Path

LESSONS_DIR = Path(__file__).resolve().parent.parent / "lessons"

# category -> (field, value)
CATEGORY_RULES = {
    "wezone-api": ("requires", "wezone-commerce"),
    "loyalty": ("requires", "wezone-commerce"),
    "woocommerce-migration": ("conflicts", "woocommerce"),
}


def _split_frontmatter(content: str):
    """Return (fm_block, rest) or None if there's no leading --- frontmatter."""
    m = re.match(r"^---\r?\n(.*?)\r?\n---\r?\n?", content, re.DOTALL)
    if not m:
        return None
    return m.group(1), content[m.end():]


def main(apply: bool):
    tagged, skipped_universal, already = [], 0, []

    for md in sorted(LESSONS_DIR.rglob("*.md")):
        if md.name == "README.md":
            continue
        try:
            content = md.read_text(encoding="utf-8")
        except OSError:
            continue
        split = _split_frontmatter(content)
        if not split:
            continue
        fm_block, rest = split

        rel = md.relative_to(LESSONS_DIR)
        category = rel.parts[0] if len(rel.parts) > 1 else md.parent.name

        rule = CATEGORY_RULES.get(category)
        if not rule:
            skipped_universal += 1
            continue
        field, value = rule

        # Idempotent: skip if requires:/conflicts: already present
        if re.search(rf"^\s*{field}\s*:", fm_block, re.MULTILINE):
            already.append(str(rel))
            continue

        tagged.append((str(rel), f"{field}: {value}"))

        if apply:
            new_fm = fm_block.rstrip("\r\n") + f"\n{field}: {value}\n"
            md.write_text(f"---\n{new_fm}---\n" + rest, encoding="utf-8")

    print(f"{'APPLIED' if apply else 'DRY-RUN'}")
    print(f"  tagged: {len(tagged)}")
    print(f"  already-tagged: {len(already)}")
    print(f"  universal (untouched): {skipped_universal}")
    by_rule = Counter(r for _, r in tagged)
    for rule, n in sorted(by_rule.items()):
        print(f"    {n:4d}  {rule}")


if __name__ == "__main__":
    main(apply="--apply" in sys.argv)