"""
Comprehensive test suite for Kiwi Impact Analysis (Hướng 6)
Tests: call graph parsing, risk scoring, affected files detection, regression prevention
"""

import os
import sys
from pathlib import Path

# Add kiwi to path
KIWI_DIR = Path(__file__).parent.parent
sys.path.insert(0, str(KIWI_DIR))

from scanner.impact import ImpactAnalyzer, ImpactReport, AffectedFile


def test_php_parser():
    """Test PHP function/class extraction"""
    print("Test 1: PHP Parser")

    test_file = KIWI_DIR / "tests" / "test_impact_demo.php"
    analyzer = ImpactAnalyzer(str(KIWI_DIR))

    graph = analyzer._build_call_graph(str(test_file))

    assert "calculate_price" in graph.functions_defined, "Should extract calculate_price function"
    assert "format_currency" in graph.functions_defined, "Should extract format_currency function"
    assert "ProductHelper" in graph.classes_defined, "Should extract ProductHelper class"

    print("  ✓ PHP parser extracts functions and classes correctly")


def test_find_callers():
    """Test finding files that call functions from fixed file"""
    print("\nTest 2: Find Callers")

    test_file = KIWI_DIR / "tests" / "test_impact_demo.php"
    analyzer = ImpactAnalyzer(str(KIWI_DIR))

    symbols = ["calculate_price", "format_currency"]
    callers = analyzer._find_symbol_callers(symbols, exclude=[str(test_file)])

    # Should find test_impact_caller.php and test_impact_caller2.php
    caller_files = [Path(f).name for f in callers.keys()]

    assert "test_impact_caller.php" in caller_files, "Should find test_impact_caller.php"
    assert "test_impact_caller2.php" in caller_files, "Should find test_impact_caller2.php"

    print(f"  ✓ Found {len(callers)} caller files")


def test_risk_scoring():
    """Test risk level calculation"""
    print("\nTest 3: Risk Scoring")

    test_file = KIWI_DIR / "tests" / "test_impact_demo.php"
    analyzer = ImpactAnalyzer(str(KIWI_DIR))

    # Mock affected file with multiple calls
    matches = {"calculate_price": [10, 15, 20], "format_currency": [25]}
    risk = analyzer._calculate_file_risk("test.php", matches, ["calculate_price", "format_currency"])

    assert risk in ["LOW", "MEDIUM", "HIGH"], f"Risk should be valid level, got {risk}"
    assert risk == "MEDIUM" or risk == "HIGH", "Multiple calls should be MEDIUM or HIGH risk"

    print(f"  ✓ Risk scoring works: {risk} for 4 calls to 2 symbols")


def test_impact_report():
    """Test full impact analysis report generation"""
    print("\nTest 4: Impact Report")

    test_file = KIWI_DIR / "tests" / "test_impact_demo.php"
    analyzer = ImpactAnalyzer(str(KIWI_DIR))

    report = analyzer.analyze_fix_impact(str(test_file))

    assert isinstance(report, ImpactReport), "Should return ImpactReport"
    assert len(report.symbols_changed) > 0, "Should detect changed symbols"
    assert report.risk_level in ["LOW", "MEDIUM", "HIGH", "CRITICAL"], "Should have valid risk level"

    print(f"  ✓ Impact report generated: {len(report.symbols_changed)} symbols, {len(report.affected_files)} affected files")


def test_overall_risk_calculation():
    """Test overall risk level from multiple affected files"""
    print("\nTest 5: Overall Risk Calculation")

    analyzer = ImpactAnalyzer(str(KIWI_DIR))

    # Test CRITICAL: 3+ HIGH risk files
    affected = [
        AffectedFile("a.php", "test", "HIGH"),
        AffectedFile("b.php", "test", "HIGH"),
        AffectedFile("c.php", "test", "HIGH"),
    ]
    risk = analyzer._calculate_overall_risk(affected)
    assert risk == "CRITICAL", f"3 HIGH files should be CRITICAL, got {risk}"

    # Test HIGH: 1 HIGH risk file
    affected = [AffectedFile("a.php", "test", "HIGH")]
    risk = analyzer._calculate_overall_risk(affected)
    assert risk == "HIGH", f"1 HIGH file should be HIGH, got {risk}"

    # Test MEDIUM: 2+ MEDIUM risk files
    affected = [
        AffectedFile("a.php", "test", "MEDIUM"),
        AffectedFile("b.php", "test", "MEDIUM"),
    ]
    risk = analyzer._calculate_overall_risk(affected)
    assert risk == "MEDIUM", f"2 MEDIUM files should be MEDIUM, got {risk}"

    print("  ✓ Overall risk calculation correct for all scenarios")


def test_suggestions_generation():
    """Test suggestion generation"""
    print("\nTest 6: Suggestions Generation")

    analyzer = ImpactAnalyzer(str(KIWI_DIR))

    high_risk = [AffectedFile("cart.php", "calls function X", "HIGH", symbols=["calculate_price"])]
    medium_risk = [AffectedFile("order.php", "imports file", "MEDIUM")]

    suggestions = analyzer._generate_suggestions(high_risk + medium_risk, ["calculate_price", "format_currency"])

    assert len(suggestions) > 0, "Should generate suggestions"
    assert any("cart.php" in s for s in suggestions), "Should mention HIGH risk file"

    print(f"  ✓ Generated {len(suggestions)} suggestions")


def run_all_tests():
    """Run all impact analysis tests"""
    print("=" * 60)
    print("Kiwi Impact Analysis Test Suite")
    print("=" * 60)

    try:
        test_php_parser()
        test_find_callers()
        test_risk_scoring()
        test_impact_report()
        test_overall_risk_calculation()
        test_suggestions_generation()

        print("\n" + "=" * 60)
        print("✅ All tests passed!")
        print("=" * 60)
        return True

    except AssertionError as e:
        print(f"\n❌ Test failed: {e}")
        return False
    except Exception as e:
        print(f"\n❌ Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)
