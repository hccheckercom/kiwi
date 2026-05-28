"""R4 — Adaptive Brief: trust score → brief depth adjustment."""

from dataclasses import dataclass


@dataclass
class BriefConfig:
    max_files: int
    include_spec: bool
    include_examples: bool
    include_warnings: bool
    include_style_hints: bool
    verbosity: str  # "minimal", "standard", "detailed"


TRUST_TIERS = {
    "high": {"min": 0.75, "config": BriefConfig(
        max_files=5, include_spec=False, include_examples=False,
        include_warnings=False, include_style_hints=True, verbosity="minimal"
    )},
    "medium": {"min": 0.50, "config": BriefConfig(
        max_files=10, include_spec=True, include_examples=False,
        include_warnings=True, include_style_hints=True, verbosity="standard"
    )},
    "low": {"min": 0.0, "config": BriefConfig(
        max_files=15, include_spec=True, include_examples=True,
        include_warnings=True, include_style_hints=True, verbosity="detailed"
    )},
}


def get_brief_config(trust_score: float) -> BriefConfig:
    """Trust score → BriefConfig. Higher trust = less verbose brief."""
    for tier_name in ("high", "medium", "low"):
        tier = TRUST_TIERS[tier_name]
        if trust_score >= tier["min"]:
            return tier["config"]
    return TRUST_TIERS["low"]["config"]


def apply_adaptive_depth(context, trust_score: float) -> BriefConfig:
    """Mutate AssembledContext based on trust-driven config."""
    config = get_brief_config(trust_score)

    if len(context.files_needed) > config.max_files:
        context.files_needed = context.files_needed[:config.max_files]

    if not config.include_spec:
        context.spec = None

    if not config.include_examples:
        context.reference_pages = []

    return config