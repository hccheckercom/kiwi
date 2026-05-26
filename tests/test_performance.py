"""
Performance benchmarks for Kiwi scanner.

Tests scan performance with varying file counts and measures:
- Scan duration
- Memory usage
- Patterns checked per second
- Files scanned per second
"""

import os
import sys
import time
import psutil
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))


def get_memory_usage():
    """Get current process memory usage in MB."""
    process = psutil.Process(os.getpid())
    return process.memory_info().rss / 1024 / 1024


def benchmark_scan(path, severity="ALL", label=""):
    """Benchmark a single scan operation."""
    from scanner.cli import scan_theme

    print(f"\n{'='*60}")
    print(f"BENCHMARK: {label}")
    print(f"{'='*60}")

    # Measure memory before
    mem_before = get_memory_usage()

    # Measure scan time
    start = time.time()
    report = scan_theme(path, severity_filter=severity)
    duration = time.time() - start

    # Measure memory after
    mem_after = get_memory_usage()
    mem_delta = mem_after - mem_before

    # Calculate metrics
    files_per_sec = report.files_scanned / duration if duration > 0 else 0
    patterns_per_sec = report.patterns_checked / duration if duration > 0 else 0

    print(f"Duration: {duration:.2f}s")
    print(f"Files scanned: {report.files_scanned}")
    print(f"Patterns checked: {report.patterns_checked}")
    print(f"Violations found: {len(report.violations)}")
    print(f"Files/sec: {files_per_sec:.1f}")
    print(f"Patterns/sec: {patterns_per_sec:.1f}")
    print(f"Memory before: {mem_before:.1f} MB")
    print(f"Memory after: {mem_after:.1f} MB")
    print(f"Memory delta: {mem_delta:.1f} MB")

    return {
        "duration": duration,
        "files_scanned": report.files_scanned,
        "patterns_checked": report.patterns_checked,
        "violations": len(report.violations),
        "files_per_sec": files_per_sec,
        "patterns_per_sec": patterns_per_sec,
        "memory_delta": mem_delta
    }


def benchmark_parallel_vs_sequential():
    """Compare parallel vs sequential scanning performance."""
    print("\n" + "="*60)
    print("PARALLEL vs SEQUENTIAL COMPARISON")
    print("="*60)

    # TODO: Implement parallel executor benchmark
    # This requires parallel executor implementation in scanner
    print("\nParallel executor not yet implemented - skipping comparison")


def main():
    print("\nKiwi Performance Benchmarks\n")

    # Find test projects
    projects_root = Path(__file__).parent.parent.parent.parent

    # Benchmark 1: Small project (< 20 files)
    small_project = projects_root / "themes" / "sfvn"
    if small_project.exists():
        benchmark_scan(str(small_project), label="Small project (< 20 files)")

    # Benchmark 2: Medium project (20-50 files)
    medium_project = projects_root / "wezone-plugins"
    if medium_project.exists():
        benchmark_scan(str(medium_project), label="Medium project (20-50 files)")

    # Benchmark 3: Large project (100+ files)
    # Use webstore-vn if available
    large_project = projects_root / "webstore-vn"
    if large_project.exists():
        benchmark_scan(str(large_project), label="Large project (100+ files)")
    else:
        print("\nLarge project not found - skipping 100+ file benchmark")
        print("To test with 100+ files, ensure webstore-vn project exists")

    # Benchmark 4: Parallel vs Sequential
    benchmark_parallel_vs_sequential()

    print("\n" + "="*60)
    print("BENCHMARKS COMPLETE")
    print("="*60)


if __name__ == "__main__":
    try:
        import psutil
    except ImportError:
        print("ERROR: psutil not installed")
        print("Install with: pip install psutil")
        sys.exit(1)

    main()