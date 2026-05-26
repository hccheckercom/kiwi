# Kiwi Performance Benchmarking

## Overview

Performance benchmarking infrastructure for Kiwi scanner to measure:
- Scan duration
- Memory usage
- Throughput (files/sec, patterns/sec)
- Scalability with large projects (100+ files)

## Benchmark Scripts

### test_performance.py
Full benchmark suite with memory profiling using psutil.

**Features:**
- Memory usage tracking (before/after/delta)
- Multiple project sizes (small < 20, medium 20-50, large 100+)
- Throughput metrics (files/sec, patterns/sec)
- Parallel vs sequential comparison (TODO)

**Requirements:**
```bash
pip install psutil
```

**Usage:**
```bash
cd .claude/kiwi
python tests/test_performance.py
```

### benchmark_simple.py
Lightweight benchmark without external dependencies.

**Usage:**
```bash
cd .claude/kiwi
python tests/benchmark_simple.py
```

## Expected Performance Targets

Based on handoff requirements:

| Project Size | Files | Target Duration | Target Throughput |
|--------------|-------|-----------------|-------------------|
| Small        | < 20  | < 2s            | > 10 files/sec    |
| Medium       | 20-50 | < 5s            | > 10 files/sec    |
| Large        | 100+  | < 15s           | > 7 files/sec     |

## Next Steps

1. Run benchmarks on actual projects (wezone-plugins, webstore-vn)
2. Profile memory usage with large projects
3. Implement parallel executor for 100+ file projects
4. Optimize bottlenecks identified in profiling
5. Add benchmark results to CI/CD pipeline

## Notes

- Parallel executor not yet implemented - sequential scanning only
- Memory profiling requires psutil package
- Benchmark results vary based on:
  - Number of patterns loaded
  - File sizes
  - Disk I/O speed
  - CPU cores available
