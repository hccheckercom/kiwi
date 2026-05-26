"""Test verification after fix - run tests to ensure fix doesn't break anything."""

import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Tuple


@dataclass
class TestResult:
    """Result of running tests after fix."""
    success: bool
    output: str
    exit_code: int
    tests_run: int = 0
    tests_failed: int = 0


class TestVerifier:
    """Verify fixes by running tests."""

    def __init__(self, project_path: str):
        self.project_path = Path(project_path)

    def detect_test_command(self) -> Optional[str]:
        """
        Auto-detect test command from project structure.

        Returns:
            Test command or None if no tests found
        """
        # Check for common test configurations
        if (self.project_path / "package.json").exists():
            # Node.js project
            return "npm test"

        if (self.project_path / "composer.json").exists():
            # PHP project with Composer
            composer_json = (self.project_path / "composer.json").read_text(encoding="utf-8")
            if "phpunit" in composer_json.lower():
                return "vendor/bin/phpunit"

        if (self.project_path / "pytest.ini").exists() or (self.project_path / "setup.py").exists():
            # Python project
            return "pytest"

        if (self.project_path / "Makefile").exists():
            # Check if Makefile has test target
            makefile = (self.project_path / "Makefile").read_text(encoding="utf-8")
            if "test:" in makefile:
                return "make test"

        return None

    def run_tests(
        self,
        test_command: Optional[str] = None,
        timeout: int = 300
    ) -> TestResult:
        """
        Run tests to verify fix.

        Args:
            test_command: Custom test command (auto-detected if None)
            timeout: Test timeout in seconds

        Returns:
            TestResult with success status and output
        """
        if test_command is None:
            test_command = self.detect_test_command()

        if test_command is None:
            return TestResult(
                success=True,  # No tests = assume safe
                output="No test command found - skipping verification",
                exit_code=0
            )

        try:
            result = subprocess.run(
                test_command.split(),
                cwd=self.project_path,
                capture_output=True,
                text=True,
                timeout=timeout
            )

            # Parse test output for counts
            tests_run, tests_failed = self._parse_test_output(result.stdout + result.stderr)

            return TestResult(
                success=result.returncode == 0,
                output=result.stdout + result.stderr,
                exit_code=result.returncode,
                tests_run=tests_run,
                tests_failed=tests_failed
            )

        except subprocess.TimeoutExpired:
            return TestResult(
                success=False,
                output=f"Tests timed out after {timeout}s",
                exit_code=-1
            )
        except Exception as e:
            return TestResult(
                success=False,
                output=f"Test execution error: {e}",
                exit_code=-1
            )

    def _parse_test_output(self, output: str) -> Tuple[int, int]:
        """
        Parse test output to extract test counts.

        Args:
            output: Test command output

        Returns:
            (tests_run, tests_failed) tuple
        """
        tests_run = 0
        tests_failed = 0

        # PHPUnit format: "Tests: 42, Assertions: 100, Failures: 2"
        if "Tests:" in output:
            import re
            match = re.search(r"Tests:\s*(\d+)", output)
            if match:
                tests_run = int(match.group(1))
            match = re.search(r"Failures:\s*(\d+)", output)
            if match:
                tests_failed = int(match.group(1))

        # Jest/npm test format: "Tests: 5 failed, 42 passed, 47 total"
        elif "passed" in output.lower():
            import re
            match = re.search(r"(\d+)\s+passed", output)
            if match:
                tests_run = int(match.group(1))
            match = re.search(r"(\d+)\s+failed", output)
            if match:
                tests_failed = int(match.group(1))
                tests_run += tests_failed

        # Pytest format: "42 passed, 2 failed in 5.23s"
        elif "pytest" in output.lower():
            import re
            match = re.search(r"(\d+)\s+passed", output)
            if match:
                tests_run = int(match.group(1))
            match = re.search(r"(\d+)\s+failed", output)
            if match:
                tests_failed = int(match.group(1))
                tests_run += tests_failed

        return tests_run, tests_failed

    def verify_fix_safe(
        self,
        file_path: str,
        test_command: Optional[str] = None
    ) -> Tuple[bool, str]:
        """
        Verify fix is safe by running tests.

        Args:
            file_path: Path to fixed file
            test_command: Optional custom test command

        Returns:
            (is_safe, reason) tuple
        """
        result = self.run_tests(test_command)

        if not result.success:
            if result.tests_failed > 0:
                return False, f"{result.tests_failed} test(s) failed after fix"
            else:
                return False, f"Tests failed with exit code {result.exit_code}"

        return True, f"All tests passed ({result.tests_run} tests)"