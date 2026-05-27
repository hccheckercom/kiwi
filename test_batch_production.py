"""Test batch rollback integration in production scenario."""

import tempfile
import subprocess
from pathlib import Path
import sys

# Add kiwi to path
kiwi_dir = Path(__file__).parent
sys.path.insert(0, str(kiwi_dir))

from scanner.models import Violation
from rollback.batch_rollback import BatchRollback


def test_batch_rollback_production():
    """Test batch rollback in production scenario."""

    with tempfile.TemporaryDirectory() as tmpdir:
        project_path = Path(tmpdir)

        # Create 3 test files
        file1 = project_path / "file1.php"
        file1.write_text('<?php\n$password = "admin123";\n', encoding="utf-8")

        file2 = project_path / "file2.php"
        file2.write_text('<?php\n$password = "secret456";\n', encoding="utf-8")

        file3 = project_path / "file3.php"
        file3.write_text('<?php\n$password = "pass789";\n', encoding="utf-8")

        # Create test that fails after all fixes
        test_script = project_path / "test.py"
        test_script.write_text('import sys\nprint("Tests failed!")\nsys.exit(1)\n', encoding="utf-8")

        pkg = project_path / "package.json"
        pkg.write_text('{"scripts":{"test":"python test.py"}}', encoding="utf-8")

        # Init git
        subprocess.run(['git', 'init'], cwd=tmpdir, capture_output=True, check=True)
        subprocess.run(['git', 'config', 'user.email', 'test@test.com'], cwd=tmpdir, capture_output=True, check=True)
        subprocess.run(['git', 'config', 'user.name', 'Test'], cwd=tmpdir, capture_output=True, check=True)
        subprocess.run(['git', 'add', '.'], cwd=tmpdir, capture_output=True, check=True)
        subprocess.run(['git', 'commit', '-m', 'init'], cwd=tmpdir, capture_output=True, check=True)

        print("Test: Batch rollback production scenario")
        print("=" * 60)
        print("Scenario: Fix 3 files, run tests ONCE, rollback ALL if fail\n")

        # Create batch rollback manager
        batch = BatchRollback(str(project_path))

        violations = [
            Violation(
                lesson_id="LES-001",
                severity="CRITICAL",
                category="security",
                description="Hardcoded credentials",
                file=str(file1),
                line=2
            ),
            Violation(
                lesson_id="LES-001",
                severity="CRITICAL",
                category="security",
                description="Hardcoded credentials",
                file=str(file2),
                line=2
            ),
            Violation(
                lesson_id="LES-001",
                severity="CRITICAL",
                category="security",
                description="Hardcoded credentials",
                file=str(file3),
                line=2
            ),
        ]

        fix_config = {
            "type": "replace",
            "search": r'\$password\s*=\s*"[^"]+";',
            "replace": '$password = getenv("PASSWORD");'
        }

        # Step 1: Apply all fixes without testing
        print("Step 1: Applying all fixes...")
        for i, v in enumerate(violations, 1):
            result = batch.apply_fix_batch(v, fix_config, dry_run=False)
            print(f"  File {i}: {result.success}")

        # Check intermediate state
        print("\nIntermediate state (after fixes, before tests):")
        print(f"  File 1 has 'getenv': {'getenv' in file1.read_text(encoding='utf-8')}")
        print(f"  File 2 has 'getenv': {'getenv' in file2.read_text(encoding='utf-8')}")
        print(f"  File 3 has 'getenv': {'getenv' in file3.read_text(encoding='utf-8')}")

        # Step 2: Run tests once and rollback all if fail
        print("\nStep 2: Running tests once for all fixes...")
        success, message = batch.verify_and_commit()
        print(f"  Result: {message}")

        # Check final state
        print("\nFinal state (after rollback):")
        content1 = file1.read_text(encoding="utf-8")
        content2 = file2.read_text(encoding="utf-8")
        content3 = file3.read_text(encoding="utf-8")

        print(f"  File 1 has 'admin123': {'admin123' in content1}")
        print(f"  File 2 has 'secret456': {'secret456' in content2}")
        print(f"  File 3 has 'pass789': {'pass789' in content3}")

        # Verify all files rolled back
        all_rolled_back = (
            'admin123' in content1 and
            'secret456' in content2 and
            'pass789' in content3
        )

        print("\n" + "=" * 60)
        if all_rolled_back:
            print("[SUCCESS] Batch rollback works correctly!")
            print("All 3 files were rolled back after test failure")
            return True
        else:
            print("[FAIL] Batch rollback did not restore all files")
            return False


if __name__ == "__main__":
    try:
        success = test_batch_rollback_production()
        if success:
            print("\n" + "=" * 60)
            print("[PRODUCTION TEST PASSED]")
            print("\nBatch rollback verified:")
            print("  ✓ Apply multiple fixes without testing")
            print("  ✓ Run tests once after all fixes")
            print("  ✓ Rollback all files on test failure")
            print("  ✓ All-or-nothing guarantee maintained")
        else:
            sys.exit(1)

    except Exception as e:
        print(f"\n[ERROR] {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)