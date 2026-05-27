"""Performance benchmark for token pipeline.

Measures performance across different token set sizes:
- Small: 50 tokens (typical theme)
- Medium: 150 tokens (large theme)
- Large: 500 tokens (very large theme)

Operations measured:
- Token extraction
- Normalization
- Validation
- Transform pipeline
- Export (single format)
- Export (all 4 formats)
"""

import time
import statistics
from pathlib import Path
from typing import Dict, List, Any
import sys

sys.path.insert(0, str(Path(__file__).parent))

from tokens import normalize_tokens, validate_design_tokens, create_default_pipeline
from exporters import CSSExporter, SCSSExporter, PHPExporter, TailwindExporter


def generate_test_tokens(size: str) -> Dict[str, Any]:
    """Generate test token sets of different sizes."""

    if size == "small":
        # 50 tokens: 20 colors + 10 typography + 15 spacing + 5 borderRadius
        return {
            "colors": {f"color-{i}": f"#{i:06x}" for i in range(20)},
            "typography": {
                f"scale-{i}": {
                    "fontSize": f"{16 + i * 2}px",
                    "lineHeight": "1.5"
                } for i in range(10)
            },
            "spacing": {f"{i}": f"{i * 4}px" for i in range(15)},
            "borderRadius": {f"r-{i}": f"{i * 2}px" for i in range(5)},
        }

    elif size == "medium":
        # 150 tokens: 60 colors + 30 typography + 40 spacing + 20 borderRadius
        return {
            "colors": {f"color-{i}": f"#{i:06x}" for i in range(60)},
            "typography": {
                f"scale-{i}": {
                    "fontSize": f"{16 + i * 2}px",
                    "lineHeight": "1.5"
                } for i in range(30)
            },
            "spacing": {f"{i}": f"{i * 4}px" for i in range(40)},
            "borderRadius": {f"r-{i}": f"{i * 2}px" for i in range(20)},
        }

    else:  # large
        # 500 tokens: 200 colors + 100 typography + 150 spacing + 50 borderRadius
        return {
            "colors": {f"color-{i}": f"#{i:06x}" for i in range(200)},
            "typography": {
                f"scale-{i}": {
                    "fontSize": f"{16 + i * 2}px",
                    "lineHeight": "1.5"
                } for i in range(100)
            },
            "spacing": {f"{i}": f"{i * 4}px" for i in range(150)},
            "borderRadius": {f"r-{i}": f"{i * 2}px" for i in range(50)},
        }


def benchmark_operation(operation_name: str, func, *args, iterations: int = 10) -> Dict[str, float]:
    """Benchmark a single operation."""
    times = []

    for _ in range(iterations):
        start = time.perf_counter()
        func(*args)
        end = time.perf_counter()
        times.append((end - start) * 1000)  # Convert to ms

    return {
        "mean": statistics.mean(times),
        "median": statistics.median(times),
        "stdev": statistics.stdev(times) if len(times) > 1 else 0,
        "min": min(times),
        "max": max(times),
        "p95": sorted(times)[int(len(times) * 0.95)],
    }


def run_benchmark(size: str, iterations: int = 10) -> Dict[str, Any]:
    """Run full benchmark for a given token size."""
    print(f"\nBenchmarking {size} token set ({iterations} iterations)...")

    # Generate test data
    legacy_tokens = generate_test_tokens(size)

    results = {}

    # 1. Normalize
    print(f"  [1/6] Normalizing...")
    results["normalize"] = benchmark_operation(
        "normalize",
        normalize_tokens,
        legacy_tokens,
        iterations=iterations
    )
    tokens = normalize_tokens(legacy_tokens)

    # 2. Validate
    print(f"  [2/6] Validating...")
    results["validate"] = benchmark_operation(
        "validate",
        validate_design_tokens,
        tokens.model_dump(),
        iterations=iterations
    )

    # 3. Transform
    print(f"  [3/6] Transforming...")
    transformer = create_default_pipeline()
    results["transform"] = benchmark_operation(
        "transform",
        transformer.apply,
        tokens,
        iterations=iterations
    )
    transformed = transformer.apply(tokens)

    # 4. Export CSS
    print(f"  [4/6] Exporting CSS...")
    css_exporter = CSSExporter()
    results["export_css"] = benchmark_operation(
        "export_css",
        css_exporter.export,
        transformed,
        iterations=iterations
    )

    # 5. Export SCSS
    print(f"  [5/6] Exporting SCSS...")
    scss_exporter = SCSSExporter()
    results["export_scss"] = benchmark_operation(
        "export_scss",
        scss_exporter.export,
        transformed,
        iterations=iterations
    )

    # 6. Export PHP
    print(f"  [6/6] Exporting PHP...")
    php_exporter = PHPExporter()
    results["export_php"] = benchmark_operation(
        "export_php",
        php_exporter.export,
        transformed,
        iterations=iterations
    )

    # 7. Export Tailwind
    tailwind_exporter = TailwindExporter()
    results["export_tailwind"] = benchmark_operation(
        "export_tailwind",
        tailwind_exporter.export,
        transformed,
        iterations=iterations
    )

    # Calculate totals
    results["export_all"] = {
        "mean": sum([
            results["export_css"]["mean"],
            results["export_scss"]["mean"],
            results["export_php"]["mean"],
            results["export_tailwind"]["mean"],
        ])
    }

    results["total"] = {
        "mean": sum([
            results["normalize"]["mean"],
            results["validate"]["mean"],
            results["transform"]["mean"],
            results["export_all"]["mean"],
        ])
    }

    return results


