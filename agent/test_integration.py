"""Test integration module."""

import sys
from pathlib import Path
import json

sys.path.insert(0, str(Path(__file__).parent.parent))

from memory.db import get_connection, init_db
from agent.integration import KiwiIntegration


def setup_test_data():
    """Create test data for integration testing."""
    init_db()
    conn = get_connection()

    # Create some test lessons with various states
    # Noisy lesson
    conn.execute("""
        INSERT OR REPLACE INTO lesson_confidence
        (lesson_id, total_hits, true_positive_count, false_positive_count,
         fix_success_count, fix_failure_count, confidence, effective_severity, last_hit)
        VALUES ('INT-001', 20, 10, 10, 8, 2, 0.85, 'CRITICAL', datetime('now', '-5 days'))
    """)

    # Stale lesson
    conn.execute("""
        INSERT OR REPLACE INTO lesson_confidence
        (lesson_id, total_hits, true_positive_count, false_positive_count,
         fix_success_count, fix_failure_count, confidence, effective_severity, last_hit)
        VALUES ('INT-002', 15, 12, 3, 10, 2, 0.45, 'HIGH', datetime('now', '-90 days'))
    """)

    # Create some false positives for feedback
    for i in range(12):
        conn.execute("""
            INSERT INTO false_positives
            (lesson_id, file, match_text, reason, dismissed_at, scope, active)
            VALUES ('INT-003', 'test.php', 'code', 'false positive in test', datetime('now'), 'file', 1)
        """)

    conn.execute("""
        INSERT OR REPLACE INTO lesson_confidence
        (lesson_id, total_hits, true_positive_count, false_positive_count,
         fix_success_count, fix_failure_count, confidence, effective_severity)
        VALUES ('INT-003', 20, 8, 12, 5, 3, 0.80, 'HIGH')
    """)

    conn.commit()
    conn.close()


def test_run_maintenance():
    """Test running weekly maintenance."""
    print("Test 1: Run weekly maintenance")

    integration = KiwiIntegration()
    results = integration.run_weekly_maintenance(dry_run=True)

    assert "timestamp" in results
    assert "dry_run" in results
    assert results["dry_run"] == True

    # Check all features ran
    assert "auto_tune" in results
    assert "decay" in results
    assert "correlation" in results
    assert "feedback" in results
    assert "ab_testing" in results
    assert "summary" in results

    print(f"  OK Maintenance ran successfully")
    print(f"  OK Total actions: {results['summary']['total_actions']}")

    if results["summary"]["warnings"]:
        print(f"  OK Warnings: {len(results['summary']['warnings'])}")

    print("  PASS\n")


def test_health_report():
    """Test health report."""
    print("Test 2: Health report")

    integration = KiwiIntegration()
    report = integration.get_health_report()

    # Check all features in report
    assert "auto_tune" in report
    assert "decay" in report
    assert "correlation" in report
    assert "feedback" in report
    assert "ab_testing" in report

    print(f"  OK Health report generated")

    if report["auto_tune"].get("noisy_lessons"):
        print(f"  OK Found {len(report['auto_tune']['noisy_lessons'])} noisy lessons")

    if report["decay"].get("stale_lessons"):
        print(f"  OK Found {len(report['decay']['stale_lessons'])} stale lessons")

    print("  PASS\n")


def test_custom_config():
    """Test custom configuration."""
    print("Test 3: Custom configuration")

    config = {
        "auto_tune": {"min_hits": 5, "enabled": True},
        "decay": {"min_days": 60, "enabled": False},
        "correlation": {"min_correlation": 0.90, "min_co_occurrences": 10, "enabled": True},
        "feedback": {"min_dismissals": 5, "enabled": True},
        "ab_testing": {"auto_finalize": False, "enabled": True}
    }

    integration = KiwiIntegration(config)

    assert integration.config["auto_tune"]["min_hits"] == 5
    assert integration.config["decay"]["enabled"] == False
    assert integration.config["correlation"]["min_correlation"] == 0.90

    print(f"  OK Custom config loaded")

    # Run with custom config
    results = integration.run_weekly_maintenance(dry_run=True)

    # Decay should be disabled
    assert results["decay"]["enabled"] == False

    print(f"  OK Decay disabled as configured")
    print("  PASS\n")


def test_config_file():
    """Test loading config from file."""
    print("Test 4: Load config from file")

    config_path = Path(__file__).parent / "integration_config.json"

    with open(config_path) as f:
        config = json.load(f)

    integration = KiwiIntegration(config)

    assert integration.config["auto_tune"]["min_hits"] == 10
    assert integration.config["decay"]["min_days"] == 30
    assert integration.config["correlation"]["min_correlation"] == 0.80

    print(f"  OK Config loaded from file")
    print("  PASS\n")


def cleanup_test_data():
    """Clean up test data."""
    conn = get_connection()
    conn.execute("DELETE FROM lesson_confidence WHERE lesson_id LIKE 'INT-%'")
    conn.execute("DELETE FROM false_positives WHERE lesson_id LIKE 'INT-%'")
    conn.commit()
    conn.close()


if __name__ == "__main__":
    print("=" * 60)
    print("Integration Module - Test Suite")
    print("=" * 60 + "\n")

    try:
        setup_test_data()
        test_run_maintenance()
        test_health_report()
        test_custom_config()
        test_config_file()

        print("=" * 60)
        print("ALL TESTS PASSED OK")
        print("=" * 60)

    except AssertionError as e:
        print(f"\nX TEST FAILED: {e}")
        import traceback
        traceback.print_exc()

    finally:
        cleanup_test_data()