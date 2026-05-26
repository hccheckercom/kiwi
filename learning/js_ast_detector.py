"""JavaScript/TypeScript AST Pattern Detection

Uses tree-sitter to parse JS/TS files and detect patterns that regex cannot catch.
Complements regex-based scanning with semantic analysis.
"""

import sys
from pathlib import Path
from typing import List, Dict, Optional

sys.path.insert(0, str(Path(__file__).parent.parent))

# Lazy imports
_parser = None
_js_language = None


def get_parser():
    """Get tree-sitter parser for JavaScript/TypeScript."""
    global _parser, _js_language

    if _parser is None:
        from tree_sitter import Parser, Language

        # Load JavaScript language
        # Note: tree-sitter-javascript supports both JS and TS
        try:
            import tree_sitter_javascript as tsjs
            _js_language = Language(tsjs.language())
        except Exception as e:
            raise ImportError(
                f"tree-sitter-javascript not available ({e}). "
                "Install with: pip install tree-sitter-javascript"
            )

        _parser = Parser()
        _parser.language = _js_language

    return _parser


def parse_js_file(file_path: str) -> Optional[object]:
    """
    Parse JS/TS file using tree-sitter.

    Returns: Tree object or None if parse fails
    """
    parser = get_parser()

    try:
        with open(file_path, 'rb') as f:
            source_code = f.read()

        tree = parser.parse(source_code)
        return tree
    except Exception as e:
        print(f"Failed to parse {file_path}: {e}")
        return None


def detect_unhandled_promise(tree, source_code: str) -> List[Dict]:
    """
    Detect Promise without .catch() or try/catch.

    Pattern: await fetch() without error handling
    """
    violations = []

    def visit_node(node):
        # Look for await expressions
        if node.type == 'await_expression':
            # Check if wrapped in try/catch
            parent = node.parent
            in_try_catch = False

            while parent:
                if parent.type == 'try_statement':
                    in_try_catch = True
                    break
                parent = parent.parent

            # Check if followed by .catch()
            has_catch = False
            if node.parent and node.parent.type == 'call_expression':
                # Check for .catch() chain
                next_sibling = node.parent.next_sibling
                if next_sibling and 'catch' in source_code[next_sibling.start_byte:next_sibling.end_byte].decode('utf-8'):
                    has_catch = True

            if not in_try_catch and not has_catch:
                violations.append({
                    'line': node.start_point[0] + 1,
                    'column': node.start_point[1],
                    'code': source_code[node.start_byte:node.end_byte].decode('utf-8')
                })

        for child in node.children:
            visit_node(child)

    visit_node(tree.root_node)
    return violations


def detect_xss_in_jsx(tree, source_code: str) -> List[Dict]:
    """
    Detect dangerouslySetInnerHTML usage in JSX.

    Pattern: <div dangerouslySetInnerHTML={{__html: userInput}} />
    """
    violations = []

    def visit_node(node):
        # Look for jsx_attribute with name "dangerouslySetInnerHTML"
        if node.type == 'jsx_attribute':
            name_node = node.child_by_field_name('name')
            if name_node:
                name = source_code[name_node.start_byte:name_node.end_byte].decode('utf-8')
                if name == 'dangerouslySetInnerHTML':
                    violations.append({
                        'line': node.start_point[0] + 1,
                        'column': node.start_point[1],
                        'code': source_code[node.start_byte:node.end_byte].decode('utf-8')
                    })

        for child in node.children:
            visit_node(child)

    visit_node(tree.root_node)
    return violations


def detect_missing_null_check(tree, source_code: str) -> List[Dict]:
    """
    Detect optional chaining violations.

    Pattern: obj.prop without obj?.prop when obj can be null
    """
    violations = []

    def visit_node(node):
        # Look for member_expression without optional chaining
        if node.type == 'member_expression':
            # Check if using optional chaining
            operator = node.child_by_field_name('operator')
            if operator:
                op_text = source_code[operator.start_byte:operator.end_byte].decode('utf-8')
                if op_text == '.':
                    # Regular member access - potential issue
                    # This is a heuristic - would need type info for accuracy
                    object_node = node.child_by_field_name('object')
                    if object_node:
                        obj_text = source_code[object_node.start_byte:object_node.end_byte].decode('utf-8')
                        # Flag if object name suggests it could be null
                        if any(keyword in obj_text.lower() for keyword in ['optional', 'maybe', 'nullable']):
                            violations.append({
                                'line': node.start_point[0] + 1,
                                'column': node.start_point[1],
                                'code': source_code[node.start_byte:node.end_byte].decode('utf-8')
                            })

        for child in node.children:
            visit_node(child)

    visit_node(tree.root_node)
    return violations


def detect_react_hooks_violations(tree, source_code: str) -> List[Dict]:
    """
    Detect React Hooks rules violations.

    Patterns:
    - Hooks called conditionally
    - Hooks called in loops
    - Hooks called in nested functions
    """
    violations = []

    def visit_node(node, in_condition=False, in_loop=False):
        # Detect hook calls (functions starting with 'use')
        if node.type == 'call_expression':
            function_node = node.child_by_field_name('function')
            if function_node and function_node.type == 'identifier':
                func_name = source_code[function_node.start_byte:function_node.end_byte].decode('utf-8')
                if func_name.startswith('use') and func_name[3:4].isupper():
                    # This is a hook call
                    if in_condition:
                        violations.append({
                            'line': node.start_point[0] + 1,
                            'column': node.start_point[1],
                            'code': source_code[node.start_byte:node.end_byte].decode('utf-8'),
                            'reason': 'Hook called conditionally'
                        })
                    elif in_loop:
                        violations.append({
                            'line': node.start_point[0] + 1,
                            'column': node.start_point[1],
                            'code': source_code[node.start_byte:node.end_byte].decode('utf-8'),
                            'reason': 'Hook called in loop'
                        })

        # Track if we're in a condition or loop
        new_in_condition = in_condition or node.type in ['if_statement', 'conditional_expression']
        new_in_loop = in_loop or node.type in ['for_statement', 'while_statement', 'do_statement']

        for child in node.children:
            visit_node(child, new_in_condition, new_in_loop)

    visit_node(tree.root_node)
    return violations


def scan_js_file(file_path: str) -> Dict:
    """
    Scan JS/TS file for all AST-based patterns.

    Returns: Dict with pattern violations
    """
    tree = parse_js_file(file_path)

    if not tree:
        return {'error': f'Failed to parse {file_path}'}

    with open(file_path, 'rb') as f:
        source_code = f.read()

    return {
        'unhandled_promises': detect_unhandled_promise(tree, source_code),
        'xss_in_jsx': detect_xss_in_jsx(tree, source_code),
        'missing_null_checks': detect_missing_null_check(tree, source_code),
        'react_hooks_violations': detect_react_hooks_violations(tree, source_code)
    }


if __name__ == '__main__':
    import argparse
    import json

    parser = argparse.ArgumentParser(description='Scan JS/TS file with AST detectors')
    parser.add_argument('file', help='JS/TS file to scan')
    parser.add_argument('--json', action='store_true', help='Output as JSON')

    args = parser.parse_args()

    results = scan_js_file(args.file)

    if args.json:
        print(json.dumps(results, indent=2))
    else:
        print(f"Scanning {args.file}...")
        for pattern_type, violations in results.items():
            if violations:
                print(f"\n{pattern_type}: {len(violations)} violations")
                for v in violations[:5]:  # Show first 5
                    print(f"  Line {v['line']}: {v.get('code', '')[:60]}")
