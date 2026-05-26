#!/usr/bin/env python3
"""Quick test script for impact analyzer"""

import sys
from pathlib import Path

# Add scanner to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from scanner.impact import ImpactAnalyzer

# Test file
test_file = Path(__file__).parent / "test_impact_demo.php"
project_root = Path(__file__).parent.parent.parent

print(f"Testing impact analysis on: {test_file.name}")
print(f"Project root: {project_root}")
print()

analyzer = ImpactAnalyzer(str(project_root))
report = analyzer.analyze_fix_impact(str(test_file))

print(f"Symbols changed: {', '.join(report.symbols_changed)}")
print(f"Affected files: {len(report.affected_files)}")
print(f"Risk level: {report.risk_level}")
print()

if report.affected_files:
    for af in report.affected_files:
        print(f"- {Path(af.path).name}")
        print(f"  Risk: {af.risk}")
        print(f"  Reason: {af.reason}")
        if af.line_numbers:
            print(f"  Lines: {af.line_numbers[:5]}")
        print()

print("Suggestions:")
for i, s in enumerate(report.suggestions, 1):
    print(f"{i}. {s}")