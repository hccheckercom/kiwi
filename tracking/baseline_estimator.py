"""Baseline Estimator — compute "cost without Kiwi" for each operation type.

Uses Sonnet pricing as baseline (most users would use Sonnet for these tasks).
Formulas are conservative: under-promise savings, over-deliver.
"""

import sys
from pathlib import Path

_KIWI_DIR = Path(__file__).parent.parent
if str(_KIWI_DIR) not in sys.path:
    sys.path.insert(0, str(_KIWI_DIR))

from agent.cost import PRICING

BASELINE_MODEL = "claude-sonnet-4-6"
_PRICING = PRICING[BASELINE_MODEL]
_INPUT_PER_TOKEN = _PRICING["input"] / 1_000_000
_OUTPUT_PER_TOKEN = _PRICING["output"] / 1_000_000

# tokens/sec estimate for latency calculation
_TOKENS_PER_SEC = 100

# Per-operation baseline formulas: (input_tokens, output_tokens)
OPERATION_FORMULAS = {
    "context": lambda fp, fl: (fp * 200 + 500, 500),
    "check": lambda fp, fl: (max(fl * 4, 400) + 800, 300),
    "scan": lambda fp, fl: (fp * 150 + 2000, 1000),
    "fix": lambda fp, fl: (max(fl * 4, 400) + 1500, 500),
    "fix_apply": lambda fp, fl: (int((max(fl * 4, 400) + 1500) * 1.5), 750),
    "query": lambda fp, fl: (3000, 500),
    "lesson": lambda fp, fl: (1500, 300),
    "template": lambda fp, fl: (2000, 800),
    "agent": lambda fp, fl: (5000, 2000),
    "deploy": lambda fp, fl: (3000, 1000),
    "stats": lambda fp, fl: (1000, 200),
    "dismiss": lambda fp, fl: (800, 200),
    "trends": lambda fp, fl: (2000, 500),
    "confidence": lambda fp, fl: (1500, 300),
    "impact": lambda fp, fl: (2500, 600),
    "dashboard": lambda fp, fl: (500, 200),
}

DEFAULT_FORMULA = lambda fp, fl: (2000, 500)


def estimate_baseline(
    operation: str,
    files_processed: int = 1,
    file_lines: int = 0,
) -> dict:
    """Estimate what this operation would cost without Kiwi.

    Returns dict with tokens, cost_usd, latency_ms.
    """
    formula = OPERATION_FORMULAS.get(operation, DEFAULT_FORMULA)
    fp = max(files_processed, 1)
    fl = max(file_lines, 100)

    input_tokens, output_tokens = formula(fp, fl)
    total_tokens = input_tokens + output_tokens

    cost_usd = (input_tokens * _INPUT_PER_TOKEN) + (output_tokens * _OUTPUT_PER_TOKEN)
    latency_ms = int(total_tokens / _TOKENS_PER_SEC * 1000)

    return {
        "tokens": total_tokens,
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "cost_usd": round(cost_usd, 6),
        "latency_ms": latency_ms,
        "model": BASELINE_MODEL,
    }