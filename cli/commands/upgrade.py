"""kiwi upgrade — activate license or show upgrade info."""

import click

from ..helpers import ensure_sys_path, print_header, print_success, print_error


@click.command()
@click.argument("tier", type=click.Choice(["starter", "pro"]), required=False)
@click.option("--license", "license_key", help="License key to activate")
def upgrade(tier, license_key):
    """Upgrade tier or activate a license key."""
    ensure_sys_path()

    from core.tier_manager import get_tier_manager
    from core.tier_config import TIER_LIMITS
    from core.upgrade_prompts import format_tier_status

    tm = get_tier_manager()
    current = tm.resolve_tier()

    if license_key:
        success = tm.activate_license(license_key)
        if success:
            new_tier = tm.resolve_tier()
            print_success(f"License activated! Tier: {new_tier.name}")
        else:
            print_error("Invalid license key.")
            raise SystemExit(1)
        return

    if not tier:
        click.echo(format_tier_status())
        return

    # Show what the target tier offers
    print_header(f"Upgrade to {tier.capitalize()}")
    limits = TIER_LIMITS[tier]
    click.echo(f"  Patterns: {'unlimited' if limits['max_patterns'] is None else limits['max_patterns']}")
    click.echo(f"  Scans/day: {'unlimited' if limits['max_scans_day'] is None else limits['max_scans_day']}")
    click.echo(f"  Code generation: {limits['code_generation']}")
    click.echo(f"  Agent mode: {limits['agent_mode']}")
    click.echo(f"  Cross-project: {limits['cross_project']}")
    click.echo("")
    click.echo("To activate: kiwi upgrade --license <your-key>")