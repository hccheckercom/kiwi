"""Simple performance benchmark for Kiwi scanner."""

import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from scanner.cli import scan_theme

def benchmark(path, label):
    """Run single benchmark."""
    print(f"\n{label}")
    print("="*60)

    start = time.time()
    report = scan_theme(path, severity_filter="ALL")
    duration = time.time() - start

    print(f"Duration: {duration:.2f}s")
    print(f"Files: {report.files_scanned}")
    print(f"Patterns: {report.patterns_checked}")
    print(f"Violations: {len(report.violations)}")
    print(f"Throughput: {report.files_scanned/duration:.1f} files/sec")

    return duration, report.files_scanned

if __name__ == "__main__":
    print("\nKiwi Performance Benchmark\n")

    # Test with wezone-plugins
    path = Path(__file__).parent.parent.parent.parent / "wezone-plugins"
    if path.exists():
        benchmark(str(path), "wezone-plugins")
    else:
        print("wezone-plugins not found")
