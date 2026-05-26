"""Post-write check: Scan file immediately after Write/Edit on code files."""
import sys
import json
import subprocess
from pathlib import Path

def main():
    # Read hook input from stdin
    try:
        data = json.load(sys.stdin)
    except json.JSONDecodeError:
        sys.exit(0)  # Allow if can't parse

    # Extract file path from tool input
    tool_input = data.get("tool_input", {})
    file_path = tool_input.get("file_path", "")

    if not file_path:
        sys.exit(0)  # Allow if no file path

    # Check if code file
    CODE_EXTENSIONS = (".php", ".css", ".js", ".ts", ".tsx", ".jsx")
    if not file_path.endswith(CODE_EXTENSIONS):
        sys.exit(0)  # Allow non-code files

    # Run kiwi_check via MCP
    kiwi_dir = Path(__file__).parent.parent
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            f"import sys; sys.path.insert(0, r'{kiwi_dir}'); "
            f"from agent.guardrail import check_file, format_result; "
            f"r = check_file(r'{file_path}', severity='CRITICAL'); "
            f"print(format_result(r) if format_result(r) else 'PASS')"
        ],
        capture_output=True,
        text=True,
        timeout=30
    )

    output = result.stdout.strip()

    # Check for violations
    if "BLOCK" in output or "CRITICAL" in output:
        print(f"\n⛔ KIWI BLOCK: {file_path}")
        print(output)
        print("\nFix violations before continuing.")
        sys.exit(2)  # Exit code 2 = block with feedback

    sys.exit(0)  # Allow

if __name__ == "__main__":
    main()