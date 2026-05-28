"""Comprehensive QA for A2 — Classify Lessons."""

import sys
import json
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core.plugin_registry import discover_plugins, reset_registry
from core.plugin_loader import detect_project, load_plugins, get_primary_plugin

KIWI_DIR = Path(__file__).resolve().parent.parent


def main():
    print("=" * 60)
    print("A2 COMPREHENSIVE QA")
    print("=" * 60)
    passed = 0
    failed = 0

    def check(name, condition, detail=""):
        nonlocal passed, failed
        if condition:
            passed += 1
            print(f"  PASS [{passed}] {name}")
        else:
            failed += 1
            print(f"  FAIL [{name}] {detail}")

    # === GROUP 1: Plugin Discovery ===
    print("\n--- GROUP 1: Plugin Discovery ---")
    reset_registry()
    plugins = discover_plugins()
    check("2 plugins discovered", len(plugins) == 2, f"got {len(plugins)}")
    names = sorted([p.get_manifest().name for p in plugins])
    check("plugin names correct", names == ["generic", "wezone-wp"], f"got {names}")

    # === GROUP 2: Lesson Counts ===
    print("\n--- GROUP 2: Lesson Counts ---")
    wz = [p for p in plugins if p.get_manifest().name == "wezone-wp"][0]
    gen = [p for p in plugins if p.get_manifest().name == "generic"][0]
    wz_lessons = list(Path(wz.get_lessons_path()).rglob("*.md"))
    gen_lessons = list(Path(gen.get_lessons_path()).rglob("*.md"))
    check("wezone-wp: 740 lessons", len(wz_lessons) == 740, f"got {len(wz_lessons)}")
    check("generic: 379 lessons", len(gen_lessons) == 379, f"got {len(gen_lessons)}")
    check("generic < wezone (proper subset)", len(gen_lessons) < len(wz_lessons))

    # === GROUP 3: Zero Contamination ===
    print("\n--- GROUP 3: Zero Contamination ---")
    contaminated = []
    for f in Path(KIWI_DIR / "plugins/generic/lessons").rglob("*.md"):
        content = f.read_text(encoding="utf-8", errors="ignore").lower()
        if "wz_" in content or "wezone" in content:
            contaminated.append(f.name)
    check("zero wz_/wezone in generic", len(contaminated) == 0, f"{len(contaminated)} files: {contaminated[:5]}")

    contaminated2 = []
    for f in Path(KIWI_DIR / "plugins/generic/lessons").rglob("*.md"):
        content = f.read_text(encoding="utf-8", errors="ignore")
        if "mu-plugins" in content:
            contaminated2.append(f.name)
    check("zero mu-plugins in generic", len(contaminated2) == 0, f"{len(contaminated2)} files: {contaminated2[:5]}")

    # === GROUP 4: Classification Integrity ===
    print("\n--- GROUP 4: Classification Integrity ---")
    report_path = KIWI_DIR / "tools" / "classification_report.json"
    check("classification_report.json exists", report_path.exists())
    with open(report_path, "r", encoding="utf-8") as f:
        report = json.load(f)
    s = report["summary"]
    total = s["universal"] + s["wezone"] + s["review"]
    check("total = 740", total == 740, f"got {total}")
    check("universal = 379", s["universal"] == 379, f"got {s['universal']}")
    check("wezone = 361", s["wezone"] == 361, f"got {s['wezone']}")
    check("review = 0", s["review"] == 0, f"got {s['review']}")

    # === GROUP 5: Project Detection ===
    print("\n--- GROUP 5: Project Detection ---")
    reset_registry()
    detected = detect_project(r"D:\projects\wezone\wezone-plugins")
    check("wezone-plugins: wezone-wp wins", detected[0][0].get_manifest().name == "wezone-wp")
    check("wezone-plugins: conf >= 0.5", detected[0][1] >= 0.5, f"conf={detected[0][1]}")

    detected_theme = detect_project(r"D:\projects\wezone\themes\sfvn")
    if detected_theme:
        check("sfvn theme: wezone-wp wins", detected_theme[0][0].get_manifest().name == "wezone-wp")
    else:
        check("sfvn theme: detected", False, "no detection")

    import tempfile, os, shutil
    tmp = tempfile.mkdtemp()
    with open(os.path.join(tmp, "main.py"), "w") as f:
        f.write("print(1)")
    detected_tmp = detect_project(tmp)
    if detected_tmp:
        check("random project: generic fallback", detected_tmp[0][0].get_manifest().name == "generic")
    else:
        loaded = load_plugins(tmp)
        check("random project: load_plugins returns plugins", len(loaded) > 0)
    shutil.rmtree(tmp)

    # === GROUP 6: Manifest Consistency ===
    print("\n--- GROUP 6: Manifest Consistency ---")
    gen_manifest_path = KIWI_DIR / "plugins" / "generic" / "manifest.json"
    check("generic manifest.json exists", gen_manifest_path.exists())
    with open(gen_manifest_path, "r", encoding="utf-8") as f:
        gen_manifest = json.load(f)
    check("manifest lessons_count = 379", gen_manifest["lessons_count"] == 379, f"got {gen_manifest['lessons_count']}")
    actual_cats = [d.name for d in (KIWI_DIR / "plugins/generic/lessons").iterdir() if d.is_dir()]
    check(
        f"manifest categories = actual ({len(actual_cats)})",
        gen_manifest["categories"] == len(actual_cats),
        f"manifest={gen_manifest['categories']}, actual={len(actual_cats)}",
    )

    # === GROUP 7: Plugin Interface Compliance ===
    print("\n--- GROUP 7: Plugin Interface Compliance ---")
    gen_checkers = gen.get_checkers()
    check("generic get_checkers() works", isinstance(gen_checkers, dict))
    check("generic has presence checker", "presence" in gen_checkers)
    check("generic has absence checker", "absence" in gen_checkers)
    check("generic has cross-check checker", "cross-check" in gen_checkers)
    check("generic has bom-check checker", "bom-check" in gen_checkers)
    check("generic get_quality_rules() = []", gen.get_quality_rules() == [])
    check("generic get_context_map() = {}", gen.get_context_map() == {})
    check("generic detect_project() > 0", gen.detect_project(".") > 0)
    wz_checkers = wz.get_checkers()
    check("wezone get_checkers() >= 6", len(wz_checkers) >= 6, f"got {len(wz_checkers)}")
    check("wezone get_quality_rules() >= 5", len(wz.get_quality_rules()) >= 5)
    check("wezone get_context_map() non-empty", len(wz.get_context_map()) > 0)

    # === GROUP 8: No NEW Duplicate Lessons ===
    print("\n--- GROUP 8: No NEW Duplicate Lessons ---")
    # Source lessons/ has pre-existing duplicate IDs across categories (44 dupes).
    # Verify generic doesn't introduce duplicates BEYOND what source already has.
    from collections import Counter
    source_ids = [f.stem for f in (KIWI_DIR / "lessons").rglob("*.md")]
    source_dupes = {k for k, v in Counter(source_ids).items() if v > 1}

    gen_all = [f.stem for f in Path(KIWI_DIR / "plugins/generic/lessons").rglob("*.md")]
    gen_dupes = {k for k, v in Counter(gen_all).items() if v > 1}
    new_dupes = gen_dupes - source_dupes
    check("no NEW duplicate IDs introduced by A2", len(new_dupes) == 0, f"new dupes: {list(new_dupes)[:5]}")
    check(f"pre-existing dupes in generic: {len(gen_dupes)} (inherited from source: {len(source_dupes)})",
          gen_dupes.issubset(source_dupes), f"unexpected: {gen_dupes - source_dupes}")

    gen_ids = set(gen_all)
    wz_ids = set(source_ids)
    missing = gen_ids - wz_ids
    check("all generic IDs exist in wezone", len(missing) == 0, f"missing: {list(missing)[:5]}")

    # === GROUP 9: Subset Correctness ===
    print("\n--- GROUP 9: Subset Correctness ---")
    # Every file in generic/lessons/ must also exist in lessons/ (same content)
    mismatches = []
    for f in Path(KIWI_DIR / "plugins/generic/lessons").rglob("*.md"):
        rel = f.relative_to(KIWI_DIR / "plugins/generic/lessons")
        original = KIWI_DIR / "lessons" / rel
        if not original.exists():
            mismatches.append(f"MISSING: {rel}")
        else:
            gen_content = f.read_text(encoding="utf-8", errors="ignore")
            orig_content = original.read_text(encoding="utf-8", errors="ignore")
            if gen_content != orig_content:
                mismatches.append(f"DIFF: {rel}")
    check("all generic lessons match originals", len(mismatches) == 0, f"{len(mismatches)} issues: {mismatches[:3]}")

    # === GROUP 10: Script Reproducibility ===
    print("\n--- GROUP 10: Script Reproducibility ---")
    check("classify_lessons.py exists", (KIWI_DIR / "tools/classify_lessons.py").exists())
    check("copy_universal_lessons.py exists", (KIWI_DIR / "tools/copy_universal_lessons.py").exists())

    # === SUMMARY ===
    print(f"\n{'=' * 60}")
    print(f"RESULTS: {passed} passed, {failed} failed")
    print(f"{'=' * 60}")
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())