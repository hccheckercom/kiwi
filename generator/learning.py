"""Pattern Mining & Confidence Scoring for UI Generator Learning System"""

from pathlib import Path
from typing import Dict, List, Any, Optional
from collections import Counter, defaultdict
import json


class PatternMiner:
    """
    Mine recurring patterns from component detection history.

    Finds patterns with 3+ occurrences and suggests new Kiwi Templates.
    """

    def __init__(self, min_occurrences: int = 3):
        self.min_occurrences = min_occurrences

    def mine_patterns(self, lookback_days: int = 30) -> List[Dict[str, Any]]:
        """
        Find recurring component patterns from feedback history.

        Args:
            lookback_days: How far back to look for patterns

        Returns:
            List of suggested patterns with occurrence counts
        """
        from ..memory.db import get_component_patterns

        # Get all component patterns from last N days
        patterns = get_component_patterns(min_confidence=0.5, limit=1000)

        # Group by component type
        by_type = defaultdict(list)
        for p in patterns:
            by_type[p["component_type"]].append(p)

        suggestions = []

        for comp_type, instances in by_type.items():
            if len(instances) < self.min_occurrences:
                continue

            # Calculate acceptance rate
            with_feedback = [i for i in instances if i["user_accepted"] is not None]
            if not with_feedback:
                continue

            accepted = sum(1 for i in with_feedback if i["user_accepted"])
            acceptance_rate = accepted / len(with_feedback)

            # Only suggest if acceptance rate > 70%
            if acceptance_rate < 0.7:
                continue

            # Find most common HTML patterns
            html_snippets = [i["html_snippet"] for i in instances]
            snippet_counter = Counter(html_snippets)
            most_common = snippet_counter.most_common(1)[0]

            suggestions.append({
                "component_type": comp_type,
                "occurrences": len(instances),
                "acceptance_rate": acceptance_rate,
                "avg_confidence": sum(i["confidence"] for i in instances) / len(instances),
                "example_html": most_common[0],
                "example_count": most_common[1],
                "should_add_to_templates": acceptance_rate >= 0.8 and len(instances) >= 5
            })

        # Sort by occurrences desc
        suggestions.sort(key=lambda x: x["occurrences"], reverse=True)

        return suggestions

    def suggest_new_template(self, pattern: Dict[str, Any]) -> Optional[str]:
        """
        Generate Kiwi Template suggestion from pattern.

        Args:
            pattern: Pattern dict from mine_patterns()

        Returns:
            Template markdown content or None
        """
        if not pattern.get("should_add_to_templates"):
            return None

        comp_type = pattern["component_type"]
        html = pattern["example_html"]

        # Generate template content
        template = f"""---
section: {comp_type}
title: Auto-detected {comp_type.title()} Pattern
tags: [auto-generated, {comp_type}]
confidence: {pattern['avg_confidence']:.2f}
occurrences: {pattern['occurrences']}
acceptance_rate: {pattern['acceptance_rate']:.1%}
---

# Auto-detected {comp_type.title()} Pattern

**Source:** Mined from {pattern['occurrences']} real generations
**Acceptance rate:** {pattern['acceptance_rate']:.1%}
**Avg confidence:** {pattern['avg_confidence']:.2f}

## HTML Pattern

```html
{html[:500]}
```

## Usage

This pattern was automatically detected from user feedback.
Review and refine before adding to production templates.
"""

        return template


