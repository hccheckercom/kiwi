#!/usr/bin/env python3
"""Kiwi — Unified CLI for bug scanning, agent, and deployment.

Usage:
    kiwi scan <path> [--severity CRITICAL]
    kiwi agent <path> [--mode auto]
    kiwi deploy <path> --type wp_theme
    kiwi check <file>
    kiwi mcp  # Start MCP server for Claude Code
"""

import sys
import os
from pathlib import Path

# Add kiwi directory to path
KIWI_DIR = Path(__file__).parent
if str(KIWI_DIR) not in sys.path:
    sys.path.insert(0, str(KIWI_DIR))

# Ensure UTF-8 encoding
if sys.platform == "win32":
    os.environ["PYTHONUTF8"] = "1"
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")


def main():
    """Main CLI entry point."""
    import argparse

    parser = argparse.ArgumentParser(
        prog="kiwi",
        description="Kiwi — Autonomous Code Quality Agent",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Commands:
  scan      Scan project for violations
  agent     Run autonomous agent loop
  deploy    Deploy to VPS
  check     Quick check single file
  mcp       Start MCP server for Claude Code

Examples:
  kiwi scan wezone-plugins --severity CRITICAL
  kiwi agent wezone-plugins --lite
  kiwi deploy themes/sfvn --type wp_theme
  kiwi check src/Plugin.php
  kiwi mcp
        """
    )

    parser.add_argument("command", choices=["scan", "agent", "deploy", "check", "mcp"],
                       help="Command to run")
    parser.add_argument("args", nargs="*", help="Command arguments")

    args, unknown = parser.parse_known_args()

    # Reconstruct argv for subcommands
    sys.argv = [f"kiwi-{args.command}"] + args.args + unknown

    if args.command == "scan":
        # Convert positional path to --project flag for scanner
        if args.args and not args.args[0].startswith('--'):
            sys.argv = [f"kiwi-scan", "--project", args.args[0]] + args.args[1:] + unknown
        else:
            sys.argv = [f"kiwi-scan"] + args.args + unknown

        from scanner.cli import main as scanner_main
        scanner_main()

    elif args.command == "agent":
        from agent.cli import main as agent_main
        agent_main()

    elif args.command == "deploy":
        from deploy.cli import main as deploy_main
        deploy_main()

    elif args.command == "check":
        _run_check(args.args + unknown)

    elif args.command == "mcp":
        from mcp_server import main as mcp_main
        mcp_main()


def _run_check(args):
    """Quick check single file."""
    import argparse

    parser = argparse.ArgumentParser(prog="kiwi check")
    parser.add_argument("file", help="File to check")
    parser.add_argument("--severity", default="CRITICAL", choices=["CRITICAL", "HIGH", "ALL"])
    parser.add_argument("--platform", choices=["wp", "nextjs"])

    parsed = parser.parse_args(args)

    from agent.guardrail import check_file, format_result

    result = check_file(parsed.file, platform=parsed.platform, severity=parsed.severity)
    output = format_result(result)

    if output:
        print(output)
    else:
        print(f"✅ PASS: {parsed.file} — 0 violations")


if __name__ == "__main__":
    main()