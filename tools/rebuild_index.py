#!/usr/bin/env python3
"""Rebuild README.md index from lessons/**/*.md frontmatter."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from scanner.loader import load_patterns


def main():
    kiwi_dir = Path(__file__).parent.parent
    lessons_dir = kiwi_dir / "lessons"
    readme_path = kiwi_dir / "README.md"

    patterns = load_patterns(str(lessons_dir))
    patterns.sort(key=lambda p: (p["category"], p["severity"] != "CRITICAL", p["severity"] != "HIGH", p["id"]))

    lines = []
    lines.append("# Kiwi — Bug/Lesson Index")
    lines.append("")
    lines.append("> Auto-generated. Do NOT edit manually. Run `python tools/rebuild_index.py`.")
    lines.append("")
    lines.append(f"**Total: {len(patterns)}** | ", )

    sev_counts = {}
    for p in patterns:
        s = p["severity"]
        sev_counts[s] = sev_counts.get(s, 0) + 1
    sev_parts = [f"{k}: {v}" for k, v in sorted(sev_counts.items())]
    lines[-1] += " | ".join(sev_parts)
    lines.append("")

    current_cat = None
    for p in patterns:
        if p["category"] != current_cat:
            current_cat = p["category"]
            lines.append(f"## {current_cat}")
            lines.append("")
            lines.append("| ID | Sev | Pattern | Summary |")
            lines.append("|----|-----|---------|---------|")

        pat_raw = p.get("pattern", "") or ""
        if not isinstance(pat_raw, str):
            pat_raw = str(pat_raw)
        pat_short = pat_raw[:40] + ("..." if len(pat_raw) > 40 else "")
        desc_short = (p.get("description") or p.get("title", ""))[:60]
        lines.append(f"| {p['id']} | {p['severity'][:4]} | `{pat_short}` | {desc_short} |")

        if p != patterns[-1] and patterns[patterns.index(p) + 1]["category"] != current_cat:
            lines.append("")

    content = "\n".join(lines) + "\n"
    with open(readme_path, "w", encoding="utf-8") as f:
        f.write(content)

    print(f"README.md rebuilt: {len(patterns)} entries in {len(sev_counts)} severities")


if __name__ == "__main__":
    main()
