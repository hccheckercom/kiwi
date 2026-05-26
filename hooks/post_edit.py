#!/usr/bin/env python3
"""Kiwi post-edit hook — instant guardrail check after each file edit."""

import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def main():
    tool_input = os.environ.get("TOOL_INPUT", "")
    if not tool_input:
        return

    try:
        data = json.loads(tool_input)
    except json.JSONDecodeError:
        return

    file_path = data.get("file_path", "")
    if not file_path:
        return

    if not any(file_path.endswith(ext) for ext in (".php", ".css", ".js", ".jsx", ".tsx", ".ts")):
        return

    from agent.guardrail import check_file, format_result

    result = check_file(file_path, severity="CRITICAL")
    output = format_result(result)
    if output:
        print("\n" + "="*70)
        print("⛔ KIWI POST-EDIT BLOCK")
        print("="*70)
        print(output)
        print("\n💡 Cách fix:")
        print("   1. Đọc violation details ở trên")
        print("   2. Gọi: kiwi_fix(lesson_id='...', file='...', apply=false) để preview")
        print("   3. Nếu OK → kiwi_fix(..., apply=true) để apply")
        print("   4. Hoặc fix thủ công theo Good example trong lesson")
        print("="*70 + "\n")


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"[kiwi] post_edit hook error: {e}", file=sys.stderr)
