"""
AST-based Pattern Detection with Context Awareness

Reduces false positives by analyzing code structure and control flow.
"""

import re
from pathlib import Path
from typing import List, Optional, Tuple

try:
    from tree_sitter import Language, Parser
    import tree_sitter_php as tslang_php
    HAS_TREE_SITTER = True
except ImportError:
    HAS_TREE_SITTER = False


class ASTPatternDetector:
    """AST-based pattern detector with context awareness"""

    def __init__(self):
        self.parser = None
        if HAS_TREE_SITTER:
            try:
                language = Language(tslang_php.language_php())
                self.parser = Parser(language)
            except Exception as e:
                import sys
                print(f"[kiwi] ast_detector parser init error: {e}", file=sys.stderr)
                self.parser = None

    def has_error_handling_for_api_call(self, filepath: str, line_number: int) -> bool:
        """
        Check if API call at line_number has error handling.

        Returns True if:
        - is_wp_error() check exists within 10 lines after the call
        - Call is inside try/catch block
        - Call is inside if statement that checks result
        """
        if not self.parser:
            return False

        try:
            content = Path(filepath).read_bytes()
            tree = self.parser.parse(content)
            root = tree.root_node

            # Find the API call node at line_number
            api_call_node = self._find_node_at_line(root, line_number)
            if not api_call_node:
                return False

            # Check 1: Is call inside try/catch?
            if self._is_inside_try_catch(api_call_node):
                return True

            # Check 2: Is there is_wp_error() check nearby?
            if self._has_is_wp_error_check_nearby(api_call_node, content):
                return True

            # Check 3: Is result checked in if statement?
            if self._has_result_check_nearby(api_call_node, content):
                return True

            return False

        except Exception as e:
            import sys
            print(f"[kiwi] has_error_handling check error: {e}", file=sys.stderr)
            return False

    def has_validation_after_sanitize(self, filepath: str, line_number: int) -> bool:
        """
        Check if sanitize_text_field() call has validation after it.

        Returns True if:
        - empty() check exists within 5 lines
        - Variable is used in if statement
        - Variable is validated with regex/strlen
        """
        if not self.parser:
            return False

        try:
            content = Path(filepath).read_bytes()
            tree = self.parser.parse(content)
            root = tree.root_node

            # Find the sanitize call node
            sanitize_node = self._find_node_at_line(root, line_number)
            if not sanitize_node:
                return False

            # Get variable name being assigned
            var_name = self._get_assigned_variable(sanitize_node)
            if not var_name:
                return False

            # Check if variable is validated nearby
            if self._has_validation_for_variable(sanitize_node, var_name, content):
                return True

            return False

        except Exception as e:
            import sys
            print(f"[kiwi] has_validation check error: {e}", file=sys.stderr)
            return False

    def has_nonce_check(self, filepath: str, line_number: int) -> bool:
        """
        Check if wp_verify_nonce() is used in an if statement condition.

        Returns True if:
        - wp_verify_nonce() is inside an if statement condition
        - Result is checked with ! operator
        """
        if not self.parser:
            return False

        try:
            content = Path(filepath).read_bytes()
            tree = self.parser.parse(content)
            root = tree.root_node

            # Find all nodes at this line
            target_line = line_number - 1  # 0-indexed

            def find_nonce_call(node):
                """Recursively find wp_verify_nonce function call"""
                if node.start_point[0] == target_line:
                    # Check if this is a function call to wp_verify_nonce
                    if node.type == 'function_call_expression':
                        name_node = node.child_by_field_name('name')
                        if name_node and 'wp_verify_nonce' in name_node.text.decode('utf-8', errors='ignore'):
                            return node

                for child in node.children:
                    result = find_nonce_call(child)
                    if result:
                        return result
                return None

            nonce_node = find_nonce_call(root)
            if not nonce_node:
                return False

            # Check if inside if statement
            current = nonce_node.parent
            while current:
                if current.type == 'if_statement':
                    return True
                current = current.parent

            return False

        except Exception as e:
            import sys
            print(f"[kiwi] has_nonce_check error: {e}", file=sys.stderr)
            return False

    def _find_node_at_line(self, root, line_number: int):
        """Find AST node at specific line number"""
        target_line = line_number - 1  # 0-indexed

        def traverse(node):
            if node.start_point[0] == target_line:
                return node
            for child in node.children:
                result = traverse(child)
                if result:
                    return result
            return None

        return traverse(root)

    def _is_inside_try_catch(self, node) -> bool:
        """Check if node is inside try/catch block"""
        current = node.parent
        while current:
            if current.type == 'try_statement':
                return True
            current = current.parent
        return False

    def _has_is_wp_error_check_nearby(self, node, content: bytes) -> bool:
        """Check if is_wp_error() exists within 20 lines after node"""
        start_line = node.start_point[0]
        end_line = start_line + 20  # Increased from 10 to 20

        lines = content.decode('utf-8', errors='ignore').split('\n')
        context = '\n'.join(lines[start_line:end_line])

        return bool(re.search(r'is_wp_error\s*\(', context))

    def _has_result_check_nearby(self, node, content: bytes) -> bool:
        """Check if result is checked in if statement"""
        start_line = node.start_point[0]
        end_line = start_line + 10

        lines = content.decode('utf-8', errors='ignore').split('\n')
        context = '\n'.join(lines[start_line:end_line])

        # Look for common error check patterns
        patterns = [
            r'if\s*\(\s*\$\w+\s*===\s*false',
            r'if\s*\(\s*!\s*\$\w+',
            r'if\s*\(\s*empty\s*\(',
            r'return\s+false',
            r'return\s+null',
        ]

        for pattern in patterns:
            if re.search(pattern, context):
                return True

        return False

    def _get_assigned_variable(self, node) -> Optional[str]:
        """Get variable name from assignment expression"""
        # If node is expression_statement, look for assignment_expression child
        if node.type == 'expression_statement':
            for child in node.children:
                if child.type == 'assignment_expression':
                    left = child.child_by_field_name('left')
                    if left and left.type == 'variable_name':
                        return left.text.decode('utf-8', errors='ignore')

        # Walk up to find assignment
        current = node.parent
        while current:
            if current.type == 'assignment_expression':
                left = current.child_by_field_name('left')
                if left and left.type == 'variable_name':
                    return left.text.decode('utf-8', errors='ignore')
            current = current.parent
        return None

    def _has_validation_for_variable(self, node, var_name: str, content: bytes) -> bool:
        """Check if variable is validated nearby or used in safe context"""
        start_line = node.start_point[0]
        end_line = start_line + 10  # Increased window to 10 lines

        lines = content.decode('utf-8', errors='ignore').split('\n')
        # Look at lines AFTER the sanitize call (start_line+1 onwards)
        context = '\n'.join(lines[start_line+1:end_line])

        # Look for validation patterns
        validation_patterns = [
            rf'if\s*\(\s*empty\s*\(\s*{re.escape(var_name)}',
            rf'if\s*\(\s*!\s*{re.escape(var_name)}',
            rf'{re.escape(var_name)}\s*===\s*["\']',
            rf'{re.escape(var_name)}\s*===\s*null',
            rf'strlen\s*\(\s*{re.escape(var_name)}',
            rf'preg_match\s*\([^,]+,\s*{re.escape(var_name)}',
            rf'wp_verify_nonce\s*\(\s*{re.escape(var_name)}',  # Nonce validation
        ]

        for pattern in validation_patterns:
            if re.search(pattern, context):
                return True

        # Check for safe usage contexts (hashing, encoding, etc.)
        safe_usage_patterns = [
            rf'md5\s*\(\s*{re.escape(var_name)}',  # Hash functions
            rf'sha1\s*\(\s*{re.escape(var_name)}',
            rf'hash\s*\([^,]+,\s*{re.escape(var_name)}',
            rf'base64_encode\s*\(\s*{re.escape(var_name)}',
        ]

        for pattern in safe_usage_patterns:
            if re.search(pattern, context):
                return True

        return False


# Singleton instance
_detector = None


def get_ast_detector() -> ASTPatternDetector:
    """Get singleton AST detector instance"""
    global _detector
    if _detector is None:
        _detector = ASTPatternDetector()
    return _detector
