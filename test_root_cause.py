"""Simple test that directly calls test_verifier without npm dependency."""

import tempfile
import subprocess
from pathlib import Path
import sys

# Add kiwi to path
kiwi_dir = Path(__file__).parent
sys.path.insert(0, str(kiwi_dir))

from scanner.models import Violation
from scanner.fixer import apply_fix
from rollback.test_verifier import TestVerifier


def test_rollback_with_direct_test_command():
    """Test rollback by passing test command directly to fixer."""

    with tempfile.TemporaryDirectory() as tmpdir:
        project_path = Path(tmpdir)

        # Create test file
        test_file = project_path / "test.php"
        test_file.write_text('<?php\n$password = "admin123";\n', encoding="utf-8")

        # Create failing test script
        test_script = project_path / "test_fail.py"
        test_script.write_text('import sys\nsys.exit(1)\n', encoding="utf-8")

        # Init git
        subprocess.run(['git', 'init'], cwd=tmpdir, capture_output=True, check=True)
        subprocess.run(['git', 'config', 'user.email', 'test@test.com'], cwd=tmpdir, capture_output=True, check=True)
        subprocess.run(['git', 'config', 'user.name', 'Test'], cwd=tmpdir, capture_output=True, check=True)
        subprocess.run(['git', 'add', '.'], cwd=tmpdir, capture_output=True, check=True)
        subprocess.run(['git', 'commit', '-m', 'init'], cwd=tmpdir, capture_output=True, check=True)

        print("Test 1: Verify test_verifier detects failure")
        print("=" * 50)

        # Test verifier directly
        verifier = TestVerifier(str(project_path))
        test_result = verifier.run_tests(f"python {test_script}")

        print(f"Test command: python {test_script}")
        print(f"Test success: {test_result.success}")
        print(f"Exit code: {test_result.exit_code}")

        if not test_result.success:
            print("[PASS] Test verifier correctly detected failure\n")
        else:
            print("[FAIL] Test verifier should detect failure\n")
            return False

        print("Test 2: Verify rollback integration in fixer")
        print("=" * 50)

        # Now test via fixer - but we need to check if fixer actually calls test_verifier
        # Let's check the fixer code flow

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

        # The issue: fixer uses TestVerifier(project_root) but project_root is calculated as:
        # kiwi_dir.parent.parent which would be wezone/ not our temp dir
        # This is why test verification never runs!

        print(f"Project path: {project_path}")
        print(f"Kiwi dir would calculate project_root as: {Path(__file__).parent.parent.parent}")
        print("\n[ISSUE FOUND] Fixer calculates project_root incorrectly!")
        print("It uses kiwi_dir.parent.parent which points to wezone/, not the actual project being fixed.")
        print("\nThis is why test verification never runs - it's looking for tests in the wrong directory.\n")

        return True


if __name__ == "__main__":
    try:
        test_rollback_with_direct_test_command()
        print("=" * 50)
        print("[ROOT CAUSE IDENTIFIED]")
        print("\nThe problem: fixer.py line 105 calculates project_root as:")
        print("  project_root = kiwi_dir.parent.parent")
        print("\nThis assumes the file being fixed is inside the Kiwi project structure,")
        print("but it should use the directory of the file being fixed instead.")
        print("\nFix needed: Pass project_path to TestVerifier based on violation.file location.")

    except Exception as e:
        print(f"\n[ERROR] {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)