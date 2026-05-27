# nosec - test fixtures with hardcoded credentials for testing purposes
"""Simple cross-platform test to verify rollback integration."""

import tempfile
import subprocess
from pathlib import Path
import sys

# Add kiwi to path
kiwi_dir = Path(__file__).parent
sys.path.insert(0, str(kiwi_dir))

from scanner.models import Violation
from scanner.fixer import apply_fix


def test_rollback_on_test_failure():
    """Test that rollback is triggered when tests fail."""

    with tempfile.TemporaryDirectory() as tmpdir:
        project_path = Path(tmpdir)

        # Create test file
        test_file = project_path / "test.php"
        test_file.write_text('<?php\n$password = "admin123";\n', encoding="utf-8")  # nosec

        # Create failing test (Python script - cross-platform)
        test_script = project_path / "test.py"
        test_script.write_text('import sys\nsys.exit(1)  # Always fail\n', encoding="utf-8")

        # Create package.json pointing to Python test
        pkg = project_path / "package.json"
        pkg.write_text('{"scripts":{"test":"python test.py"}}', encoding="utf-8")

        # Init git
        subprocess.run(['git', 'init'], cwd=tmpdir, capture_output=True, check=True)
        subprocess.run(['git', 'config', 'user.email', 'test@test.com'], cwd=tmpdir, capture_output=True, check=True)
        subprocess.run(['git', 'config', 'user.name', 'Test'], cwd=tmpdir, capture_output=True, check=True)
        subprocess.run(['git', 'add', '.'], cwd=tmpdir, capture_output=True, check=True)
        subprocess.run(['git', 'commit', '-m', 'init'], cwd=tmpdir, capture_output=True, check=True)

        # Create violation
        violation = Violation(
            lesson_id="LES-001",
            severity="CRITICAL",
            category="security",
            description="Hardcoded credentials",
            file=str(test_file),
            line=2
        )

        fix_config = {
            "type": "replace",
            "search": r'\$password\s*=\s*"[^"]+";',
            "replace": '$password = getenv("PASSWORD");'
        }

        print("Test 1: Rollback on test failure")
        print("=" * 50)
        result = apply_fix(violation, fix_config, dry_run=False, enable_rollback=True)

        print(f"Success: {result.success}")
        print(f"Rolled back: {result.rolled_back}")
        print(f"Error: {result.error}")

        content = test_file.read_text(encoding="utf-8")

        if result.rolled_back and 'admin123' in content:
            print("[PASS] Rollback triggered and content restored\n")
            return True
        else:
            print(f"[FAIL] Expected rollback=True with original content")
            print(f"Got: rollback={result.rolled_back}, content has admin123={('admin123' in content)}\n")
            return False


def test_no_rollback_on_test_pass():
    """Test that fix is kept when tests pass."""

    with tempfile.TemporaryDirectory() as tmpdir:
        project_path = Path(tmpdir)

        # Create test file
        test_file = project_path / "test.php"
        test_file.write_text('<?php\n$password = "admin123";\n', encoding="utf-8")  # nosec

        # Create passing test
        test_script = project_path / "test.py"
        test_script.write_text('import sys\nsys.exit(0)  # Always pass\n', encoding="utf-8")

        pkg = project_path / "package.json"
        pkg.write_text('{"scripts":{"test":"python test.py"}}', encoding="utf-8")

        # Init git
        subprocess.run(['git', 'init'], cwd=tmpdir, capture_output=True, check=True)
        subprocess.run(['git', 'config', 'user.email', 'test@test.com'], cwd=tmpdir, capture_output=True, check=True)
        subprocess.run(['git', 'config', 'user.name', 'Test'], cwd=tmpdir, capture_output=True, check=True)
        subprocess.run(['git', 'add', '.'], cwd=tmpdir, capture_output=True, check=True)
        subprocess.run(['git', 'commit', '-m', 'init'], cwd=tmpdir, capture_output=True, check=True)

        violation = Violation(
            lesson_id="LES-001",
            severity="CRITICAL",
            category="security",
            description="Hardcoded credentials",
            file=str(test_file),
            line=2
        )

        fix_config = {
            "type": "replace",
            "search": r'\$password\s*=\s*"[^"]+";',
            "replace": '$password = getenv("PASSWORD");'
        }

        print("Test 2: No rollback on test pass")
        print("=" * 50)
        result = apply_fix(violation, fix_config, dry_run=False, enable_rollback=True)

        print(f"Success: {result.success}")
        print(f"Rolled back: {result.rolled_back}")
        print(f"Error: {result.error}")

        content = test_file.read_text(encoding="utf-8")

        if result.success and not result.rolled_back and 'getenv' in content:
            print("[PASS] Fix kept when tests pass\n")
            return True
        else:
            print(f"[FAIL] Expected success=True, rollback=False, fixed content")
            print(f"Got: success={result.success}, rollback={result.rolled_back}, has getenv={('getenv' in content)}\n")
            return False


if __name__ == "__main__":
    print("Running rollback integration tests (cross-platform)\n")

    try:
        test1 = test_rollback_on_test_failure()
        test2 = test_no_rollback_on_test_pass()

        if test1 and test2:
            print("=" * 50)
            print("[SUCCESS] All rollback integration tests passed")
            print("\nVerified:")
            print("  - Test verifier detects test failures")
            print("  - Rollback triggered on test failure")
            print("  - Original content restored after rollback")
            print("  - Fix kept when tests pass")
        else:
            print("=" * 50)
            print("[FAIL] Some tests failed")
            sys.exit(1)

    except Exception as e:
        print(f"\n[ERROR] {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)