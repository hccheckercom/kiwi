"""Context-aware upgrade messages — show value of upgrading."""

from typing import Optional


_TEMPLATES = {
    "max_patterns": (
        "Pattern limit reached ({current}/{limit}). "
        "Found new patterns but can't learn them. "
        "Upgrade to {next_tier} for {next_limit} patterns."
    ),
    "max_conventions": (
        "Convention limit reached ({current}/{limit}). "
        "Upgrade to {next_tier} for {next_limit} conventions."
    ),
    "max_scans_day": (
        "Daily scan limit reached ({current}/{limit}). "
        "Upgrade to {next_tier} for {next_limit}/day."
    ),
    "code_generation": (
        "Code generation requires {next_tier} tier."
    ),
    "cross_project": (
        "Cross-project analysis requires Pro tier."
    ),
    "session_learning": (
        "Session learning requires {next_tier} tier."
    ),
    "agent_mode": (
        "Agent mode requires {next_tier} tier."
    ),
}

_NEXT_LIMITS = {
    "starter": {
        "max_patterns": 200,
        "max_conventions": 20,
        "max_scans_day": 100,
    },
    "pro": {
        "max_patterns": "unlimited",
        "max_conventions": "unlimited",
        "max_scans_day": "unlimited",
    },
}


def get_upgrade_prompt(
    feature: str,
    current_count: int = 0,
    limit: Optional[int] = None,
    next_tier: Optional[str] = None,
) -> str:
    """Generate context-aware upgrade message."""
    if not next_tier:
        next_tier = "starter"

    template = _TEMPLATES.get(feature, "Feature '{feature}' requires upgrade to {next_tier}.")

    next_limit = "unlimited"
    if next_tier in _NEXT_LIMITS and feature in _NEXT_LIMITS[next_tier]:
        next_limit = _NEXT_LIMITS[next_tier][feature]

    msg = template.format(
        current=current_count,
        limit=limit or "?",
        next_tier=next_tier.capitalize(),
        next_limit=next_limit,
        feature=feature,
    )

    savings_line = _get_savings_estimate(feature, next_tier)
    if savings_line:
        msg += f"\n{savings_line}"

    msg += f"\nRun: kiwi_tier(action='status') to see your usage."
    return msg


def _get_savings_estimate(feature: str, next_tier: str) -> str:
    """Try to estimate savings from upgrade using A4 tracking data."""
    try:
        from tracking.savings import get_savings
        data = get_savings("week")
        totals = data.get("totals", {})
        saved_week = totals.get("saved_usd", 0)

        if saved_week <= 0:
            return ""

        multiplier = {"starter": 3, "pro": 6}.get(next_tier, 2)
        estimated = saved_week * multiplier

        return f"You saved ${saved_week:.2f} this week. {next_tier.capitalize()} could save ~${estimated:.2f}/week."
    except Exception:
        return ""


def format_tier_status(tier_name: str, counts: dict, limits: dict) -> str:
    """Format tier status for kiwi_tier tool output."""
    lines = [
        f"Kiwi Tier: {tier_name.upper()}",
        "=" * 30,
    ]

    usage_items = [
        ("Patterns learned", counts.get("patterns_learned", 0), limits.get("max_patterns")),
        ("Conventions", counts.get("conventions_learned", 0), limits.get("max_conventions")),
        ("Scans today", counts.get("scans_today", 0), limits.get("max_scans_day")),
    ]

    for label, current, limit in usage_items:
        if limit is None:
            lines.append(f"  {label}: {current} (unlimited)")
        else:
            pct = int(current / limit * 100) if limit > 0 else 0
            bar = _progress_bar(pct)
            lines.append(f"  {label}: {current}/{limit} {bar}")

    bool_features = [
        ("Code generation", limits.get("code_generation")),
        ("Cross-project", limits.get("cross_project")),
        ("Session learning", limits.get("session_learning")),
        ("Agent mode", limits.get("agent_mode")),
    ]

    lines.append("")
    lines.append("Features:")
    for label, value in bool_features:
        if value is False:
            lines.append(f"  {label}: locked")
        elif value is True:
            lines.append(f"  {label}: full")
        else:
            lines.append(f"  {label}: {value}")

    return "\n".join(lines)


def _progress_bar(pct: int, width: int = 10) -> str:
    filled = int(width * min(pct, 100) / 100)
    empty = width - filled
    if pct >= 90:
        return f"[{'#' * filled}{'.' * empty}] {pct}% !"
    return f"[{'#' * filled}{'.' * empty}] {pct}%"