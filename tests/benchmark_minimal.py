"""Minimal performance test - no external dependencies."""

import time
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

try:
    from scanner.cli import scan_theme

    # Test with wezone-plugins
    path = Path(__file__).parent.parent.parent.parent / "wezone-plugins"

    if not path.exists():
        print(f"ERROR: Path not found: {path}")
        sys.exit(1)

    print("Minimal Performance Test")
    print("="*60)
    print(f"Path: {path}")

    start = time.time()
    report = scan_theme(str(path), severity_filter="CRITICAL")
    duration = time.time() - start

    print(f"\nResults:")
    print(f"  Duration: {duration:.2f}s")
    print(f"  Files: {report.files_scanned}")
    print(f"  Patterns: {report.patterns_checked}")
    print(f"  Violations: {len(report.violations)}")

    if duration > 0:
        print(f"  Throughput: {report.files_scanned/duration:.1f} files/sec")

    print("\nSUCCESS")

except Exception as e:
    print(f"ERROR: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)