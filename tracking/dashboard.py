"""Dashboard — formatted output for CLI and MCP tool."""

import sys
import json
from pathlib import Path

_KIWI_DIR = Path(__file__).parent.parent
if str(_KIWI_DIR) not in sys.path:
    sys.path.insert(0, str(_KIWI_DIR))

from tracking.savings import get_savings


def format_compact(data: dict) -> str:
    t = data["totals"]
    period = data["period"]

    lines = [
        f"Kiwi Savings (this {period})",
        "━" * 30,
        f"Operations: {t['total_ops']} ({t['local_rate_pct']}% local)",
        f"Saved: ${t['saved_usd']:.2f} / ${t['baseline_usd']:.2f} baseline ({t['savings_pct']:.1f}% savings)",
        f"Local tokens: {t['tokens_local']:,} | Baseline tokens: {t['tokens_baseline']:,}",
    ]

    ops = data["by_operation"]
    if ops:
        lines.append("")
        lines.append("Top operations:")
        for op in ops[:5]:
            lines.append(f"  {op['operation']}: {op['ops']} ops, saved ${op['saved_usd']:.2f}")

    return "\n".join(lines)


def format_detail(data: dict) -> str:
    lines = [format_compact(data)]

    daily = data["daily"]
    if daily:
        lines.append("")
        lines.append("Daily breakdown:")
        lines.append(f"  {'Day':<12} {'Ops':>5} {'Saved':>8}")
        lines.append(f"  {'-'*12} {'-'*5} {'-'*8}")
        for d in daily:
            lines.append(f"  {d['day']:<12} {d['ops']:>5} ${d['saved_usd']:>6.2f}")

    ops = data["by_operation"]
    if ops:
        lines.append("")
        lines.append("Per-operation breakdown:")
        lines.append(f"  {'Operation':<12} {'Ops':>5} {'Saved':>8} {'Tokens':>10}")
        lines.append(f"  {'-'*12} {'-'*5} {'-'*8} {'-'*10}")
        for op in ops:
            lines.append(
                f"  {op['operation']:<12} {op['ops']:>5} ${op['saved_usd']:>6.2f} {op['tokens_baseline']:>10,}"
            )

    return "\n".join(lines)


def format_json(data: dict) -> str:
    return json.dumps(data, indent=2)


def dashboard(period: str = "week", detail: bool = False, as_json: bool = False) -> str:
    data = get_savings(period=period)
    if as_json:
        return format_json(data)
    if detail:
        return format_detail(data)
    return format_compact(data)


def main():
    import argparse

    parser = argparse.ArgumentParser(description="Kiwi Usage Dashboard")
    parser.add_argument("--period", choices=["today", "week", "month", "all"], default="week")
    parser.add_argument("--detail", action="store_true")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    print(dashboard(period=args.period, detail=args.detail, as_json=args.json))


if __name__ == "__main__":
    main()