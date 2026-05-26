"""
Proactive Coverage CLI — Scan for coverage gaps and suggest lessons.

Usage:
    python bin/kiwicover.py <path> [--min-coverage 80] [--platform wp]
"""

import sys
import argparse
from pathlib import Path

# Add parent to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from learning.inventory import extract_inventory
from learning.coverage import calculate_coverage, CoverageMatcher
from learning.gaps import detect_gaps


def main():
    parser = argparse.ArgumentParser(description='Proactive Coverage Scanner')
    parser.add_argument('path', help='File or folder to scan')
    parser.add_argument('--min-coverage', type=int, default=80, help='Minimum coverage threshold (default: 80)')
    parser.add_argument('--platform', choices=['wp', 'nextjs'], default='wp', help='Platform (default: wp)')
    parser.add_argument('--show-covered', action='store_true', help='Show covered patterns (default: only gaps)')

    args = parser.parse_args()

    path = Path(args.path)

    if not path.exists():
        print(f"Error: Path not found: {path}")
        sys.exit(1)

    # Collect files
    if path.is_file():
        files = [path]
    else:
        # Scan folder for PHP/JS files
        files = list(path.rglob('*.php'))
        files.extend(path.rglob('*.js'))
        files.extend(path.rglob('*.ts'))
        files.extend(path.rglob('*.jsx'))
        files.extend(path.rglob('*.tsx'))

    if not files:
        print(f"No PHP/JS/TS files found in {path}")
        sys.exit(0)

    print(f"{'='*60}")
    print(f"  PROACTIVE COVERAGE SCANNER")
    print(f"{'='*60}")
    print(f"  Path: {path}")
    print(f"  Files: {len(files)}")
    print(f"  Platform: {args.platform}")
    print(f"  Min coverage: {args.min_coverage}%")
    print(f"{'='*60}\n")

    # Scan all files
    total_patterns = 0
    total_covered = 0
    total_gaps = 0
    critical_gaps = 0
    high_gaps = 0

    all_gaps = []

    for file in files:
        # Extract patterns
        inventory = extract_inventory(str(file))

        if inventory.total_patterns == 0:
            continue

        # Calculate coverage
        coverage = calculate_coverage(inventory, platform=args.platform)

        # Detect gaps
        report = detect_gaps(inventory, platform=args.platform)

        # Aggregate
        total_patterns += coverage.total_patterns
        total_covered += coverage.covered_patterns
        total_gaps += report.total_gaps
        critical_gaps += report.critical_gaps
        high_gaps += report.high_gaps

        # Collect gaps
        for gap in report.gaps:
            all_gaps.append({
                'file': str(file.relative_to(path.parent)),
                'gap': gap
            })

    # Calculate overall coverage
    overall_coverage = (total_covered / total_patterns * 100) if total_patterns > 0 else 0

    # Print summary
    print(f"COVERAGE SUMMARY:")
    print(f"  Total patterns: {total_patterns}")
    print(f"  Covered: {total_covered} ({overall_coverage:.1f}%)")
    print(f"  Gaps: {total_gaps}")
    print(f"    CRITICAL: {critical_gaps}")
    print(f"    HIGH: {high_gaps}")
    print(f"    SUGGEST: {total_gaps - critical_gaps - high_gaps}")
    print()

    # Check threshold
    if overall_coverage < args.min_coverage:
        print(f"[FAIL] Coverage {overall_coverage:.1f}% is below threshold {args.min_coverage}%")
        print()
    else:
        print(f"[PASS] Coverage {overall_coverage:.1f}% meets threshold {args.min_coverage}%")
        print()

    # Print gaps
    if all_gaps:
        print(f"GAPS DETECTED ({len(all_gaps)}):")
        print()

        # Group by severity
        critical = [g for g in all_gaps if g['gap'].severity == 'CRITICAL']
        high = [g for g in all_gaps if g['gap'].severity == 'HIGH']
        suggest = [g for g in all_gaps if g['gap'].severity == 'SUGGEST']

        # Show CRITICAL gaps
        if critical:
            print(f"CRITICAL GAPS ({len(critical)}):")
            for i, item in enumerate(critical[:10], 1):
                gap = item['gap']
                print(f"{i}. {gap.suggested_lesson['title']}")
                print(f"   File: {item['file']}:{gap.pattern.line}")
                print(f"   Code: {gap.pattern.context[:80]}")
                print(f"   Confidence: {gap.confidence:.0%}")
                print()

            if len(critical) > 10:
                print(f"   ... and {len(critical) - 10} more CRITICAL gaps")
                print()

        # Show HIGH gaps (top 5)
        if high:
            print(f"HIGH GAPS ({len(high)}):")
            for i, item in enumerate(high[:5], 1):
                gap = item['gap']
                print(f"{i}. {gap.suggested_lesson['title']}")
                print(f"   File: {item['file']}:{gap.pattern.line}")
                print()

            if len(high) > 5:
                print(f"   ... and {len(high) - 5} more HIGH gaps")
                print()

        # Show SUGGEST count only
        if suggest:
            print(f"SUGGEST GAPS: {len(suggest)} (use --show-covered to see all)")
            print()
    else:
        print("[PASS] No gaps detected — 100% coverage!")
        print()

    # Exit code
    if overall_coverage < args.min_coverage or critical_gaps > 0:
        sys.exit(1)
    else:
        sys.exit(0)


if __name__ == '__main__':
    main()
