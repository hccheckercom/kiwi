"""Regression harness for Fix 4 (project-signature lesson filtering).

Captures the set of (lesson_id, file, line) violations for a target project so a
classification pass can be proven behaviour-neutral on Wezone projects.

Usage:
    python tests/regression_stack_filter.py snapshot <project_path> <out.json>
    python tests/regression_stack_filter.py diff <baseline.json> <after.json>
    python tests/regression_stack_filter.py caps <project_path>
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def _snapshot(project_path, out_path):
    from scanner.loader import invalidate_cache
    from scanner import project_profile
    from scanner.cli import scan_theme

    invalidate_cache()
    project_profile.invalidate()

    caps = project_profile.detect_stack(project_path, use_cache=False)
    report = scan_theme(project_path, severity_filter="ALL")
    rows = sorted(
        f"{v.lesson_id}|{v.file}|{v.line}" for v in report.violations
    )
    data = {
        "project": os.path.abspath(project_path),
        "caps": sorted(caps),
        "count": len(rows),
        "rows": rows,
    }
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)
    print(f"caps={sorted(caps)} violations={len(rows)} -> {out_path}")


def _diff(baseline_path, after_path):
    with open(baseline_path, encoding="utf-8") as f:
        base = json.load(f)
    with open(after_path, encoding="utf-8") as f:
        after = json.load(f)
    bset, aset = set(base["rows"]), set(after["rows"])
    removed = sorted(bset - aset)
    added = sorted(aset - bset)
    print(f"baseline={base['count']} (caps={base['caps']})")
    print(f"after   ={after['count']} (caps={after['caps']})")
    print(f"removed ={len(removed)}  added={len(added)}")
    for r in removed[:30]:
        print(f"  - {r}")
    for r in added[:30]:
        print(f"  + {r}")
    if not removed and not added:
        print("RESULT: IDENTICAL — no regression")
        return 0
    print("RESULT: DIFF DETECTED")
    return 1


def _caps(project_path):
    from scanner import project_profile
    print(project_profile.detect_stack(project_path, use_cache=False))


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else ""
    if cmd == "snapshot":
        _snapshot(sys.argv[2], sys.argv[3])
    elif cmd == "diff":
        sys.exit(_diff(sys.argv[2], sys.argv[3]))
    elif cmd == "caps":
        _caps(sys.argv[2])
    else:
        print(__doc__)
        sys.exit(2)