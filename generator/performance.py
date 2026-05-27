"""Performance Optimization for UI Generator"""

import time
from functools import wraps
from typing import Dict, Any, Callable, List
from pathlib import Path
import json


class PerformanceMonitor:
    """Monitor and optimize generator performance."""

    def __init__(self):
        self.metrics = {}

    def measure(self, func: Callable) -> Callable:
        """Decorator to measure function execution time."""
        @wraps(func)
        def wrapper(*args, **kwargs):
            start = time.time()
            result = func(*args, **kwargs)
            duration = time.time() - start

            func_name = func.__name__
            if func_name not in self.metrics:
                self.metrics[func_name] = []

            self.metrics[func_name].append(duration)
            return result

        return wrapper

    def get_report(self) -> Dict[str, Any]:
        """Get performance report."""
        report = {}

        for func_name, durations in self.metrics.items():
            report[func_name] = {
                "calls": len(durations),
                "total_time": sum(durations),
                "avg_time": sum(durations) / len(durations),
                "min_time": min(durations),
                "max_time": max(durations),
            }

        return report


class TokenCache:
    """Cache extracted design tokens to avoid re-parsing."""

    def __init__(self, cache_dir: str = ".claude/kiwi/generator/.cache", ttl_hours: int = 24):
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.ttl_seconds = ttl_hours * 3600

    def get_cache_key(self, demo_path: str) -> str:
        """Generate cache key from demo path."""
        import hashlib
        return hashlib.sha256(demo_path.encode()).hexdigest()

    def get(self, demo_path: str) -> Dict[str, Any]:
        """Get cached tokens if available and fresh."""
        cache_key = self.get_cache_key(demo_path)
        cache_file = self.cache_dir / f"{cache_key}.json"

        if not cache_file.exists():
            return None

        # Check TTL
        cache_age = time.time() - cache_file.stat().st_mtime
        if cache_age > self.ttl_seconds:
            cache_file.unlink()
            return None

        # Check if cache is fresh (demo files not modified)
        demo_dir = Path(demo_path)
        html_file = demo_dir / "code.html"
        design_file = demo_dir / "DESIGN.md"

        if not html_file.exists():
            return None

        cache_mtime = cache_file.stat().st_mtime
        html_mtime = html_file.stat().st_mtime

        if html_mtime > cache_mtime:
            cache_file.unlink()
            return None

        if design_file.exists() and design_file.stat().st_mtime > cache_mtime:
            cache_file.unlink()
            return None

        # Load cache
        try:
            with open(cache_file, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return None

    def set(self, demo_path: str, tokens: Dict[str, Any]):
        """Cache extracted tokens."""
        cache_key = self.get_cache_key(demo_path)
        cache_file = self.cache_dir / f"{cache_key}.json"

        try:
            with open(cache_file, "w", encoding="utf-8") as f:
                json.dump(tokens, f, indent=2)
        except Exception as e:
            print(f"Warning: Failed to cache tokens: {e}")

    def clear(self):
        """Clear all cached tokens."""
        for cache_file in self.cache_dir.glob("*.json"):
            cache_file.unlink()


class ComponentCache:
    """Cache detected components to avoid re-detection."""

    def __init__(self, cache_dir: str = ".claude/kiwi/generator/.cache", ttl_hours: int = 24):
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.ttl_seconds = ttl_hours * 3600

    def get_cache_key(self, html_content: str) -> str:
        """Generate cache key from HTML content."""
        import hashlib
        return hashlib.sha256(html_content.encode()).hexdigest()

    def get(self, html_content: str) -> List[Dict[str, Any]]:
        """Get cached components if available and fresh."""
        cache_key = self.get_cache_key(html_content)
        cache_file = self.cache_dir / f"comp_{cache_key}.json"

        if not cache_file.exists():
            return None

        # Check TTL
        cache_age = time.time() - cache_file.stat().st_mtime
        if cache_age > self.ttl_seconds:
            cache_file.unlink()
            return None

        try:
            with open(cache_file, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return None

    def set(self, html_content: str, components: List[Dict[str, Any]]):
        """Cache detected components."""
        cache_key = self.get_cache_key(html_content)
        cache_file = self.cache_dir / f"comp_{cache_key}.json"

        try:
            with open(cache_file, "w", encoding="utf-8") as f:
                json.dump(components, f, indent=2)
        except Exception as e:
            print(f"Warning: Failed to cache components: {e}")


class BatchProcessor:
    """Process multiple components in batches for efficiency."""

    def __init__(self, batch_size: int = 10):
        self.batch_size = batch_size

    def process_components(
        self,
        components: List[Dict[str, Any]],
        processor: Callable
    ) -> List[Any]:
        """Process components in batches."""
        results = []

        for i in range(0, len(components), self.batch_size):
            batch = components[i:i + self.batch_size]
            batch_results = [processor(comp) for comp in batch]
            results.extend(batch_results)

        return results


def optimize_html_parsing(html_content: str) -> str:
    """Optimize HTML content for faster parsing."""
    # Remove comments
    import re
    html_content = re.sub(r'<!--.*?-->', '', html_content, flags=re.DOTALL)

    # Remove excessive whitespace
    html_content = re.sub(r'\s+', ' ', html_content)

    return html_content


def format_performance_report(report: Dict[str, Any]) -> str:
    """Format performance report for display."""
    lines = [
        "Performance Report:",
        "",
        f"{'Function':<30} {'Calls':<10} {'Total (s)':<12} {'Avg (s)':<12} {'Min (s)':<12} {'Max (s)':<12}",
        "-" * 90
    ]

    for func_name, metrics in sorted(report.items()):
        lines.append(
            f"{func_name:<30} "
            f"{metrics['calls']:<10} "
            f"{metrics['total_time']:<12.3f} "
            f"{metrics['avg_time']:<12.3f} "
            f"{metrics['min_time']:<12.3f} "
            f"{metrics['max_time']:<12.3f}"
        )

    return "\n".join(lines)