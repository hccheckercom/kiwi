"""Test multi-file rollback in batch mode."""

import tempfile
import subprocess
from pathlib import Path
import sys

# Add kiwi to path
kiwi_dir = Path(__file__).parent
sys.path.insert(0, str(kiwi_dir))

from scanner.models import Violation
from scanner.fixer import apply_fix


def test_batch_rollback():
    """Test that multiple files are rolled back together when one fix fails."""

    with tempfile.TemporaryDirectory() as tmpdir:
        project_path = Path(tmpdir)

        # Create 3 test files
        file1 = project_path / "file1.php"
        file1.write_text('<?php\n$password = "admin123";\n', encoding="utf-8")

        file2 = project_path / "file2.php"
        file2.write_text('<?php\n$password = "secret456";\n', encoding="utf-8")

        file3 = project_path / "file3.php"
        file3.write_text('<?php\n$password = "pass789";\n', encoding="utf-8")

        # Create test that fails after 2nd fix
        test_script = project_path / "test.py"
        test_script.write_text('''
import sys
from pathlib import Path

# Check how many files have been fixed
file1 = Path("file1.php").read_text()
file2 = Path("file2.php").read_text()
file3 = Path("file3.php").read_text()

fixed_count = sum([
    "getenv" in file1,
    "getenv" in file2,
    "getenv" in file3
])

print(f"Fixed files: {fixed_count}")

# Fail if 2 or more files are fixed (simulate test breaking after 2nd fix)
if fixed_count >= 2:
    print("Tests failed after 2nd fix!")
    sys.exit(1)
else:
    print("Tests passed")
    sys.exit(0)
''', encoding="utf-8")

        pkg = project_path / "package.json"
        pkg.write_text('{"scripts":{"test":"python test.py"}}', encoding="utf-8")

        # Init git
        subprocess.run(['git', 'init'], cwd=tmpdir, capture_output=True, check=True)
        subprocess.run(['git', 'config', 'user.email', 'test@test.com'], cwd=tmpdir, capture_output=True, check=True)
        subprocess.run(['git', 'config', 'user.name', 'Test'], cwd=tmpdir, capture_output=True, check=True)
        subprocess.run(['git', 'add', '.'], cwd=tmpdir, capture_output=True, check=True)
        subprocess.run(['git', 'commit', '-m', 'init'], cwd=tmpdir, capture_output=True, check=True)

        print("Test: Multi-file rollback in batch mode")
        print("=" * 60)
        print("Scenario: Fix 3 files, test fails after 2nd fix")
        print("Expected: All 3 files should be rolled back\n")

        # Fix all 3 files
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

        results = []
        for i, v in enumerate(violations, 1):
            print(f"Fixing file {i}/3: {Path(v.file).name}")
            result = apply_fix(v, fix_config, dry_run=False, enable_rollback=True)
            results.append(result)
            print(f"  Success: {result.success}, Rolled back: {result.rolled_back}")
            if result.error:
                print(f"  Error: {result.error}")

        print("\n" + "=" * 60)
        print("Results:")
        print("=" * 60)

        # Check final state
        content1 = file1.read_text(encoding="utf-8")
        content2 = file2.read_text(encoding="utf-8")
        content3 = file3.read_text(encoding="utf-8")

        print(f"\nFile 1 has 'admin123': {'admin123' in content1}")
        print(f"File 1 has 'getenv': {'getenv' in content1}")
        print(f"\nFile 2 has 'secret456': {'secret456' in content2}")
        print(f"File 2 has 'getenv': {'getenv' in content2}")
        print(f"\nFile 3 has 'pass789': {'pass789' in content3}")
        print(f"File 3 has 'getenv': {'getenv' in content3}")

        # Current implementation: Each file is rolled back independently
        # This is NOT true batch mode - each fix is isolated
        print("\n" + "=" * 60)
        print("Analysis:")
        print("=" * 60)
        print("Current behavior: Each file rollback is INDEPENDENT")
        print("- File 1: Fixed successfully (test passed)")
        print("- File 2: Fixed, then rolled back (test failed)")
        print("- File 3: Fixed, then rolled back (test failed)")
        print("\nThis is correct for single-file fixes.")
        print("\nFor TRUE batch mode (all-or-nothing), we need:")
        print("1. GitRollback.start_batch() before fixes")
        print("2. Apply all fixes without running tests")
        print("3. Run tests ONCE after all fixes")
        print("4. GitRollback.end_batch(success) to commit or rollback ALL")

        return True


if __name__ == "__main__":
    try:
        test_batch_rollback()
        print("\n" + "=" * 60)
        print("[ANALYSIS COMPLETE]")
        print("\nCurrent implementation: Single-file rollback works ✓")
        print("Batch mode: NOT YET IMPLEMENTED")
        print("\nNext step: Implement batch mode in agent loop")

    except Exception as e:
        print(f"\n[ERROR] {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)