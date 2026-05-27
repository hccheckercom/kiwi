"""Performance benchmark suite for Kiwi scanner."""

import time
import os
import sys
from pathlib import Path
from typing import Dict, List, Tuple

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from scanner.cli import scan_theme
from scanner import cache as cache_module


class PerformanceBenchmark:
    """Benchmark scanner performance across different scenarios."""

    def __init__(self, theme_path: str, lessons_dir: str = None):
        self.theme_path = os.path.abspath(theme_path)
        self.lessons_dir = lessons_dir or str(Path(__file__).parent.parent / "lessons")
        self.results: List[Dict] = []

    def benchmark_cold_cache(self, severity: str = "CRITICAL") -> Dict:
        """Benchmark scan with cold cache (no cached results)."""
        # Clear cache
        cache_module.clear_cache(older_than_days=0)

        start = time.time()
        report = scan_theme(
            self.theme_path,
            severity_filter=severity,
            lessons_dir=self.lessons_dir,
            use_cache=True
        )
        elapsed = time.time() - start

        return {
            "scenario": "cold_cache",
            "severity": severity,
            "time_seconds": round(elapsed, 2),
            "files_scanned": report.files_scanned,
            "patterns_checked": report.patterns_checked,
            "violations": len(report.violations),
            "cache_hits": 0,
            "cache_misses": report.files_scanned
        }

    def benchmark_warm_cache(self, severity: str = "CRITICAL") -> Dict:
        """Benchmark scan with warm cache (all files cached)."""
        # First scan to populate cache
        scan_theme(
            self.theme_path,
            severity_filter=severity,
            lessons_dir=self.lessons_dir,
            use_cache=True
        )

        # Second scan with warm cache
        start = time.time()
        report = scan_theme(
            self.theme_path,
            severity_filter=severity,
            lessons_dir=self.lessons_dir,
            use_cache=True
        )
        elapsed = time.time() - start

        return {
            "scenario": "warm_cache",
            "severity": severity,
            "time_seconds": round(elapsed, 2),
            "files_scanned": report.files_scanned,
            "patterns_checked": report.patterns_checked,
            "violations": len(report.violations),
            "cache_hits": report.files_scanned,
            "cache_misses": 0
        }

    def benchmark_no_cache(self, severity: str = "CRITICAL") -> Dict:
        """Benchmark scan without cache (baseline)."""
        start = time.time()
        report = scan_theme(
            self.theme_path,
            severity_filter=severity,
            lessons_dir=self.lessons_dir,
            use_cache=False
        )
        elapsed = time.time() - start

        return {
            "scenario": "no_cache",
            "severity": severity,
            "time_seconds": round(elapsed, 2),
            "files_scanned": report.files_scanned,
            "patterns_checked": report.patterns_checked,
            "violations": len(report.violations),
            "cache_hits": 0,
            "cache_misses": 0
        }

    def benchmark_all_severities(self) -> List[Dict]:
        """Benchmark scan across all severity levels."""
        results = []
        for severity in ["CRITICAL", "HIGH", "SUGGEST", "ALL"]:
            # Clear cache for fair comparison
            cache_module.clear_cache(older_than_days=0)

            start = time.time()
            report = scan_theme(
                self.theme_path,
                severity_filter=severity,
                lessons_dir=self.lessons_dir,
                use_cache=False
            )
            elapsed = time.time() - start

            results.append({
                "scenario": "severity_comparison",
                "severity": severity,
                "time_seconds": round(elapsed, 2),
                "files_scanned": report.files_scanned,
                "patterns_checked": report.patterns_checked,
                "violations": len(report.violations)
            })

        return results

    def run_all_benchmarks(self) -> List[Dict]:
        """Run all benchmark scenarios."""
        print(f"Running benchmarks on: {self.theme_path}")
        print("=" * 60)

        # Scenario 1: Cold cache
        print("\n[1/5] Benchmarking cold cache...")
        result = self.benchmark_cold_cache()
        self.results.append(result)
        print(f"  Time: {result['time_seconds']}s | Files: {result['files_scanned']} | Violations: {result['violations']}")

        # Scenario 2: Warm cache
        print("\n[2/5] Benchmarking warm cache...")
        result = self.benchmark_warm_cache()
        self.results.append(result)
        print(f"  Time: {result['time_seconds']}s | Files: {result['files_scanned']} | Violations: {result['violations']}")
        speedup = round(self.results[0]['time_seconds'] / result['time_seconds'], 1)
        print(f"  Speedup: {speedup}x faster than cold cache")

        # Scenario 3: No cache (baseline)
        print("\n[3/5] Benchmarking no cache (baseline)...")
        result = self.benchmark_no_cache()
        self.results.append(result)
        print(f"  Time: {result['time_seconds']}s | Files: {result['files_scanned']} | Violations: {result['violations']}")

        # Scenario 4: All severities
        print("\n[4/5] Benchmarking all severity levels...")
        severity_results = self.benchmark_all_severities()
        self.results.extend(severity_results)
        for r in severity_results:
            print(f"  {r['severity']:8s}: {r['time_seconds']:5.2f}s | Patterns: {r['patterns_checked']:3d} | Violations: {r['violations']:3d}")

        # Scenario 5: Cache statistics
        print("\n[5/5] Cache statistics...")
        cache_module.init_cache_db()
        stats = cache_module.get_cache_stats()
        print(f"  Total entries: {stats.get('total_entries', 0)}")
        print(f"  Unique commits: {stats.get('unique_commits', 0)}")
        print(f"  Last scan: {stats.get('last_scan', 'N/A')}")

        print("\n" + "=" * 60)
        print("Benchmarks complete!")

        return self.results

    def print_summary(self):
        """Print benchmark summary."""
        if not self.results:
            print("No benchmark results available")
            return

        print("\n" + "=" * 60)
        print("BENCHMARK SUMMARY")
        print("=" * 60)

        # Find cold and warm cache results
        cold = next((r for r in self.results if r['scenario'] == 'cold_cache'), None)
        warm = next((r for r in self.results if r['scenario'] == 'warm_cache'), None)
        no_cache = next((r for r in self.results if r['scenario'] == 'no_cache'), None)

        if cold and warm:
            speedup = round(cold['time_seconds'] / warm['time_seconds'], 1)
            improvement = round((1 - warm['time_seconds'] / cold['time_seconds']) * 100, 1)
            print(f"\nCache Performance:")
            print(f"  Cold cache: {cold['time_seconds']}s")
            print(f"  Warm cache: {warm['time_seconds']}s")
            print(f"  Speedup: {speedup}x faster ({improvement}% improvement)")

        if no_cache and cold:
            overhead = round((cold['time_seconds'] - no_cache['time_seconds']) / no_cache['time_seconds'] * 100, 1)
            print(f"\nCache Overhead:")
            print(f"  No cache: {no_cache['time_seconds']}s")
            print(f"  Cold cache: {cold['time_seconds']}s")
            print(f"  Overhead: {overhead}% (acceptable if < 10%)")

        # Severity comparison
        severity_results = [r for r in self.results if r['scenario'] == 'severity_comparison']
        if severity_results:
            print(f"\nSeverity Level Performance:")
            for r in severity_results:
                print(f"  {r['severity']:8s}: {r['time_seconds']:5.2f}s | {r['patterns_checked']:3d} patterns | {r['violations']:3d} violations")

        print("\n" + "=" * 60)


def main():
    """Run benchmarks on default theme."""
    import argparse

    parser = argparse.ArgumentParser(description="Kiwi Performance Benchmarks")
    parser.add_argument("--theme", required=True, help="Path to theme directory")
    parser.add_argument("--lessons", default=None, help="Path to lessons directory")
    parser.add_argument("--output", default=None, help="Output file for results (JSON)")

    args = parser.parse_args()

    if not os.path.isdir(args.theme):
        print(f"Error: Theme directory not found: {args.theme}")
        sys.exit(1)

    benchmark = PerformanceBenchmark(args.theme, args.lessons)
    results = benchmark.run_all_benchmarks()
    benchmark.print_summary()

    if args.output:
        import json
        with open(args.output, 'w') as f:
            json.dump(results, f, indent=2)
        print(f"\nResults saved to: {args.output}")


if __name__ == "__main__":
    main()