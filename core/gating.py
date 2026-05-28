"""Gate enforcement — decorator + inline check for tier limits."""

import functools
from dataclasses import dataclass
from typing import Optional

from .tier_config import GATED_TOOLS
from .tier_manager import get_tier_manager


@dataclass
class GateResult:
    allowed: bool
    feature: str
    message: str = ""
    current_count: int = 0
    limit: Optional[int] = None
    upgrade_tier: Optional[str] = None


def gate_check(feature: str, current_count: int = 0) -> GateResult:
    """Check if a feature is allowed under current tier."""
    mgr = get_tier_manager()

    if mgr.is_dev_mode():
        return GateResult(allowed=True, feature=feature)

    result = mgr.check_limit(feature, current_count)

    if result["allowed"]:
        return GateResult(
            allowed=True,
            feature=feature,
            current_count=current_count,
            limit=result["limit"],
        )

    tier = mgr.get_current_tier()
    next_tier = tier.next_tier()

    from .upgrade_prompts import get_upgrade_prompt
    message = get_upgrade_prompt(feature, current_count, result["limit"], next_tier)

    return GateResult(
        allowed=False,
        feature=feature,
        message=message,
        current_count=current_count,
        limit=result["limit"],
        upgrade_tier=next_tier,
    )


def gate_tool(tool_name: str) -> GateResult:
    """Check if an MCP tool is allowed under current tier."""
    if tool_name not in GATED_TOOLS:
        return GateResult(allowed=True, feature=tool_name)

    feature = GATED_TOOLS[tool_name]
    mgr = get_tier_manager()

    if mgr.is_dev_mode():
        return GateResult(allowed=True, feature=feature)

    counts = mgr.get_usage_counts()

    count_map = {
        "max_scans_day": counts.get("scans_today", 0),
        "max_patterns": counts.get("patterns_learned", 0),
        "max_conventions": counts.get("conventions_learned", 0),
    }

    current = count_map.get(feature, 0)
    return gate_check(feature, current)


def gated(feature: str):
    """Decorator that blocks function execution if tier limit exceeded."""
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            mgr = get_tier_manager()
            if mgr.is_dev_mode():
                return func(*args, **kwargs)

            counts = mgr.get_usage_counts()
            count_map = {
                "max_patterns": counts.get("patterns_learned", 0),
                "max_conventions": counts.get("conventions_learned", 0),
                "max_scans_day": counts.get("scans_today", 0),
            }
            current = count_map.get(feature, 0)

            result = gate_check(feature, current)
            if not result.allowed:
                return {"gated": True, "message": result.message,
                        "feature": feature, "upgrade_tier": result.upgrade_tier}

            return func(*args, **kwargs)
        return wrapper
    return decorator