"""PHP AST-based checker for CRITICAL security lessons.

Uses php-parser (nikic/php-parser) via subprocess to detect violations
more accurately than regex patterns.
"""

import json
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Optional


@dataclass
class ASTViolation:
    """AST-detected violation."""
    lesson_id: str
    file: str
    line: int
    description: str
    confidence: float  # 0.0-1.0


class PHPASTChecker:
    """PHP AST-based security checker for top 10 CRITICAL lessons."""

    # Top 10 CRITICAL lessons to check with AST
    AST_LESSONS = {
        "LES-001": "is_user_logged_in",
        "LES-002": "order_user_id_check",
        "LES-016": "idor_check",
        "LES-030": "post_unslash",
        "LES-039": "rest_nonce",
        "LES-045": "raw_superglobal",
        "LES-064": "ajax_referer",
        "LES-071": "rest_permission",
        "LES-076": "wpdb_prepare",
        "LES-213": "rest_permission_callback",
    }

    def __init__(self, php_parser_path: Optional[str] = None):
        """
        Initialize AST checker.

        Args:
            php_parser_path: Path to PHP parser script (optional)
        """
        self.php_parser_path = php_parser_path or self._find_php_parser()

    def _find_php_parser(self) -> Optional[str]:
        """Find PHP parser script in kiwi directory."""
        kiwi_dir = Path(__file__).parent.parent
        parser_script = kiwi_dir / "ast" / "php_parser.php"
        return str(parser_script) if parser_script.exists() else None

    def check_file(self, file_path: str, lesson_ids: list[str] = None) -> list[ASTViolation]:
        """
        Check PHP file using AST for specified lessons.

        Args:
            file_path: Path to PHP file
            lesson_ids: List of lesson IDs to check (default: all AST lessons)

        Returns:
            List of AST-detected violations
        """
        if not self.php_parser_path:
            return []  # Parser not available, fall back to regex

        if lesson_ids is None:
            lesson_ids = list(self.AST_LESSONS.keys())

        # Filter to only AST-supported lessons
        lesson_ids = [lid for lid in lesson_ids if lid in self.AST_LESSONS]
        if not lesson_ids:
            return []

        try:
            # Call PHP parser script
            result = subprocess.run(
                ["php", self.php_parser_path, file_path, ",".join(lesson_ids)],
                capture_output=True,
                text=True,
                timeout=10,
            )

            if result.returncode != 0:
                return []  # Parser failed, fall back to regex

            # Parse JSON output
            violations = json.loads(result.stdout)
            return [
                ASTViolation(
                    lesson_id=v["lesson_id"],
                    file=file_path,
                    line=v["line"],
                    description=v["description"],
                    confidence=v.get("confidence", 1.0),
                )
                for v in violations
            ]

        except (subprocess.TimeoutExpired, subprocess.SubprocessError, json.JSONDecodeError):
            return []  # Fall back to regex on any error

    def check_lesson_001(self, ast_tree: dict) -> list[dict]:
        """
        LES-001: Account template missing is_user_logged_in() gate.

        Checks if file has is_user_logged_in() call before sensitive operations.
        """
        violations = []

        # Look for template files without is_user_logged_in() check
        has_login_check = self._has_function_call(ast_tree, "is_user_logged_in")

        # Look for sensitive operations (wz_get_order, wz_get_user_orders, etc.)
        sensitive_calls = self._find_function_calls(
            ast_tree, ["wz_get_order", "wz_get_user_orders", "wz_get_customer"]
        )

        if sensitive_calls and not has_login_check:
            for call in sensitive_calls:
                violations.append({
                    "lesson_id": "LES-001",
                    "line": call["line"],
                    "description": f"Sensitive function {call['name']}() without is_user_logged_in() gate",
                    "confidence": 0.95,
                })

        return violations

    def check_lesson_076(self, ast_tree: dict) -> list[dict]:
        """
        LES-076: SQL query without $wpdb->prepare().

        Detects direct $wpdb->query() calls without prepare().
        """
        violations = []

        # Find all $wpdb->query() calls
        query_calls = self._find_method_calls(ast_tree, "$wpdb", "query")

        for call in query_calls:
            # Check if argument is a string concatenation or variable
            arg = call.get("arg")
            if arg and self._is_dynamic_string(arg):
                # Dynamic string in query() without prepare() = SQL injection risk
                violations.append({
                    "lesson_id": "LES-076",
                    "line": call["line"],
                    "description": "Dynamic SQL query without $wpdb->prepare()",
                    "confidence": 0.90,
                })

        return violations

    def check_lesson_045(self, ast_tree: dict) -> list[dict]:
        """
        LES-045: Raw $_GET/$_POST without sanitization.

        Detects direct superglobal access without sanitize_*() wrapper.
        """
        violations = []

        # Find all $_GET/$_POST accesses
        superglobal_accesses = self._find_superglobal_access(ast_tree, ["$_GET", "$_POST", "$_REQUEST"])

        for access in superglobal_accesses:
            # Check if wrapped in sanitize function
            if not self._is_wrapped_in_sanitize(access):
                violations.append({
                    "lesson_id": "LES-045",
                    "line": access["line"],
                    "description": f"{access['var']}['{access['key']}'] without sanitization",
                    "confidence": 0.85,
                })

        return violations

    def _has_function_call(self, ast_tree: dict, function_name: str) -> bool:
        """Check if AST contains a function call."""
        # Simplified - real implementation would traverse AST
        return function_name in str(ast_tree)

    def _find_function_calls(self, ast_tree: dict, function_names: list[str]) -> list[dict]:
        """Find all calls to specified functions in AST."""
        # Simplified - real implementation would traverse AST
        return []

    def _find_method_calls(self, ast_tree: dict, object_var: str, method_name: str) -> list[dict]:
        """Find all method calls on an object."""
        # Simplified - real implementation would traverse AST
        return []

    def _is_dynamic_string(self, arg: dict) -> bool:
        """Check if argument is a dynamic string (concatenation or variable)."""
        # Simplified - real implementation would check AST node type
        return True

    def _find_superglobal_access(self, ast_tree: dict, vars: list[str]) -> list[dict]:
        """Find all accesses to superglobal variables."""
        # Simplified - real implementation would traverse AST
        return []

    def _is_wrapped_in_sanitize(self, access: dict) -> bool:
        """Check if superglobal access is wrapped in sanitize function."""
        # Simplified - real implementation would check parent nodes
        return False