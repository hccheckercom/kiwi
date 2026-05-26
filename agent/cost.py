"""Cost tracking for Kiwi Agent runs."""

import time
from dataclasses import dataclass
from typing import Optional


# Pricing per 1M tokens (as of 2026-05)
PRICING = {
    "claude-opus-4-7": {
        "input": 15.00,
        "output": 75.00,
        "cache_write": 18.75,
        "cache_read": 1.50,
    },
    "claude-sonnet-4-6": {
        "input": 3.00,
        "output": 15.00,
        "cache_write": 3.75,
        "cache_read": 0.30,
    },
    "claude-haiku-4-5": {
        "input": 0.80,
        "output": 4.00,
        "cache_write": 1.00,
        "cache_read": 0.08,
    },
}


@dataclass
class TokenUsage:
    """Token usage for a single API call."""
    input_tokens: int = 0
    output_tokens: int = 0
    cache_creation_tokens: int = 0
    cache_read_tokens: int = 0


@dataclass
class CostSummary:
    """Cost summary for an agent run."""
    model: str
    total_tokens: int
    input_tokens: int
    output_tokens: int
    cache_creation_tokens: int
    cache_read_tokens: int
    total_cost_usd: float
    input_cost_usd: float
    output_cost_usd: float
    cache_write_cost_usd: float
    cache_read_cost_usd: float
    api_calls: int
    duration_seconds: float


class CostTracker:
    """Track token usage and costs for agent runs."""

    def __init__(self, model: str):
        self.model = model
        self.api_calls = 0
        self.total_input = 0
        self.total_output = 0
        self.total_cache_write = 0
        self.total_cache_read = 0
        self.start_time = time.time()

    def add_usage(self, usage: TokenUsage):
        """Add token usage from an API call."""
        self.api_calls += 1
        self.total_input += usage.input_tokens
        self.total_output += usage.output_tokens
        self.total_cache_write += usage.cache_creation_tokens
        self.total_cache_read += usage.cache_read_tokens

    def get_summary(self) -> CostSummary:
        """Calculate cost summary."""
        duration = time.time() - self.start_time
        pricing = PRICING.get(self.model, PRICING["claude-sonnet-4-6"])

        # Calculate costs (pricing is per 1M tokens)
        input_cost = (self.total_input / 1_000_000) * pricing["input"]
        output_cost = (self.total_output / 1_000_000) * pricing["output"]
        cache_write_cost = (self.total_cache_write / 1_000_000) * pricing["cache_write"]
        cache_read_cost = (self.total_cache_read / 1_000_000) * pricing["cache_read"]
        total_cost = input_cost + output_cost + cache_write_cost + cache_read_cost

        total_tokens = (
            self.total_input
            + self.total_output
            + self.total_cache_write
            + self.total_cache_read
        )

        return CostSummary(
            model=self.model,
            total_tokens=total_tokens,
            input_tokens=self.total_input,
            output_tokens=self.total_output,
            cache_creation_tokens=self.total_cache_write,
            cache_read_tokens=self.total_cache_read,
            total_cost_usd=total_cost,
            input_cost_usd=input_cost,
            output_cost_usd=output_cost,
            cache_write_cost_usd=cache_write_cost,
            cache_read_cost_usd=cache_read_cost,
            api_calls=self.api_calls,
            duration_seconds=duration,
        )

    def format_summary(self) -> str:
        """Format cost summary as human-readable string."""
        summary = self.get_summary()

        lines = [
            f"Cost Summary ({summary.model})",
            f"Duration: {summary.duration_seconds:.1f}s",
            f"API calls: {summary.api_calls}",
            "",
            "Tokens:",
            f"  Input: {summary.input_tokens:,}",
            f"  Output: {summary.output_tokens:,}",
            f"  Cache write: {summary.cache_creation_tokens:,}",
            f"  Cache read: {summary.cache_read_tokens:,}",
            f"  Total: {summary.total_tokens:,}",
            "",
            "Cost (USD):",
            f"  Input: ${summary.input_cost_usd:.4f}",
            f"  Output: ${summary.output_cost_usd:.4f}",
            f"  Cache write: ${summary.cache_write_cost_usd:.4f}",
            f"  Cache read: ${summary.cache_read_cost_usd:.4f}",
            f"  Total: ${summary.total_cost_usd:.4f}",
        ]

        return "\n".join(lines)
