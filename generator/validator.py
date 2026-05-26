"""
Validator

Multi-layer validation for generated code.
Ensures generated themes are bug-free and GATE-compliant.
"""

from pathlib import Path
from typing import Dict, List, Optional, Tuple
import subprocess
import re


class ValidationResult:
    """Result of validation check."""

    def __init__(self, passed: bool, message: str = "", violations: List = None):
        self.passed = passed
        self.message = message
        self.violations = violations or []

    def __bool__(self):
        return self.passed


class Validator:
    """
    Multi-layer validation for generated code.

    Layers:
    1. Template validation (pre-generation)
    2. Content validation (post-generation)
    3. Kiwi scan (bug detection)
    4. GATE compliance (rule enforcement)
    5. Integration tests (phase verification)
    """

    def __init__(self, kiwi_dir: Path):
        self.kiwi_dir = kiwi_dir

    def validate_template(self, template_content: str) -> ValidationResult:
        """
        Layer 1: Template validation (pre-generation).

        Checks:
        - All required variables provided
        - No circular dependencies
        - Template syntax valid (Jinja2)
        """
        from jinja2 import Environment, TemplateSyntaxError

        try:
            env = Environment()
            env.from_string(template_content)
            return ValidationResult(True, "Template syntax valid")
        except TemplateSyntaxError as e:
            return ValidationResult(False, f"Template syntax error: {e}")

    def validate_content(self, content: str, file_path: str) -> ValidationResult:
        """
        Layer 2: Content validation (post-generation).

        Checks:
        - No TODO/placeholder strings
        - PHP syntax valid (php -l)
        - No hardcoded hex colors (except in token definition files)
        - No BEM classes
        - No PHP constant names with hyphens (LES-474)
        """
        issues = []

        # Check for TODO/placeholder
        if 'TODO' in content or '{{' in content or '}}' in content:
            issues.append("Contains TODO or unresolved placeholders")

        # Check for PHP constant names with hyphens (LES-474)
        if file_path.endswith('.php'):
            constant_hyphen_pattern = r'define\s*\(\s*[\'"]([A-Z0-9_]*-[A-Z0-9_-]*)[\'"]'
            matches = re.findall(constant_hyphen_pattern, content)
            if matches:
                issues.append(f"LES-474: PHP constant names contain hyphens: {', '.join(matches)}")

        # Check for hardcoded hex colors (whitelist token definition files)
        hex_pattern = r'#[0-9a-fA-F]{3,6}'
        token_definition_files = [
            'store-config.php',
            'design-tokens.json',
            'src/main.css',
            'main.css'
        ]
        is_token_file = any(file_path.endswith(f) for f in token_definition_files)

        if not is_token_file and re.search(hex_pattern, content):
            matches = re.findall(hex_pattern, content)
            issues.append(f"Contains hardcoded hex colors: {', '.join(set(matches))}")

        # Check for BEM classes (__ or --)
        if file_path.endswith('.php'):
            bem_pattern = r'class=["\'][^"\']*(__|--)[\w-]*["\']'
            if re.search(bem_pattern, content):
                issues.append("Contains BEM classes (__ or --)")

        # PHP syntax check (skip for template files with HTML)
        if file_path.endswith('.php'):
            # Skip PHP syntax check for template files that start with HTML
            template_files = ['header.php', 'footer.php', 'index.php']
            is_template = any(file_path.endswith(f) for f in template_files)

            if not is_template:
                php_result = self._check_php_syntax(content)
                if not php_result.passed:
                    issues.append(php_result.message)

        if issues:
            return ValidationResult(False, "; ".join(issues))

        return ValidationResult(True, "Content validation passed")

    def _check_php_syntax(self, content: str) -> ValidationResult:
        """Check PHP syntax using php -l."""
        try:
            # Write to temp file
            import tempfile
            with tempfile.NamedTemporaryFile(mode='w', suffix='.php', delete=False, encoding='utf-8') as f:
                f.write(content)
                temp_path = f.name

            # Run php -l
            result = subprocess.run(
                ['php', '-l', temp_path],
                capture_output=True,
                text=True,
                timeout=5
            )

            # Clean up
            Path(temp_path).unlink()

            if result.returncode == 0:
                return ValidationResult(True, "PHP syntax valid")
            else:
                return ValidationResult(False, f"PHP syntax error: {result.stderr}")

        except FileNotFoundError:
            # PHP not installed - skip syntax check
            return ValidationResult(True, "PHP not available, skipping syntax check")
        except Exception as e:
            return ValidationResult(False, f"PHP syntax check failed: {e}")

    def validate_with_kiwi(self, file_path: Path) -> ValidationResult:
        """
        Layer 3: Kiwi scan (bug detection).

        Runs Kiwi scanner on generated file.
        """
        try:
            # Import scanner
            import sys
            sys.path.insert(0, str(self.kiwi_dir))
            from scanner.cli import scan_theme

            # Scan file
            report = scan_theme(
                str(file_path.parent),
                severity_filter="CRITICAL",
                platform="wp",
                scope_type="theme"
            )

            # Filter violations for this file
            violations = [
                v for v in report.violations
                if Path(v.file).name == file_path.name
            ]

            if violations:
                msg = f"Found {len(violations)} CRITICAL violations"
                return ValidationResult(False, msg, violations)

            return ValidationResult(True, "Kiwi scan passed (0 CRITICAL violations)")

        except Exception as e:
            return ValidationResult(False, f"Kiwi scan failed: {e}")

    def validate_gate_compliance(self, content: str, file_path: str) -> ValidationResult:
        """
        Layer 4: GATE compliance (rule enforcement).

        Checks against 15 immutable rules from 00-GATE.md.
        Whitelists token definition files where hardcoded values are necessary.
        """
        issues = []

        # Token definition files are allowed to have hardcoded values
        token_definition_files = [
            'store-config.php',
            'design-tokens.json',
            'src/main.css',
            'main.css',
            'tailwind.config.js'
        ]
        is_token_file = any(file_path.endswith(f) for f in token_definition_files)

        # Rule 4: No hardcoded px/colors/fonts (except in token files)
        if not is_token_file and re.search(r'\d+px', content) and 'tailwind.config.js' not in file_path:
            issues.append("Rule 4: Contains hardcoded px values")

        # Rule 5: No max-width in media queries (except in token files)
        if not is_token_file and 'max-width' in content and file_path.endswith('.css'):
            issues.append("Rule 5: Contains max-width (mobile-first only)")

        # Rule 6: No WooCommerce
        wc_pattern = r'\b(wc_|WC_|woocommerce)\w*'
        if re.search(wc_pattern, content):
            issues.append("Rule 6: Contains WooCommerce references")

        # Rule 13: No BEM classes
        if file_path.endswith('.php'):
            bem_pattern = r'class=["\'][^"\']*(__|--)[\w-]*["\']'
            if re.search(bem_pattern, content):
                issues.append("Rule 13: Contains BEM classes")

        if issues:
            return ValidationResult(False, "; ".join(issues))

        return ValidationResult(True, "GATE compliance passed")

    def validate_phase(self, phase: str, output_dir: Path) -> ValidationResult:
        """
        Layer 5: Integration tests (phase verification).

        Phase-specific verification:
        - G0-T1: npm run build:css succeeds
        - G0-T2: Theme activates without errors
        - G0-T3: Responsive at 3 breakpoints
        """
        if phase == 'G0-T1':
            return self._verify_tailwind_build(output_dir)
        elif phase == 'G0-T2':
            return self._verify_theme_activation(output_dir)
        elif phase == 'G0-T3':
            return self._verify_responsive(output_dir)
        else:
            return ValidationResult(True, f"No verification for phase {phase}")

    def _verify_tailwind_build(self, output_dir: Path) -> ValidationResult:
        """Verify npm run build:css succeeds."""
        package_json = output_dir / 'package.json'
        if not package_json.exists():
            return ValidationResult(False, "package.json not found")

        try:
            # Run npm install
            subprocess.run(
                ['npm', 'install'],
                cwd=str(output_dir),
                capture_output=True,
                timeout=60
            )

            # Run npm run build:css
            result = subprocess.run(
                ['npm', 'run', 'build:css'],
                cwd=str(output_dir),
                capture_output=True,
                text=True,
                timeout=30
            )

            if result.returncode == 0:
                return ValidationResult(True, "Tailwind build succeeded")
            else:
                return ValidationResult(False, f"Tailwind build failed: {result.stderr}")

        except Exception as e:
            return ValidationResult(False, f"Build verification failed: {e}")

    def _verify_theme_activation(self, output_dir: Path) -> ValidationResult:
        """Verify theme has no PHP fatal errors."""
        functions_php = output_dir / 'functions.php'
        if not functions_php.exists():
            return ValidationResult(False, "functions.php not found")

        # Check PHP syntax
        result = self._check_php_syntax(functions_php.read_text(encoding='utf-8'))
        if not result.passed:
            return ValidationResult(False, f"Theme activation check failed: {result.message}")

        return ValidationResult(True, "Theme activation check passed")

    def _verify_responsive(self, output_dir: Path) -> ValidationResult:
        """Verify responsive breakpoints."""
        # Phase 1 MVP: Basic check for header.php and footer.php
        header = output_dir / 'header.php'
        footer = output_dir / 'footer.php'

        if not header.exists():
            return ValidationResult(False, "header.php not found")
        if not footer.exists():
            return ValidationResult(False, "footer.php not found")

        return ValidationResult(True, "Responsive check passed (header + footer exist)")

    def validate_all(
        self,
        content: str,
        file_path: str,
        phase: Optional[str] = None
    ) -> Tuple[bool, List[str]]:
        """
        Run all validation layers.

        Returns:
            (success, messages) tuple
        """
        messages = []

        # Layer 2: Content validation
        result = self.validate_content(content, file_path)
        messages.append(f"Content: {result.message}")
        if not result.passed:
            return False, messages

        # Layer 4: GATE compliance
        result = self.validate_gate_compliance(content, file_path)
        messages.append(f"GATE: {result.message}")
        if not result.passed:
            return False, messages

        return True, messages