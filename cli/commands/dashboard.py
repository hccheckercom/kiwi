"""kiwi dashboard — show usage metrics and savings."""

import click

from ..helpers import ensure_sys_path, print_header


@click.command()
@click.option("--period", type=click.Choice(["day", "week", "month"]), default="week")
@click.option("--detail", is_flag=True, help="Show detailed breakdown")
@click.option("--json-output", "--json", "json_out", is_flag=True, help="Output as JSON")
def dashboard(period, detail, json_out):
    """Show Kiwi usage metrics and cost savings."""
    ensure_sys_path()

    from tracking.dashboard import format_compact, format_detail
    from tracking.savings import get_savings

    data = get_savings(period=period)

    if json_out:
        import json
        click.echo(json.dumps(data, indent=2, ensure_ascii=False, default=str))
    elif detail:
        click.echo(format_detail(data))
    else:
        click.echo(format_compact(data))