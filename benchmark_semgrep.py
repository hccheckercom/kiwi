#!/usr/bin/env python3
"""Benchmark: Regex scanner vs Semgrep scanner."""

import time
import subprocess
import json
from pathlib import Path

def benchmark_regex_scanner(theme_path: str) -> dict:
    """Benchmark current regex scanner."""
    start = time.time()
    result = subprocess.run(
        ["python", "-m", "scanner.cli", "--theme", theme_path, "--severity", "CRITICAL", "--json"],
        capture_output=True,
        text=True,
        cwd=".claude/kiwi",
        timeout=120
    )
    elapsed = time.time() - start

    try:
        data = json.loads(result.stdout)
        return {
            "time": elapsed,
            "violations": len(data.get("violations", [])),
            "files_scanned": data.get("files_scanned", 0),
            "patterns_checked": data.get("patterns_checked", 0)
        }
    except json.JSONDecodeError:
        return {
            "time": elapsed,
            "violations": 0,
            "files_scanned": 0,
            "patterns_checked": 0,
            "error": "Failed to parse JSON output"
        }

def benchmark_semgrep(files: list, rule_path: str) -> dict:
    """Benchmark Semgrep scanner."""
    start = time.time()
    result = subprocess.run(
        ["semgrep", "--config", rule_path, "--json", *files],
        capture_output=True,
        text=True,
        timeout=120
    )
    elapsed = time.time() - start

    try:
        data = json.loads(result.stdout)
        return {
            "time": elapsed,
            "violations": len(data.get("results", [])),
            "files_scanned": len(files)
        }
    except json.JSONDecodeError:
        return {
            "time": elapsed,
            "violations": 0,
            "files_scanned": len(files),
            "error": "Failed to parse JSON output"
        }

def main():
    theme_path = "../../themes/kiwi-generator"

    print("=" * 60)
    print("BENCHMARK: Regex Scanner vs Semgrep")
    print("=" * 60)

    # Benchmark 1: Regex scanner (full theme)
    print("\n[1/2] Benchmarking Regex Scanner...")
    regex_result = benchmark_regex_scanner(theme_path)
    print(f"  Time: {regex_result['time']:.2f}s")
    print(f"  Violations: {regex_result['violations']}")
    print(f"  Files scanned: {regex_result['files_scanned']}")
    print(f"  Patterns checked: {regex_result['patterns_checked']}")

    # Benchmark 2: Semgrep (single rule, 10 files)
    print("\n[2/2] Benchmarking Semgrep (single rule, 10 files)...")
    test_files = [
        "../../themes/kiwi-generator/inc/helpers.php",
        "../../themes/kiwi-generator/inc/security.php",
        "../../themes/kiwi-generator/inc/setup.php",
        "../../themes/kiwi-generator/inc/seo.php",
        "../../themes/kiwi-generator/inc/cart.php",
        "../../themes/kiwi-generator/header.php",
        "../../themes/kiwi-generator/footer.php",
        "../../themes/kiwi-generator/index.php",
        "../../themes/kiwi-generator/functions.php",
        "../../themes/kiwi-generator/style.css"
    ]

    # Filter existing files
    existing_files = [f for f in test_files if Path(f).exists()]

    semgrep_result = benchmark_semgrep(existing_files, "semgrep_test_cross_check.yaml")
    print(f"  Time: {semgrep_result['time']:.2f}s")
    print(f"  Violations: {semgrep_result['violations']}")
    print(f"  Files scanned: {semgrep_result['files_scanned']}")

    # Comparison
    print("\n" + "=" * 60)
    print("COMPARISON")
    print("=" * 60)

    if regex_result['files_scanned'] > 0:
        regex_per_file = regex_result['time'] / regex_result['files_scanned']
        print(f"Regex scanner: {regex_per_file:.3f}s per file")

    if semgrep_result['files_scanned'] > 0:
        semgrep_per_file = semgrep_result['time'] / semgrep_result['files_scanned']
        print(f"Semgrep: {semgrep_per_file:.3f}s per file")

        if regex_result['files_scanned'] > 0:
            speedup = regex_per_file / semgrep_per_file
            print(f"\nSpeedup: {speedup:.1f}x {'faster' if speedup > 1 else 'slower'}")

    print("\n" + "=" * 60)

if __name__ == "__main__":
    main()
