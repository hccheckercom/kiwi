"""Test with verbose logging to trace execution flow."""

import tempfile
import subprocess
from pathlib import Path
import sys
import os

# Add kiwi to path
kiwi_dir = Path(__file__).parent
sys.path.insert(0, str(kiwi_dir))

# Monkey-patch fixer to add debug logging
import scanner.fixer as fixer_module

original_apply_fix = fixer_module.apply_fix

def debug_apply_fix(violation, fix_config, dry_run=True, enable_rollback=True):
    print(f"\n[DEBUG] apply_fix called:")
    print(f"  dry_run={dry_run}")
    print(f"  enable_rollback={enable_rollback}")
    print(f"  file={violation.file}")

    # Patch verify_fix_safety to log
    try:
        from rollback import git_rollback
        original_verify = git_rollback.verify_fix_safety

        def debug_verify(*args, **kwargs):
            result = original_verify(*args, **kwargs)
            print(f"[DEBUG] verify_fix_safety: {result}")
            return result

        git_rollback.verify_fix_safety = debug_verify
    except (ImportError, AttributeError):
        pass

    # Patch TestVerifier to log
    try:
        from rollback import test_verifier
        original_init = test_verifier.TestVerifier.__init__
        original_detect = test_verifier.TestVerifier.detect_test_command
        original_run = test_verifier.TestVerifier.run_tests

        def debug_init(self, project_path):
            print(f"[DEBUG] TestVerifier.__init__: project_path={project_path}")
            return original_init(self, project_path)

        def debug_detect(self):
            result = original_detect(self)
            print(f"[DEBUG] detect_test_command: {result}")
            return result

        def debug_run(self, test_command=None, timeout=300):
            print(f"[DEBUG] run_tests: command={test_command}")
            result = original_run(self, test_command, timeout)
            print(f"[DEBUG] run_tests result: success={result.success}, exit_code={result.exit_code}")
            return result

        test_verifier.TestVerifier.__init__ = debug_init
        test_verifier.TestVerifier.detect_test_command = debug_detect
        test_verifier.TestVerifier.run_tests = debug_run
    except Exception as e:
        print(f"[DEBUG] Failed to patch TestVerifier: {e}")

    result = original_apply_fix(violation, fix_config, dry_run, enable_rollback)

    print(f"[DEBUG] apply_fix result:")
    print(f"  success={result.success}")
    print(f"  rolled_back={result.rolled_back}")
    print(f"  error={result.error}")

    return result

fixer_module.apply_fix = debug_apply_fix

from scanner.models import Violation
from scanner.fixer import apply_fix


def test_with_verbose_logging():
    """Test with full debug logging."""

    with tempfile.TemporaryDirectory() as tmpdir:
        project_path = Path(tmpdir)

        print(f"Project path: {project_path}")

        # Create test file
        test_file = project_path / "test.php"
        test_file.write_text('<?php\n$password = "admin123";\n', encoding="utf-8")

        # Create failing test
        test_script = project_path / "test.py"
        test_script.write_text('import sys\nprint("Test running")\nsys.exit(1)\n', encoding="utf-8")

        pkg = project_path / "package.json"
        pkg.write_text('{"scripts":{"test":"python test.py"}}', encoding="utf-8")

        # Init git
        subprocess.run(['git', 'init'], cwd=tmpdir, capture_output=True, check=True)
        subprocess.run(['git', 'config', 'user.email', 'test@test.com'], cwd=tmpdir, capture_output=True, check=True)
        subprocess.run(['git', 'config', 'user.name', 'Test'], cwd=tmpdir, capture_output=True, check=True)
        subprocess.run(['git', 'add', '.'], cwd=tmpdir, capture_output=True, check=True)
        subprocess.run(['git', 'commit', '-m', 'init'], cwd=tmpdir, capture_output=True, check=True)

        print(f"\nFiles created:")
        print(f"  {test_file.exists()} - test.php")
        print(f"  {test_script.exists()} - test.py")
        print(f"  {pkg.exists()} - package.json")
        print(f"  {(project_path / '.git').exists()} - .git")

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

        print("\n" + "="*60)
        print("Applying fix with rollback enabled...")
        print("="*60)

        result = apply_fix(violation, fix_config, dry_run=False, enable_rollback=True)

        print("\n" + "="*60)
        print("Final result:")
        print("="*60)
        print(f"Success: {result.success}")
        print(f"Rolled back: {result.rolled_back}")
        print(f"Error: {result.error}")

        content = test_file.read_text(encoding="utf-8")
        print(f"\nFile content:")
        print(content)


if __name__ == "__main__":
    test_with_verbose_logging()