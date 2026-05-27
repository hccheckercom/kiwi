"""Test to capture the actual exception."""

import tempfile
import subprocess
from pathlib import Path
import sys
import traceback

# Add kiwi to path
kiwi_dir = Path(__file__).parent
sys.path.insert(0, str(kiwi_dir))

from scanner.models import Violation
from scanner.fixer import apply_fix


def test_capture_exception():
    """Test to see what exception is being raised."""

    with tempfile.TemporaryDirectory() as tmpdir:
        project_path = Path(tmpdir)

        # Create test file
        test_file = project_path / "test.php"
        test_file.write_text('<?php\n$password = "admin123";\n', encoding="utf-8")

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

        # Manually test the flow
        print("Testing rollback flow manually...")

        # Step 1: Create rollback
        from rollback.git_rollback import GitRollback
        rollback = GitRollback(str(project_path))

        checkpoint_created = rollback.create_checkpoint([str(test_file)])
        print(f"Checkpoint created: {checkpoint_created}")

        if not checkpoint_created:
            print("ISSUE: Checkpoint creation failed!")
            print("This is why rollback object is None in fixer.py")
            return

        # Step 2: Apply fix manually
        content = test_file.read_text(encoding="utf-8")
        import re
        new_content = re.sub(r'\$password\s*=\s*"[^"]+";', '$password = getenv("PASSWORD");', content)
        test_file.write_text(new_content, encoding="utf-8")

        print(f"Fix applied, file now has: {test_file.read_text(encoding='utf-8')[:50]}")

        # Step 3: Test verification
        from rollback.test_verifier import TestVerifier
        verifier = TestVerifier(str(project_path))

        test_safe, test_reason = verifier.verify_fix_safe(str(test_file))
        print(f"Test safe: {test_safe}")
        print(f"Test reason: {test_reason}")

        if not test_safe:
            print("\nTests failed, attempting rollback...")
            success, message = rollback.rollback()
            print(f"Rollback success: {success}")
            print(f"Rollback message: {message}")

            content_after = test_file.read_text(encoding="utf-8")
            print(f"Content after rollback: {content_after[:50]}")

            if 'admin123' in content_after:
                print("\n[SUCCESS] Rollback worked!")
            else:
                print("\n[FAIL] Rollback did not restore content")


if __name__ == "__main__":
    try:
        test_capture_exception()
    except Exception as e:
        print(f"\n[EXCEPTION] {e}")
        traceback.print_exc()