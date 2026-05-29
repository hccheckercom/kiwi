"""Kiwi Agent CLI."""

import argparse
import json
import os
import sys

from .loop import run_agent, run_lite, run_multi_agent


def main():
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

    parser = argparse.ArgumentParser(
        description="Kiwi Agent — autonomous code quality scanner",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""Examples:
  python -m agent.cli wezone-plugins --init                     # One-shot project onboarding
  python -m agent.cli wezone-plugins --lite                     # Zero-token scan+fix preview
  python -m agent.cli wezone-plugins --lite --apply             # Zero-token auto-fix
  python -m agent.cli wezone-plugins --mode review              # Claude-powered analysis
  python -m agent.cli D:\\projects\\wezone\\themes\\x --mode auto  # Claude-powered auto-fix""",
    )
    parser.add_argument("path", help="Project path or name from _meta.json")
    parser.add_argument("--init", action="store_true",
                        help="Onboard project: detect stack → mine → review → seed scan → learn → anchor + hook")
    parser.add_argument("--no-anchor", action="store_true",
                        help="With --init: skip writing CLAUDE.md/AGENTS.md anchor block")
    parser.add_argument("--cursor", action="store_true",
                        help="With --init: also write .cursor/rules/kiwi.mdc")
    parser.add_argument("--windsurf", action="store_true",
                        help="With --init: also write .windsurfrules")
    parser.add_argument("--lite", action="store_true", help="Lite mode: scan+fix locally, zero API tokens")
    parser.add_argument("--multi-agent", action="store_true", help="Multi-agent mode: spawn specialized agents")
    parser.add_argument("--agents", nargs="+", help="Agent types to spawn (security, performance, architecture, compliance)")
    parser.add_argument("--apply", action="store_true", help="With --lite: apply fixes (default: dry-run preview)")
    parser.add_argument("--mode", choices=["review", "interactive", "auto"], default="review")
    parser.add_argument("--severity", choices=["CRITICAL", "HIGH", "SUGGEST", "ALL"], default="CRITICAL")
    parser.add_argument("--max-iterations", type=int, default=3)
    parser.add_argument("--max-fixes", type=int, default=10)
    parser.add_argument("--model", default=None, help="Override model (e.g. claude-sonnet-4-6)")
    parser.add_argument("--json", action="store_true", dest="json_mode")
    parser.add_argument("--verbose", "-v", action="store_true")

    args = parser.parse_args()

    resolved = _resolve_path(args.path)

    if args.init:
        from .init_pipeline import run_init, format_init_report

        report = run_init(
            project_path=resolved,
            write_anchor=not args.no_anchor,
            write_cursor=args.cursor,
            write_windsurf=args.windsurf,
            assume_yes=True,
            verbose=args.verbose or not args.json_mode,
        )
        if args.json_mode:
            print(json.dumps(report, indent=2, ensure_ascii=False))
        else:
            print(format_init_report(report))
        sys.exit(0 if report.get("ok") else 1)

    if args.multi_agent:
        report = run_multi_agent(
            path=resolved,
            mode=args.mode,
            agent_types=args.agents,
            severity=args.severity,
            max_fixes=args.max_fixes,
            verbose=args.verbose,
        )
    elif args.lite:
        report = run_lite(
            path=resolved,
            severity=args.severity,
            max_fixes=args.max_fixes,
            dry_run=not args.apply,
            verbose=args.verbose,
        )
    else:
        report = run_agent(
            path=resolved,
            mode=args.mode,
            severity=args.severity,
            max_iterations=args.max_iterations,
            max_fixes=args.max_fixes,
            model=args.model,
            verbose=args.verbose,
        )

    if args.json_mode:
        print(json.dumps(report, indent=2, ensure_ascii=False))
    else:
        _print_report(report)


def _resolve_path(path_or_name: str) -> str:
    if os.path.isdir(path_or_name):
        return os.path.abspath(path_or_name)

    meta_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "_meta.json")
    if os.path.isfile(meta_path):
        try:
            import json as j
            with open(meta_path, encoding="utf-8") as f:
                meta = j.load(f)
            resolved = meta.get("projects", {}).get(path_or_name)
            if resolved and os.path.isdir(resolved):
                return resolved
        except Exception as e:
            print(f"WARNING: Failed to load _meta.json: {e}", file=sys.stderr)

    print(f"WARNING: '{path_or_name}' not found as directory or in _meta.json, using as-is", file=sys.stderr)
    return path_or_name


def _print_report(report: dict):
    print("=" * 60)
    print("  KIWI AGENT REPORT")
    print("=" * 60)
    print(f"  Mode:       {report['mode']}")
    print(f"  Path:       {report['path']}")
    print(f"  Scans:      {report['scans']}")
    print(f"  Duration:   {report['elapsed_seconds']}s")
    print()
    print(f"  Violations found:     {report['violations_found']}")
    print(f"  Fixes applied:        {report['fixes_applied']}")
    print(f"  Fixes failed:         {report['fixes_failed']}")
    print(f"  Violations remaining: {report['violations_remaining']}")
    print()

    if report.get("history"):
        print("  History:")
        for h in report["history"]:
            detail = f" — {h['detail']}" if h.get("detail") else ""
            print(f"    [{h['action']}]{detail}")
        print()

    if report.get("final_message"):
        print("-" * 60)
        print(report["final_message"])
        print("-" * 60)


if __name__ == "__main__":
    main()