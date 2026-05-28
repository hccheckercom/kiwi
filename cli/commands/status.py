"""kiwi status — quick summary of tier, patterns, savings."""

import click

from ..helpers import ensure_sys_path, print_header
from .. import __version__


@click.command()
@click.option("--json-output", "--json", "json_out", is_flag=True, help="Output as JSON")
def status(json_out):
    """Show Kiwi status: tier, patterns, savings."""
    ensure_sys_path()

    from core.tier_manager import get_tier_manager
    from tracking.savings import get_savings

    tm = get_tier_manager()
    tier = tm.resolve_tier()

    savings_data = get_savings(period="week")
    totals = savings_data.get("totals", {})

    info = {
        "version": __version__,
        "tier": tier.name,
        "resolved_from": tier.resolved_from,
        "savings_week_usd": totals.get("saved_usd", 0),
        "savings_pct": totals.get("savings_pct", 0),
        "ops_today": totals.get("total_ops", 0),
    }

    if json_out:
        import json
        click.echo(json.dumps(info, indent=2))
    else:
        click.echo(f"Kiwi AI v{__version__} — {tier.name.capitalize()} tier ({tier.resolved_from})")
        click.echo("━" * 30)
        click.echo(f"Savings: ${totals.get('saved_usd', 0):.2f} this week ({totals.get('savings_pct', 0):.1f}% reduction)")
        click.echo(f"Operations: {totals.get('total_ops', 0)} this week")

        if tier.name == "free":
            click.echo("")
            click.echo("Upgrade: kiwi upgrade starter")