#!/usr/bin/env python3
"""Kiwi stats — severity/category breakdown."""

import os
import sys
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from scanner.loader import load_patterns


def main():
    kiwi_dir = Path(__file__).parent.parent
    lessons_dir = kiwi_dir / "lessons"
    patterns = load_patterns(str(lessons_dir))

    print("=" * 50)
    print("  KIWI KNOWLEDGE BASE — Statistics")
    print("=" * 50)
    print(f"  Total patterns: {len(patterns)}")
    print()

    # Severity breakdown
    sev = {}
    for p in patterns:
        s = p["severity"]
        sev[s] = sev.get(s, 0) + 1
    print("  By Severity:")
    for s in ["CRITICAL", "HIGH", "SUGGEST", "INFO"]:
        if s in sev:
            print(f"    {s:10s} {sev[s]:3d}")

    # Category breakdown
    cats = {}
    for p in patterns:
        c = p["category"]
        cats[c] = cats.get(c, 0) + 1
    print()
    print("  By Category:")
    for c, count in sorted(cats.items(), key=lambda x: -x[1]):
        print(f"    {c:20s} {count:3d}")

    # Type breakdown
    types = {}
    for p in patterns:
        t = p["type"]
        types[t] = types.get(t, 0) + 1
    print()
    print("  By Check Type:")
    for t, count in sorted(types.items(), key=lambda x: -x[1]):
        print(f"    {t:15s} {count:3d}")

    print()
    print("=" * 50)


if __name__ == "__main__":
    main()