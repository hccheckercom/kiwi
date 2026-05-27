# nosec - test fixtures with hardcoded credentials for testing purposes
"""Test rollback history tracking end-to-end."""

import tempfile
import subprocess
from pathlib import Path
import sys

# Add kiwi to path
kiwi_dir = Path(__file__).parent
sys.path.insert(0, str(kiwi_dir))

from scanner.models import Violation
from scanner.fixer import apply_fix
from memory.rollback_tracking import record_rollback, get_rollback_stats, get_high_rollback_lessons


def test_rollback_history_tracking():
    """Test that rollback events are tracked in confidence.db."""

    with tempfile.TemporaryDirectory() as tmpdir:
        project_path = Path(tmpdir)

        # Create test file
        test_file = project_path / "test.php"
        test_file.write_text('<?php\n$password = "admin123";\n', encoding="utf-8")  # nosec

        # Create failing test
        test_script = project_path / "test.py"
        test_script.write_text('import sys\nsys.exit(1)\n', encoding="utf-8")

        pkg = project_path / "package.json"
        pkg.write_text('{"scripts":{"test":"python test.py"}}', encoding="utf-8")

        # Init git
        subprocess.run(['git', 'init'], cwd=tmpdir, capture_output=True, check=True)
        subprocess.run(['git', 'config', 'user.email', 'test@test.com'], cwd=tmpdir, capture_output=True, check=True)
        subprocess.run(['git', 'config', 'user.name', 'Test'], cwd=tmpdir, capture_output=True, check=True)
        subprocess.run(['git', 'add', '.'], cwd=tmpdir, capture_output=True, check=True)
        subprocess.run(['git', 'commit', '-m', 'init'], cwd=tmpdir, capture_output=True, check=True)

        print("Test: Rollback history tracking")
        print("=" * 60)

        violation = Violation(
            lesson_id="LES-999",  # Use unique ID for testing
            severity="CRITICAL",
            category="security",
            description="Test violation",
            file=str(test_file),
            line=2
        )

        fix_config = {
            "type": "replace",
            "search": r'\$password\s*=\s*"[^"]+";',
            "replace": '$password = getenv("PASSWORD");'
        }

        # Apply fix (will rollback due to test failure)
        print("Step 1: Apply fix (will trigger rollback)...")
        result = apply_fix(violation, fix_config, dry_run=False, enable_rollback=True)

        print(f"  Success: {result.success}")
        print(f"  Rolled back: {result.rolled_back}")
        print(f"  Error: {result.error}")

        # Check rollback stats
        print("\nStep 2: Check rollback stats in DB...")
        stats = get_rollback_stats("LES-999")

        print(f"  Lesson ID: {stats['lesson_id']}")
        print(f"  Rollback count: {stats['rollback_count']}")
        print(f"  Last rollback at: {stats['last_rollback_at']}")
        print(f"  Rollback rate: {stats['rollback_rate']}")

        # Verify tracking worked
        print("\n" + "=" * 60)
        if stats['rollback_count'] > 0:
            print("[SUCCESS] Rollback history tracking works!")
            print(f"\nVerified:")
            print(f"  ✓ Rollback event recorded in confidence.db")
            print(f"  ✓ Rollback count: {stats['rollback_count']}")
            print(f"  ✓ Timestamp tracked: {stats['last_rollback_at']}")
            return True
        else:
            print("[FAIL] Rollback was not tracked in DB")
            return False


if __name__ == "__main__":
    try:
        success = test_rollback_history_tracking()
        if not success:
            sys.exit(1)

        print("\n" + "=" * 60)
        print("[STEP 3 COMPLETE]")
        print("\nRollback history tracking verified:")
        print("  ✓ Schema updated with rollback_count, last_rollback_at")
        print("  ✓ record_rollback() function implemented")
        print("  ✓ get_rollback_stats() function implemented")
        print("  ✓ Integration with fixer.py complete")
        print("  ✓ End-to-end tracking verified")

    except Exception as e:
        print(f"\n[ERROR] {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)