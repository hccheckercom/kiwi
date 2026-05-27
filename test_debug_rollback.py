"""Debug test to trace rollback execution flow."""

import tempfile
import subprocess
from pathlib import Path
import sys

# Add kiwi to path
kiwi_dir = Path(__file__).parent
sys.path.insert(0, str(kiwi_dir))

from scanner.models import Violation
from scanner.fixer import apply_fix


def test_with_debug():
    """Test with debug output to trace execution."""

    with tempfile.TemporaryDirectory() as tmpdir:
        project_path = Path(tmpdir)

        # Create test file
        test_file = project_path / "test.php"
        test_file.write_text('<?php\n$password = "admin123";\n', encoding="utf-8")

        # Create failing test
        test_script = project_path / "test.py"
        test_script.write_text('import sys\nprint("Test running...")\nsys.exit(1)\n', encoding="utf-8")

        pkg = project_path / "package.json"
        pkg.write_text('{"scripts":{"test":"python test.py"}}', encoding="utf-8")

        # Init git
        subprocess.run(['git', 'init'], cwd=tmpdir, capture_output=True, check=True)
        subprocess.run(['git', 'config', 'user.email', 'test@test.com'], cwd=tmpdir, capture_output=True, check=True)
        subprocess.run(['git', 'config', 'user.name', 'Test'], cwd=tmpdir, capture_output=True, check=True)
        subprocess.run(['git', 'add', '.'], cwd=tmpdir, capture_output=True, check=True)
        subprocess.run(['git', 'commit', '-m', 'init'], cwd=tmpdir, capture_output=True, check=True)

        print(f"Project path: {project_path}")
        print(f"Test file: {test_file}")
        print(f"Git initialized: {(project_path / '.git').exists()}")

        # Manually test test_verifier
        print("\n1. Testing test_verifier directly:")
        from rollback.test_verifier import TestVerifier
        verifier = TestVerifier(str(project_path))

        cmd = verifier.detect_test_command()
        print(f"   Detected command: {cmd}")

        if cmd:
            result = verifier.run_tests(cmd)
            print(f"   Test success: {result.success}")
            print(f"   Exit code: {result.exit_code}")
            print(f"   Output: {result.output[:100]}")

        # Now test via apply_fix
        print("\n2. Testing via apply_fix:")
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

        # Patch fixer to add debug output
        import scanner.fixer as fixer_module
        original_apply_fix = fixer_module.apply_fix

        def debug_apply_fix(*args, **kwargs):
            print("   apply_fix called")
            print(f"   enable_rollback: {kwargs.get('enable_rollback', True)}")
            result = original_apply_fix(*args, **kwargs)
            print(f"   Result success: {result.success}")
            print(f"   Result rolled_back: {result.rolled_back}")
            print(f"   Result error: {result.error}")
            return result

        fixer_module.apply_fix = debug_apply_fix

        result = apply_fix(violation, fix_config, dry_run=False, enable_rollback=True)

        print(f"\n3. Final result:")
        print(f"   Success: {result.success}")
        print(f"   Rolled back: {result.rolled_back}")
        print(f"   Error: {result.error}")

        content = test_file.read_text(encoding="utf-8")
        print(f"   File has 'admin123': {'admin123' in content}")
        print(f"   File has 'getenv': {'getenv' in content}")


if __name__ == "__main__":
    test_with_debug()