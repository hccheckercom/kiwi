"""Simple test to verify rollback integration works."""

import tempfile
import subprocess
from pathlib import Path
import sys

# Add kiwi to path
kiwi_dir = Path(__file__).parent
sys.path.insert(0, str(kiwi_dir))

from scanner.models import Violation
from scanner.fixer import apply_fix


def test_rollback_integration():
    """Test that rollback is triggered when tests fail."""

    with tempfile.TemporaryDirectory() as tmpdir:
        project_path = Path(tmpdir)

        # Create test file
        test_file = project_path / "test.php"
        test_file.write_text('<?php\n$password = "admin123";\n', encoding="utf-8")

        # Create failing test
        test_script = project_path / "test.sh"
        test_script.write_text('#!/bin/bash\nexit 1\n', encoding="utf-8")

        # Create package.json
        pkg = project_path / "package.json"
        pkg.write_text('{"scripts":{"test":"bash test.sh"}}', encoding="utf-8")

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

        print("Applying fix with rollback enabled...")
        result = apply_fix(violation, fix_config, dry_run=False, enable_rollback=True)

        print(f"Success: {result.success}")
        print(f"Rolled back: {result.rolled_back}")
        print(f"Error: {result.error}")

        # Check file content
        content = test_file.read_text(encoding="utf-8")
        print(f"\nFile content after fix:\n{content}")

        # Verify expectations
        if result.rolled_back:
            print("\n[OK] Rollback was triggered")
            if 'admin123' in content:
                print("[OK] Original content restored")
            else:
                print("[FAIL] Original content NOT restored")
                return False
        else:
            print("\n[FAIL] Rollback was NOT triggered")
            print(f"Expected rolled_back=True, got rolled_back={result.rolled_back}")
            return False

        return True


if __name__ == "__main__":
    try:
        success = test_rollback_integration()
        if success:
            print("\n[SUCCESS] Rollback integration test passed")
        else:
            print("\n[FAIL] Rollback integration test failed")
            sys.exit(1)
    except Exception as e:
        print(f"\n[ERROR] {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)