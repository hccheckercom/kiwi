"""
Pattern Inventory Extractor — Extract ALL code patterns from file.

Proactive coverage approach: extract patterns before violations occur.
"""

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Set, Optional
import sys

sys.path.insert(0, str(Path(__file__).parent.parent))

from scanner.checkers.ast_checker import _get_parser, _detect_lang

# Import AST detector
try:
    from .ast_detector import get_ast_detector
    HAS_AST_DETECTOR = True
except ImportError:
    HAS_AST_DETECTOR = False


@dataclass
class CodePattern:
    """Single code pattern extracted from file"""
    pattern_type: str  # 'function_call', 'security_op', 'error_handling', 'hook', 'db_op', 'class_def', 'function_def'
    pattern_name: str  # 'wp_remote_post', 'sanitize_text_field', 'add_action'
    context: str       # surrounding code snippet
    line: int
    severity: str      # CRITICAL, HIGH, SUGGEST (inferred)
    file_path: str
    language: str      # php, javascript, typescript


@dataclass
class FileInventory:
    """Complete inventory of patterns in a file"""
    file_path: str
    language: str
    patterns: List[CodePattern] = field(default_factory=list)
    total_patterns: int = 0

    def add_pattern(self, pattern: CodePattern):
        self.patterns.append(pattern)
        self.total_patterns += 1


