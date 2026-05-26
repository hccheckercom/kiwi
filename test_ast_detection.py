#!/usr/bin/env python3
"""Test AST detection on unhandled-promise-demo.ts"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from learning.js_ast_detector import parse_js_file, detect_unhandled_promise

test_file = Path(__file__).parent.parent.parent / "webstore-vn" / "unhandled-promise-demo.ts"

print(f"Testing: {test_file}")
print(f"File exists: {test_file.exists()}")

if not test_file.exists():
    print("ERROR: Test file not found")
    sys.exit(1)

tree = parse_js_file(str(test_file))
if not tree:
    print("ERROR: Failed to parse file")
    sys.exit(1)

print(f"Parsed successfully. Root node: {tree.root_node.type}")

with open(test_file, 'rb') as f:
    source = f.read()

violations = detect_unhandled_promise(tree, source)

print(f"\nViolations found: {len(violations)}")
for v in violations:
    print(f"  Line {v['line']}: {v['code'][:80]}")

if len(violations) == 0:
    print("\nERROR: Expected 1 violation (line 3: await fetch without try/catch)")
    print("Debugging AST structure...")

    def print_awaits(node, indent=0):
        if node.type == 'await_expression':
            print(f"{'  ' * indent}await_expression at line {node.start_point[0] + 1}")
            parent = node.parent
            while parent:
                print(f"{'  ' * (indent+1)}parent: {parent.type}")
                if parent.type == 'try_statement':
                    print(f"{'  ' * (indent+2)}FOUND try_statement!")
                    break
                parent = parent.parent
        for child in node.children:
            print_awaits(child, indent + 1)

    print_awaits(tree.root_node)
else:
    print("\nSUCCESS: AST detection working!")
