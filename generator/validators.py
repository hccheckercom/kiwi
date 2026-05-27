"""PHP Syntax Validation for Generated Files"""

import subprocess
from pathlib import Path
from typing import Dict, Any, List, Tuple


class PHPValidator:
    """Validate PHP syntax of generated files."""

    def __init__(self, php_binary: str = "php"):
        self.php_binary = php_binary

    def validate_file(self, file_path: str) -> Tuple[bool, str]:
        """
        Validate PHP syntax of a file.

        Args:
            file_path: Path to PHP file

        Returns:
            (is_valid, error_message)
        """
        try:
            result = subprocess.run(
                [self.php_binary, "-l", file_path],
                capture_output=True,
                text=True,
                timeout=5
            )

            if result.returncode == 0:
                return True, ""
            else:
                return False, result.stderr or result.stdout

        except FileNotFoundError:
            return False, f"PHP binary not found: {self.php_binary}"
        except subprocess.TimeoutExpired:
            return False, "PHP validation timed out"
        except Exception as e:
            return False, f"Validation failed: {e}"

    def validate_content(self, php_content: str) -> Tuple[bool, str]:
        """
        Validate PHP syntax of content string.

        Args:
            php_content: PHP code as string

        Returns:
            (is_valid, error_message)
        """
        import tempfile

        # Write to temp file
        with tempfile.NamedTemporaryFile(mode="w", suffix=".php", delete=False, encoding="utf-8") as f:
            f.write(php_content)
            temp_path = f.name

        try:
            return self.validate_file(temp_path)
        finally:
            Path(temp_path).unlink(missing_ok=True)

    def validate_batch(self, file_paths: List[str]) -> Dict[str, Tuple[bool, str]]:
        """
        Validate multiple PHP files.

        Args:
            file_paths: List of PHP file paths

        Returns:
            Dict mapping file_path to (is_valid, error_message)
        """
        results = {}

        for file_path in file_paths:
            results[file_path] = self.validate_file(file_path)

        return results


def format_validation_report(results: Dict[str, Tuple[bool, str]]) -> str:
    """Format PHP validation report."""
    lines = ["PHP Syntax Validation Report:", ""]

    valid_count = sum(1 for is_valid, _ in results.values() if is_valid)
    invalid_count = len(results) - valid_count

    lines.append(f"Total files: {len(results)}")
    lines.append(f"Valid: {valid_count}")
    lines.append(f"Invalid: {invalid_count}")

    if invalid_count > 0:
        lines.append("")
        lines.append("Errors:")

        for file_path, (is_valid, error) in results.items():
            if not is_valid:
                lines.append(f"  {file_path}:")
                lines.append(f"    {error}")

    return "\n".join(lines)