def format_results(results: Dict[str, Dict[str, Any]]) -> str:
    """Format benchmark results as table."""
    lines = []
    lines.append("\n" + "=" * 80)
    lines.append("Token Pipeline Performance Benchmark")
    lines.append("=" * 80)

    for size in ["small", "medium", "large"]:
        if size not in results:
            continue

        size_results = results[size]
        token_count = {
            "small": 50,
            "medium": 150,
            "large": 500,
        }[size]

        lines.append(f"\n{size.upper()} ({token_count} tokens)")
        lines.append("-" * 80)
        lines.append(f"{'Operation':<20} {'Mean':<10} {'Median':<10} {'P95':<10} {'Min':<10} {'Max':<10}")
        lines.append("-" * 80)

        for op in ["normalize", "validate", "transform", "export_css", "export_scss", "export_php", "export_tailwind", "export_all", "total"]:
            if op not in size_results:
                continue

            stats = size_results[op]
            lines.append(
                f"{op:<20} "
                f"{stats['mean']:>8.2f}ms "
                f"{stats.get('median', 0):>8.2f}ms "
                f"{stats.get('p95', 0):>8.2f}ms "
                f"{stats.get('min', 0):>8.2f}ms "
                f"{stats.get('max', 0):>8.2f}ms"
            )

    lines.append("\n" + "=" * 80)
    lines.append("Summary")
    lines.append("=" * 80)

    # Compare sizes
    if "small" in results and "large" in results:
        small_total = results["small"]["total"]["mean"]
        large_total = results["large"]["total"]["mean"]
        scale_factor = large_total / small_total

        lines.append(f"\nScaling (small -> large):")
        lines.append(f"  Token count: 50 -> 500 (10x)")
        lines.append(f"  Total time: {small_total:.2f}ms -> {large_total:.2f}ms ({scale_factor:.2f}x)")
        lines.append(f"  Efficiency: {'Linear' if scale_factor < 12 else 'Sub-linear' if scale_factor < 10 else 'Super-linear'}")

    # Bottleneck analysis
    if "medium" in results:
        medium = results["medium"]
        total = medium["total"]["mean"]

        lines.append(f"\nBottleneck Analysis (medium size):")
        for op in ["normalize", "validate", "transform", "export_all"]:
            if op in medium:
                pct = (medium[op]["mean"] / total) * 100
                lines.append(f"  {op:<15} {medium[op]['mean']:>6.2f}ms ({pct:>5.1f}%)")

    lines.append("\n" + "=" * 80)

    return "\n".join(lines)


def main():
    """Run benchmark suite."""
    print("Token Pipeline Performance Benchmark")
    print("=" * 80)
    print("\nThis will measure performance across 3 token set sizes:")
    print("  - Small: 50 tokens (typical theme)")
    print("  - Medium: 150 tokens (large theme)")
    print("  - Large: 500 tokens (very large theme)")
    print("\nEach operation will be run 10 times to get statistical measures.")

    results = {}

    for size in ["small", "medium", "large"]:
        results[size] = run_benchmark(size, iterations=10)

    # Print results
    output = format_results(results)
    print(output)

    # Save to file
    output_file = Path(__file__).parent / "BENCHMARK-RESULTS.md"
    output_file.write_text(output, encoding="utf-8")
    print(f"\nResults saved to: {output_file}")


if __name__ == "__main__":
    main()
