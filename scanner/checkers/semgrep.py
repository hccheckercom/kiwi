"""Semgrep-based AST checker."""

import json
import subprocess
import tempfile
from pathlib import Path
from typing import List, Dict, Optional

import yaml


class SemgrepChecker:
    """AST-based pattern checker using Semgrep."""

    def __init__(self):
        self.semgrep_available = self._check_semgrep()
        self.rule_cache = {}

    def _check_semgrep(self) -> bool:
        """Check if Semgrep is installed."""
        try:
            subprocess.run(
                ["semgrep", "--version"],
                capture_output=True,
                timeout=5
            )
            return True
        except (FileNotFoundError, subprocess.SubprocessError):
            return False

    def check(self, pattern_def: dict, files: list, theme_path: str) -> list:
        """Run Semgrep check on files.

        Args:
            pattern_def: Lesson definition with scan config
            files: List of file paths to scan
            theme_path: Root path of theme

        Returns:
            List of Violation objects
        """
        # Fallback to regex if Semgrep unavailable
        if not self.semgrep_available:
            return self._fallback_to_regex(pattern_def, files, theme_path)

        # Convert lesson to Semgrep rule
        from ..converters.semgrep_converter import lesson_to_semgrep_rule
        rule = lesson_to_semgrep_rule(pattern_def)

        if rule is None:
            # Pattern not convertible (e.g., BOM check, absence)
            return self._fallback_to_regex(pattern_def, files, theme_path)

        # Run Semgrep
        try:
            violations = self._run_semgrep(rule, files, theme_path, pattern_def)
            return violations
        except Exception as e:
            # Semgrep failed, fallback to regex
            import sys
            print(f"[WARN] Semgrep failed for {pattern_def['id']}: {e}", file=sys.stderr)
            return self._fallback_to_regex(pattern_def, files, theme_path)

    def _run_semgrep(
        self,
        rule: dict,
        files: list,
        theme_path: str,
        pattern_def: dict
    ) -> list:
        """Execute Semgrep with rule."""
        # Write rule to temp file
        with tempfile.NamedTemporaryFile(
            mode="w",
            suffix=".yaml",
            delete=False,
            encoding="utf-8"
        ) as f:
            yaml.dump({"rules": [rule]}, f, allow_unicode=True)
            rule_path = f.name

        try:
            # Run Semgrep
            result = subprocess.run(
                [
                    "semgrep",
                    "--config", rule_path,
                    "--json",
                    "--no-git-ignore",
                    "--quiet",
                    *files
                ],
                capture_output=True,
                text=True,
                timeout=60,
                cwd=theme_path
            )

            # Parse results
            if result.returncode not in (0, 1):
                # Semgrep error (not just findings)
                raise RuntimeError(f"Semgrep exit code {result.returncode}")

            output = json.loads(result.stdout)
            return self._parse_results(output, pattern_def, theme_path)

        finally:
            Path(rule_path).unlink(missing_ok=True)

    def _parse_results(
        self,
        output: dict,
        pattern_def: dict,
        theme_path: str
    ) -> list:
        """Convert Semgrep JSON output to Violations."""
        from ..models import Violation
        import os

        violations = []
        for result in output.get("results", []):
            rel_path = os.path.relpath(result["path"], theme_path)
            violations.append(Violation(
                lesson_id=pattern_def["id"],
                severity=pattern_def["severity"],
                category=pattern_def.get("category", ""),
                description=pattern_def.get("title", ""),
                file=rel_path.replace("\\", "/"),
                line=result["start"]["line"],
                match_text=result["extra"]["lines"][:120]
            ))

        return violations

    def _fallback_to_regex(
        self,
        pattern_def: dict,
        files: list,
        theme_path: str
    ) -> list:
        """Fallback to regex checker."""
        scan = pattern_def.get("scan", {})
        scan_type = scan.get("type", "presence")

        # Get appropriate checker based on scan type
        if scan_type == "bom-check":
            from .bom import BOMChecker
            return BOMChecker().check(pattern_def, files, theme_path)
        elif scan_type in ("cross-check", "cross_check"):
            from .cross_check import CrossCheckChecker
            return CrossCheckChecker().check(pattern_def, files, theme_path)
        elif scan_type == "absence":
            from .absence import AbsenceChecker
            return AbsenceChecker().check(pattern_def, files, theme_path)
        else:
            from .presence import PresenceChecker
            return PresenceChecker().check(pattern_def, files, theme_path)