class InventoryExtractor:
    """Extract all code patterns from file"""

    # Security-sensitive functions (CRITICAL)
    SECURITY_FUNCTIONS = {
        'wp_remote_post', 'wp_remote_get', 'wp_remote_request',
        'curl_exec', 'file_get_contents', 'fopen', 'file_put_contents',
        'eval', 'exec', 'system', 'shell_exec', 'passthru',
        'unserialize', 'base64_decode',
        'wp_verify_nonce', 'check_ajax_referer', 'check_admin_referer',
        'sanitize_text_field', 'sanitize_email',
        'wp_kses', 'wp_kses_post', 'absint', 'intval',
    }

    # Output escaping functions (skip - these don't need validation)
    OUTPUT_ESCAPING_FUNCTIONS = {
        'esc_html', 'esc_attr', 'esc_url', 'esc_js', 'esc_textarea',
        'esc_sql', 'esc_like',
    }

    # Database operations (HIGH)
    DB_FUNCTIONS = {
        '$wpdb->query', '$wpdb->get_results', '$wpdb->get_row', '$wpdb->get_var',
        '$wpdb->insert', '$wpdb->update', '$wpdb->delete', '$wpdb->prepare',
        'wz_bulk_insert', 'wz_get_products', 'wz_get_product',
    }

    # WordPress hooks (SUGGEST)
    HOOK_FUNCTIONS = {
        'add_action', 'add_filter', 'do_action', 'apply_filters',
        'remove_action', 'remove_filter',
    }

    # Error handling patterns (HIGH)
    ERROR_PATTERNS = {
        'try', 'catch', 'throw', 'is_wp_error', 'WP_Error',
        'error_log', 'trigger_error',
    }

    def extract(self, file_path: str) -> FileInventory:
        """
        Extract all patterns from file.

        Returns:
            FileInventory with all patterns found
        """
        path = Path(file_path)
        if not path.exists():
            return FileInventory(file_path=file_path, language='unknown')

        lang = _detect_lang(file_path)
        if not lang:
            return FileInventory(file_path=file_path, language='unknown')

        inventory = FileInventory(file_path=file_path, language=lang)

        try:
            content = path.read_text(encoding='utf-8', errors='ignore')
        except Exception as e:
            import sys
            print(f"[kiwi] inventory extract read error: {e}", file=sys.stderr)
            return inventory

        # Extract patterns based on language
        if lang == 'php':
            self._extract_php_patterns(content, inventory)
        elif lang == 'javascript':
            self._extract_js_patterns(content, inventory)

        return inventory

    def _has_error_handling_nearby(self, lines: list, line_idx: int, window: int = 5) -> bool:
        """
        Check if error handling exists within ±window lines.

        Looks for: is_wp_error(), try/catch, if (empty()), error checks
        """
        start = max(0, line_idx - window)
        end = min(len(lines), line_idx + window + 1)

        context = '\n'.join(lines[start:end])

        # Error handling patterns
        error_patterns = [
            r'is_wp_error\s*\(',
            r'WP_Error',
            r'try\s*\{',
            r'catch\s*\(',
            r'if\s*\(\s*empty\s*\(',
            r'if\s*\(\s*!\s*',
            r'if\s*\(\s*\$[a-zA-Z_].*===.*false',
            r'return\s+false',
            r'return\s+null',
            r'throw\s+new',
        ]

        for pattern in error_patterns:
            if re.search(pattern, context, re.IGNORECASE):
                return True

        return False

    def _extract_php_patterns(self, content: str, inventory: FileInventory):
        """Extract patterns from PHP file"""
        lines = content.split('\n')

        # Get AST detector once for this file
        ast_detector = None
        if HAS_AST_DETECTOR:
            try:
                ast_detector = get_ast_detector()
                if not ast_detector.parser:
                    ast_detector = None
            except Exception as e:
                ast_detector = None

        # 1. Function definitions
        func_pattern = r'function\s+([a-zA-Z_][a-zA-Z0-9_]*)\s*\('
        for i, line in enumerate(lines, 1):
            for match in re.finditer(func_pattern, line):
                fn_name = match.group(1)
                inventory.add_pattern(CodePattern(
                    pattern_type='function_def',
                    pattern_name=fn_name,
                    context=line.strip(),
                    line=i,
                    severity='SUGGEST',
                    file_path=inventory.file_path,
                    language='php'
                ))

        # 2. Class definitions
        class_pattern = r'class\s+([a-zA-Z_][a-zA-Z0-9_]*)'
        for i, line in enumerate(lines, 1):
            for match in re.finditer(class_pattern, line):
                class_name = match.group(1)
                inventory.add_pattern(CodePattern(
                    pattern_type='class_def',
                    pattern_name=class_name,
                    context=line.strip(),
                    line=i,
                    severity='SUGGEST',
                    file_path=inventory.file_path,
                    language='php'
                ))

        # 3. Security-sensitive function calls (with AST-based context check)
        for fn in self.SECURITY_FUNCTIONS:
            pattern = rf'\b{re.escape(fn)}\s*\('
            for i, line in enumerate(lines, 1):
                if re.search(pattern, line):
                    skip_pattern = False

                    # Use AST detector for wp_remote_* calls
                    if fn.startswith('wp_remote_'):
                        if ast_detector and ast_detector.parser:
                            try:
                                has_error_handling = ast_detector.has_error_handling_for_api_call(inventory.file_path, i)
                                if has_error_handling:
                                    skip_pattern = True
                            except Exception as e:
                                pass  # AST check failed, fallback to regex

                        # Fallback to regex-based context check
                        if not skip_pattern and self._has_error_handling_nearby(lines, i - 1):
                            skip_pattern = True

                    # Use AST detector for sanitize_* calls
                    elif fn.startswith('sanitize_'):
                        if ast_detector and ast_detector.parser:
                            try:
                                has_validation = ast_detector.has_validation_after_sanitize(inventory.file_path, i)
                                if has_validation:
                                    skip_pattern = True
                            except Exception as e:
                                pass

                    # Use regex for wp_verify_nonce calls (simpler than AST)
                    elif fn == 'wp_verify_nonce':
                        # Check if used in if statement condition (with ! negation)
                        if re.search(r'if\s*\(.*wp_verify_nonce', line):
                            skip_pattern = True

                    if skip_pattern:
                        continue

                    inventory.add_pattern(CodePattern(
                        pattern_type='security_op',
                        pattern_name=fn,
                        context=line.strip(),
                        line=i,
                        severity='CRITICAL',
                        file_path=inventory.file_path,
                        language='php'
                    ))

        # 3b. Output escaping functions (skip - no validation needed)
        for fn in self.OUTPUT_ESCAPING_FUNCTIONS:
            # These are intentionally not added to inventory as they don't need validation
            pass

        # 4. Database operations
        for db_fn in self.DB_FUNCTIONS:
            # Handle both function calls and $wpdb methods
            if db_fn.startswith('$wpdb->'):
                pattern = re.escape(db_fn)
            else:
                pattern = rf'\b{re.escape(db_fn)}\s*\('

            for i, line in enumerate(lines, 1):
                if re.search(pattern, line):
                    inventory.add_pattern(CodePattern(
                        pattern_type='db_op',
                        pattern_name=db_fn,
                        context=line.strip(),
                        line=i,
                        severity='HIGH',
                        file_path=inventory.file_path,
                        language='php'
                    ))

        # 5. WordPress hooks
        for hook_fn in self.HOOK_FUNCTIONS:
            pattern = rf'\b{re.escape(hook_fn)}\s*\('
            for i, line in enumerate(lines, 1):
                if re.search(pattern, line):
                    inventory.add_pattern(CodePattern(
                        pattern_type='hook',
                        pattern_name=hook_fn,
                        context=line.strip(),
                        line=i,
                        severity='SUGGEST',
                        file_path=inventory.file_path,
                        language='php'
                    ))

        # 6. Error handling
        for err_pattern in self.ERROR_PATTERNS:
            pattern = rf'\b{re.escape(err_pattern)}\b'
            for i, line in enumerate(lines, 1):
                if re.search(pattern, line):
                    inventory.add_pattern(CodePattern(
                        pattern_type='error_handling',
                        pattern_name=err_pattern,
                        context=line.strip(),
                        line=i,
                        severity='HIGH',
                        file_path=inventory.file_path,
                        language='php'
                    ))

        # 7. API calls (wp_remote_*) - REMOVED: Already handled in section 3 with AST detection

    def _extract_js_patterns(self, content: str, inventory: FileInventory):
        """Extract patterns from JS/TS file"""
        lines = content.split('\n')

        # 1. Function definitions
        func_pattern = r'(?:function|const|let|var)\s+([a-zA-Z_$][a-zA-Z0-9_$]*)\s*[=\(]'
        for i, line in enumerate(lines, 1):
            for match in re.finditer(func_pattern, line):
                fn_name = match.group(1)
                inventory.add_pattern(CodePattern(
                    pattern_type='function_def',
                    pattern_name=fn_name,
                    context=line.strip(),
                    line=i,
                    severity='SUGGEST',
                    file_path=inventory.file_path,
                    language='javascript'
                ))

        # 2. Class definitions
        class_pattern = r'class\s+([a-zA-Z_$][a-zA-Z0-9_$]*)'
        for i, line in enumerate(lines, 1):
            for match in re.finditer(class_pattern, line):
                class_name = match.group(1)
                inventory.add_pattern(CodePattern(
                    pattern_type='class_def',
                    pattern_name=class_name,
                    context=line.strip(),
                    line=i,
                    severity='SUGGEST',
                    file_path=inventory.file_path,
                    language='javascript'
                ))

        # 3. API calls (fetch, axios)
        api_patterns = [
            (r'\bfetch\s*\(', 'fetch'),
            (r'\baxios\.[a-z]+\s*\(', 'axios'),
            (r'\$\.ajax\s*\(', '$.ajax'),
        ]

        for pattern, name in api_patterns:
            for i, line in enumerate(lines, 1):
                if re.search(pattern, line):
                    inventory.add_pattern(CodePattern(
                        pattern_type='function_call',
                        pattern_name=name,
                        context=line.strip(),
                        line=i,
                        severity='CRITICAL',
                        file_path=inventory.file_path,
                        language='javascript'
                    ))

        # 4. Error handling
        error_patterns = ['try', 'catch', 'throw', 'Promise.reject', 'Promise.catch']
        for err_pattern in error_patterns:
            pattern = rf'\b{re.escape(err_pattern)}\b'
            for i, line in enumerate(lines, 1):
                if re.search(pattern, line):
                    inventory.add_pattern(CodePattern(
                        pattern_type='error_handling',
                        pattern_name=err_pattern,
                        context=line.strip(),
                        line=i,
                        severity='HIGH',
                        file_path=inventory.file_path,
                        language='javascript'
                    ))

        # 5. React hooks (if applicable)
        hook_pattern = r'\buse[A-Z][a-zA-Z]*\s*\('
        for i, line in enumerate(lines, 1):
            for match in re.finditer(hook_pattern, line):
                hook_name = match.group(0).replace('(', '').strip()
                inventory.add_pattern(CodePattern(
                    pattern_type='hook',
                    pattern_name=hook_name,
                    context=line.strip(),
                    line=i,
                    severity='SUGGEST',
                    file_path=inventory.file_path,
                    language='javascript'
                ))


def extract_inventory(file_path: str) -> FileInventory:
    """
    Convenience function to extract inventory from file.

    Args:
        file_path: Path to file

    Returns:
        FileInventory with all patterns
    """
    extractor = InventoryExtractor()
    return extractor.extract(file_path)


if __name__ == '__main__':
    import sys

    if len(sys.argv) < 2:
        print("Usage: python inventory.py <file_path>")
        sys.exit(1)

    file_path = sys.argv[1]
    inventory = extract_inventory(file_path)

    print(f"File: {inventory.file_path}")
    print(f"Language: {inventory.language}")
    print(f"Total patterns: {inventory.total_patterns}")
    print()

    # Group by pattern type
    by_type = {}
    for pattern in inventory.patterns:
        if pattern.pattern_type not in by_type:
            by_type[pattern.pattern_type] = []
        by_type[pattern.pattern_type].append(pattern)

    for pattern_type, patterns in sorted(by_type.items()):
        print(f"{pattern_type}: {len(patterns)}")
        for p in patterns[:3]:  # Show first 3
            print(f"  Line {p.line}: {p.pattern_name} [{p.severity}]")
        if len(patterns) > 3:
            print(f"  ... and {len(patterns) - 3} more")
        print()
