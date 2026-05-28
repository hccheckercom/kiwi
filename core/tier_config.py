"""Tier definitions — pure data, no I/O."""

from dataclasses import dataclass, field
from typing import Optional, Union


TIER_LIMITS = {
    "free": {
        "max_patterns": 30,
        "max_conventions": 5,
        "trust_cap": 0.6,
        "code_generation": False,
        "cross_project": False,
        "session_learning": False,
        "max_scans_day": 20,
        "agent_mode": False,
    },
    "starter": {
        "max_patterns": 200,
        "max_conventions": 20,
        "trust_cap": 0.8,
        "code_generation": "skeleton",
        "cross_project": False,
        "session_learning": "basic",
        "max_scans_day": 100,
        "agent_mode": "review",
    },
    "pro": {
        "max_patterns": None,
        "max_conventions": None,
        "trust_cap": 1.0,
        "code_generation": "full",
        "cross_project": True,
        "session_learning": "full",
        "max_scans_day": None,
        "agent_mode": "auto",
    },
}

TIER_ORDER = ["free", "starter", "pro"]

FREE_TOOLS = {
    "kiwi_check", "kiwi_context", "kiwi_query", "kiwi_lesson",
    "kiwi_stats", "kiwi_fix", "kiwi_template", "kiwi_tier",
    "kiwi_confidence", "kiwi_dismiss", "kiwi_dashboard",
}

GATED_TOOLS = {
    "kiwi_scan": "max_scans_day",
    "kiwi_agent": "agent_mode",
    "kiwi_learn_session": "session_learning",
    "kiwi_learn_from_folder": "max_patterns",
    "kiwi_mine_patterns": "max_patterns",
}

GRACE_PERIOD_DAYS = 7


@dataclass
class TierConfig:
    name: str
    limits: dict = field(default_factory=dict)
    resolved_from: str = "default"

    def get_limit(self, key: str) -> Optional[Union[int, float, bool, str]]:
        return self.limits.get(key)

    def is_unlimited(self, key: str) -> bool:
        return self.limits.get(key) is None

    def next_tier(self) -> Optional[str]:
        idx = TIER_ORDER.index(self.name) if self.name in TIER_ORDER else -1
        if idx < len(TIER_ORDER) - 1:
            return TIER_ORDER[idx + 1]
        return None


def get_tier_config(tier_name: str) -> TierConfig:
    if tier_name not in TIER_LIMITS:
        tier_name = "free"
    return TierConfig(
        name=tier_name,
        limits=TIER_LIMITS[tier_name].copy(),
    )