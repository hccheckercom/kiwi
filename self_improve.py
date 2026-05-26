"""Self-improvement script — Kiwi scans and learns from its own codebase."""

import sys
import argparse
from pathlib import Path
from collections import defaultdict

sys.path.insert(0, str(Path(__file__).parent))

from scanner.cli import scan_theme
from learning.miner import mine_patterns
from memory.db import get_suggested_lessons, init_db
from agent.learn import learn_from_folder, gap_detect


def self_scan_and_learn(target=None, platform="python", auto_approve=False,
                        report_only=False, severity="ALL", learn=False):
    """Scan target codebase and learn new patterns.

    Args:
        target: Path to scan (default: Kiwi's own codebase)
        platform: Platform filter — python, wp, nextjs (default: python)
        auto_approve: Auto-approve CRITICAL/HIGH suggestions
        report_only: Only print violations, skip mine/approve
        severity: Severity filter — CRITICAL, HIGH, ALL
    """

    print("=" * 60)
    print(f"Kiwi Self-Improvement — platform: {platform}")
    print("=" * 60 + "\n")

    init_db()

    scan_path = Path(target) if target else Path(__file__).parent

    # Step 1: Scan
    print(f"Step 1: Scanning {scan_path.name}/ ...")
    report = scan_theme(
        str(scan_path),
        severity_filter=severity,
        platform=platform,
        use_cache=False,
    )

    total = len(report.violations) if hasattr(report, 'violations') else 0
    critical = report.critical_count if hasattr(report, 'critical_count') else 0
    high = report.high_count if hasattr(report, 'high_count') else 0
    suggest = report.suggest_count if hasattr(report, 'suggest_count') else 0

    print(f"  Total: {total} violations")
    print(f"  CRITICAL: {critical}")
    print(f"  HIGH: {high}")
    print(f"  SUGGEST: {suggest}\n")

    if total == 0:
        print("  Clean! No violations found.\n")
    else:
        # Top files by violation count
        file_counts = defaultdict(int)
        for v in report.violations:
            rel = Path(v.file).name if hasattr(v, 'file') else str(v)
            file_counts[rel] += 1
        top_files = sorted(file_counts.items(), key=lambda x: -x[1])[:10]
        print("  Top files:")
        for fname, count in top_files:
            print(f"    {count:3d} | {fname}")
        print()

        # Violations grouped by lesson
        lesson_counts = defaultdict(list)
        for v in report.violations:
            lid = v.lesson_id if hasattr(v, 'lesson_id') else "unknown"
            lesson_counts[lid].append(v)

        print("  Violations by lesson:")
        for lid, violations in sorted(lesson_counts.items(), key=lambda x: -len(x[1])):
            desc = violations[0].description if hasattr(violations[0], 'description') else ""
            print(f"    {len(violations):3d} | {lid}: {desc[:60]}")
        print()

        # Show details of each violation
        print("  Details:")
        for lid, violations in sorted(lesson_counts.items()):
            print(f"\n  --- {lid} ---")
            for v in violations[:5]:
                fname = Path(v.file).name if hasattr(v, 'file') else "?"
                line = v.line if hasattr(v, 'line') else "?"
                match_text = v.match[:80] if hasattr(v, 'match') else ""
                print(f"    {fname}:{line} — {match_text}")
            if len(violations) > 5:
                print(f"    ... and {len(violations) - 5} more")
        print()

    if report_only:
        print("Report-only mode — skipping mine/approve steps.")
        print("\n" + "=" * 60)
        return total

    # Step 2: Mine patterns
    print("Step 2: Mining patterns from violations...")
    patterns = mine_patterns(
        min_occurrences=2,
        similarity_threshold=0.8,
        lookback_days=30,
        path=str(scan_path)
    )
    print(f"  Found {len(patterns)} recurring patterns\n")

    # Step 3: Review suggestions
    print("Step 3: Reviewing suggested lessons...")
    suggestions = get_suggested_lessons(status="pending")

    if not suggestions:
        print("  No new suggestions to review\n")
    else:
        print(f"  {len(suggestions)} pending suggestions:\n")
        for s in suggestions[:10]:
            print(f"  ID {s['id']}: [{s['severity']}] {s['category']}")
            print(f"    Pattern: {s['pattern'][:80]}")
            print(f"    Example: {s['example_file']}:{s['example_line']}")
            print()

    # Step 4: Auto-approve
    if auto_approve and suggestions:
        print("Step 4: Auto-approving high-confidence suggestions...")
        try:
            from learning.generator import generate_lesson
            approved = 0
            for s in suggestions:
                if s['severity'] in ('CRITICAL', 'HIGH'):
                    lesson_id = generate_lesson(s['id'])
                    if lesson_id:
                        print(f"  + Created {lesson_id}")
                        approved += 1
            print(f"\n  Auto-approved {approved} lessons")
            if approved:
                print("  Run 'python tools/rebuild_index.py' to update README")
        except ImportError:
            print("  [warn] generate_lesson not available, skipping auto-approve")
    elif not auto_approve and suggestions:
        print("Step 4: Manual approval required")
        print("  Approve via: kiwi_approve_suggestion(suggestion_id=X)")

    # Step 5: Learn — detect new patterns from code
    if learn:
        print("\nStep 5: Learning new patterns from codebase...")
        # Only scan Python files when scanning Kiwi itself
        learn_file_types = ['py'] if platform == 'python' else None
        learn_result = learn_from_folder(
            path=str(scan_path),
            min_occurrences=2,
            auto_approve=auto_approve,
            file_types=learn_file_types,
        )
        n_files = learn_result.get('scanned_files', 0)
        n_patterns = learn_result.get('patterns_found', 0)
        n_sug = len(learn_result.get('suggestions', []))
        print(f"  Scanned {n_files} files, found {n_patterns} patterns, {n_sug} suggestions")

        for sug in learn_result.get('suggestions', []):
            print(f"  [{sug['severity']}] {sug['title']} — {sug['occurrences']} occurrences in {len(sug['files'])} files")

        # Step 5.5: Gap detect — catalog vs existing lessons
        if auto_approve:
            print("\nStep 5.5: Gap detect (catalog vs lessons)...")
            lang_map = {'python': ['python'], 'wp': ['php', 'js'], 'nextjs': ['js']}
            gap_langs = lang_map.get(platform, ['python', 'php', 'js'])
            gap_result = gap_detect(scan_path=str(scan_path), file_types=gap_langs)
            n_gaps = len(gap_result.get('gaps', []))
            n_covered = gap_result.get('already_covered', 0)
            n_created_gap = len(gap_result.get('created', []))
            print(f"  Catalog coverage: {n_covered} patterns already have lessons")
            if n_gaps > 0:
                print(f"  Found {n_gaps} gaps — created {n_created_gap} new lessons:")
                for c in gap_result.get('created', []):
                    print(f"    + {c['lesson_id']}: {c.get('catalog_id', '')}")
            else:
                print("  No gaps — all catalog patterns covered!")

        created = learn_result.get('created_lessons', [])
        try:
            if auto_approve and gap_result.get('created'):
                created = created + gap_result['created']
        except NameError:
            pass
        skipped = learn_result.get('skipped_duplicates', 0)
        if skipped:
            print(f"\n  Skipped {skipped} duplicates (already exist in knowledge base)")
        if created:
            print(f"\n  Auto-created {len(created)} lessons:")
            for c in created:
                print(f"    + {c['lesson_id']}: {c['file']}")

            # Step 6: Post-create guardrail — dedup + noise detection
            print("\nStep 6: Post-create guardrail (dedup + noise)...")
            try:
                from learning.dedup import post_create_guardrail
                created_ids = [c['lesson_id'] for c in created]
                guardrail = post_create_guardrail(
                    created_ids=created_ids,
                    scan_path=str(scan_path),
                    auto_merge=True,
                    auto_demote=True,
                    noise_threshold=100,
                )
                print(f"  {guardrail['report']}")

                dedup = guardrail.get('dedup', {})
                noise = guardrail.get('noise', {})
                total_issues = (len(dedup.get('merged', []))
                                + len(dedup.get('disabled', []))
                                + len(noise.get('demoted', [])))

                if total_issues > 0:
                    # Save JSON report for Claude handoff
                    import json
                    report_path = scan_path / 'reports'
                    report_path.mkdir(exist_ok=True)
                    from datetime import datetime
                    report_file = report_path / f"guardrail_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
                    report_data = {
                        'timestamp': datetime.now().isoformat(),
                        'created_lessons': created_ids,
                        'guardrail': guardrail,
                    }
                    report_file.write_text(json.dumps(report_data, indent=2, ensure_ascii=False), encoding='utf-8')
                    print(f"  Report saved: {report_file.name}")
                    print("  Review: kiwi_agent_consensus or manual check recommended")

            except Exception as e:
                print(f"  [warn] Guardrail failed: {e}")

            print("  Run 'python tools/rebuild_index.py' to update README")
        elif n_sug > 0 and not auto_approve:
            print("\n  Use --auto-approve to auto-create lessons from these suggestions")
    elif not report_only:
        print("\n  (Use --learn to auto-detect new bug patterns from code)")

    print("\n" + "=" * 60)
    blocking = critical + high
    if blocking > 0:
        status = f"FAIL ({critical} CRITICAL, {high} HIGH)"
    elif suggest > 0:
        status = f"PASS ({suggest} SUGGEST — style only)"
    else:
        status = "PASS (clean)"
    print(f"Self-improvement complete! Status: {status}")
    print("=" * 60)
    return blocking


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Kiwi self-improvement: scan, mine, and learn from codebase"
    )
    parser.add_argument("--target", type=str, default=None,
                        help="Path to scan (default: Kiwi's own codebase)")
    parser.add_argument("--platform", type=str, default="python",
                        choices=["python", "wp", "nextjs"],
                        help="Platform filter (default: python)")
    parser.add_argument("--severity", type=str, default="ALL",
                        choices=["CRITICAL", "HIGH", "SUGGEST", "ALL"],
                        help="Severity filter (default: ALL)")
    parser.add_argument("--auto-approve", action="store_true",
                        help="Auto-approve CRITICAL/HIGH suggestions")
    parser.add_argument("--report", action="store_true",
                        help="Report-only mode: show violations, skip mine/approve")
    parser.add_argument("--learn", action="store_true",
                        help="Detect new bug patterns from code and suggest/create lessons")

    args = parser.parse_args()

    violation_count = self_scan_and_learn(
        target=args.target,
        platform=args.platform,
        auto_approve=args.auto_approve,
        report_only=args.report,
        severity=args.severity,
        learn=args.learn,
    )
    sys.exit(1 if violation_count > 0 else 0)