class ConfidenceScorer:
    """
    Track accuracy per component type and adjust confidence thresholds dynamically.
    """

    def __init__(self):
        self.default_threshold = 0.7

    def get_component_accuracy(self, component_type: str) -> Dict[str, float]:
        """
        Calculate accuracy metrics for a specific component type.

        Returns:
            Dict with precision, recall, f1_score
        """
        from ..memory.db import get_component_patterns

        patterns = get_component_patterns(component_type=component_type, limit=500)

        # Filter to only patterns with user feedback
        with_feedback = [p for p in patterns if p["user_accepted"] is not None]

        if not with_feedback:
            return {"precision": 0.0, "recall": 0.0, "f1_score": 0.0, "sample_size": 0}

        # True positives: auto-applied AND user accepted
        tp = sum(1 for p in with_feedback if p["auto_applied"] and p["user_accepted"])

        # False positives: auto-applied BUT user rejected
        fp = sum(1 for p in with_feedback if p["auto_applied"] and not p["user_accepted"])

        # False negatives: NOT auto-applied BUT user accepted (should have been applied)
        fn = sum(1 for p in with_feedback if not p["auto_applied"] and p["user_accepted"])

        # True negatives: NOT auto-applied AND user rejected
        tn = sum(1 for p in with_feedback if not p["auto_applied"] and not p["user_accepted"])

        precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
        recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0
        f1_score = 2 * (precision * recall) / (precision + recall) if (precision + recall) > 0 else 0.0

        return {
            "precision": precision,
            "recall": recall,
            "f1_score": f1_score,
            "sample_size": len(with_feedback),
            "tp": tp,
            "fp": fp,
            "fn": fn,
            "tn": tn
        }

    def recommend_threshold(self, component_type: str) -> float:
        """
        Recommend optimal confidence threshold for a component type.

        Uses F1-score optimization to balance precision and recall.
        """
        from ..memory.db import get_component_patterns

        patterns = get_component_patterns(component_type=component_type, limit=500)
        with_feedback = [p for p in patterns if p["user_accepted"] is not None]

        if len(with_feedback) < 10:
            return self.default_threshold

        # Try different thresholds and find best F1
        best_threshold = self.default_threshold
        best_f1 = 0.0

        for threshold in [0.5, 0.6, 0.7, 0.8, 0.9]:
            tp = sum(1 for p in with_feedback if p["confidence"] >= threshold and p["user_accepted"])
            fp = sum(1 for p in with_feedback if p["confidence"] >= threshold and not p["user_accepted"])
            fn = sum(1 for p in with_feedback if p["confidence"] < threshold and p["user_accepted"])

            precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
            recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0
            f1 = 2 * (precision * recall) / (precision + recall) if (precision + recall) > 0 else 0.0

            if f1 > best_f1:
                best_f1 = f1
                best_threshold = threshold

        return best_threshold

    def get_all_thresholds(self) -> Dict[str, float]:
        """Get recommended thresholds for all component types."""
        from ..memory.db import get_pattern_stats

        stats = get_pattern_stats()
        per_component = stats.get("per_component", [])

        thresholds = {}
        for comp in per_component:
            comp_type = comp["component_type"]
            if comp["total_detected"] >= 10:
                thresholds[comp_type] = self.recommend_threshold(comp_type)

        return thresholds

    def should_retrain(self) -> bool:
        """
        Check if ML classifier should be retrained.

        Retrain every 10 generations with feedback.
        """
        from ..memory.db import get_pattern_stats

        stats = get_pattern_stats()
        overall = stats.get("overall", {})
        total = overall.get("total_generations", 0)

        # Retrain every 10 generations
        return total > 0 and total % 10 == 0


def format_pattern_report(patterns: List[Dict[str, Any]]) -> str:
    """Format pattern mining report for MCP tool output."""
    if not patterns:
        return "No recurring patterns found (need 3+ occurrences with 70%+ acceptance rate)"

    lines = [
        "Kiwi UI Generator — Pattern Mining Report",
        "",
        f"Found {len(patterns)} recurring patterns:",
        ""
    ]

    for i, p in enumerate(patterns[:10], 1):
        lines.append(f"{i}. {p['component_type']}")
        lines.append(f"   Occurrences: {p['occurrences']}")
        lines.append(f"   Acceptance rate: {p['acceptance_rate']:.1%}")
        lines.append(f"   Avg confidence: {p['avg_confidence']:.2f}")

        if p["should_add_to_templates"]:
            lines.append(f"   ✓ RECOMMEND: Add to Kiwi Templates")

        lines.append("")

    if len(patterns) > 10:
        lines.append(f"... and {len(patterns) - 10} more patterns")

    return "\n".join(lines)


def format_confidence_report(component_type: Optional[str] = None) -> str:
    """Format confidence scoring report for MCP tool output."""
    scorer = ConfidenceScorer()

    if component_type:
        # Single component report
        accuracy = scorer.get_component_accuracy(component_type)
        threshold = scorer.recommend_threshold(component_type)

        lines = [
            f"Confidence Analysis: {component_type}",
            "",
            f"Sample size: {accuracy['sample_size']} generations with feedback",
            "",
            f"Accuracy Metrics:",
            f"  Precision: {accuracy['precision']:.1%} (of auto-applied, how many were correct)",
            f"  Recall: {accuracy['recall']:.1%} (of correct patterns, how many were auto-applied)",
            f"  F1 Score: {accuracy['f1_score']:.2f}",
            "",
            f"Confusion Matrix:",
            f"  True Positives: {accuracy['tp']} (auto-applied + accepted)",
            f"  False Positives: {accuracy['fp']} (auto-applied + rejected)",
            f"  False Negatives: {accuracy['fn']} (not applied + accepted)",
            f"  True Negatives: {accuracy['tn']} (not applied + rejected)",
            "",
            f"Recommended threshold: {threshold:.2f}",
        ]
    else:
        # All components report
        thresholds = scorer.get_all_thresholds()

        lines = [
            "Confidence Analysis: All Components",
            "",
            f"Recommended thresholds (optimized for F1 score):",
            ""
        ]

        for comp_type, threshold in sorted(thresholds.items()):
            accuracy = scorer.get_component_accuracy(comp_type)
            lines.append(f"{comp_type:<20} {threshold:.2f}  (F1: {accuracy['f1_score']:.2f}, n={accuracy['sample_size']})")

        lines.append("")
        lines.append(f"Default threshold: {scorer.default_threshold:.2f}")

    return "\n".join(lines)