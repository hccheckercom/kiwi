"""Integration module for P1-P5 features into agent loop.

This module provides a unified interface to run all P1-P5 features
in the agent loop with configurable schedules and thresholds.
"""

import sys
from pathlib import Path
from typing import Dict, List, Optional
from datetime import datetime, timezone

sys.path.insert(0, str(Path(__file__).parent.parent))

from agent.auto_tune import auto_tune_all
from agent.confidence_decay import apply_decay_all, get_stale_lessons
from agent.correlation import auto_mark_correlated, find_correlated_lessons
from agent.feedback_loop import auto_apply_feedback, get_lessons_needing_tune
from agent.ab_testing import get_active_tests, calculate_ab_metrics, finalize_ab_test


class KiwiIntegration:
    """Unified interface for P1-P5 features."""

    def __init__(self, config: Optional[Dict] = None):
        """Initialize with optional config.

        Args:
            config: {
                "auto_tune": {"min_hits": 10, "enabled": True},
                "decay": {"min_days": 30, "enabled": True},
                "correlation": {"min_correlation": 0.80, "min_co_occurrences": 5, "enabled": True},
                "feedback": {"min_dismissals": 10, "enabled": True},
                "ab_testing": {"auto_finalize": True, "enabled": True}
            }
        """
        self.config = config or self._default_config()

    def _default_config(self) -> Dict:
        """Default configuration."""
        return {
            "auto_tune": {"min_hits": 10, "enabled": True},
            "decay": {"min_days": 30, "enabled": True},
            "correlation": {"min_correlation": 0.80, "min_co_occurrences": 5, "enabled": True},
            "feedback": {"min_dismissals": 10, "enabled": True},
            "ab_testing": {"auto_finalize": True, "enabled": True}
        }

    def run_weekly_maintenance(self, dry_run: bool = False) -> Dict:
        """Run all P1-P5 features for weekly maintenance.

        Args:
            dry_run: If True, preview without applying changes

        Returns:
            {
                "auto_tune": {...},
                "decay": {...},
                "correlation": {...},
                "feedback": {...},
                "ab_testing": {...},
                "summary": {...}
            }
        """
        results = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "dry_run": dry_run
        }

        # P1: Auto-tune noisy lessons
        if self.config["auto_tune"]["enabled"]:
            auto_tune_results = auto_tune_all(
                min_hits=self.config["auto_tune"]["min_hits"],
                dry_run=dry_run
            )
            results["auto_tune"] = {
                "tuned_count": len(auto_tune_results),
                "lessons": [r["metrics"]["lesson_id"] for r in auto_tune_results]
            }
        else:
            results["auto_tune"] = {"enabled": False}

        # P2: Apply confidence decay
        if self.config["decay"]["enabled"]:
            decay_results = apply_decay_all(
                min_days=self.config["decay"]["min_days"],
                dry_run=dry_run
            )
            stale = get_stale_lessons(confidence_threshold=0.50)
            results["decay"] = {
                "decayed_count": len(decay_results),
                "stale_count": len(stale),
                "stale_lessons": [s["lesson_id"] for s in stale]
            }
        else:
            results["decay"] = {"enabled": False}

        # P3: Mark correlated lessons
        if self.config["correlation"]["enabled"]:
            correlation_results = auto_mark_correlated(
                min_correlation=self.config["correlation"]["min_correlation"],
                min_co_occurrences=self.config["correlation"]["min_co_occurrences"],
                dry_run=dry_run
            )
            results["correlation"] = {
                "marked_count": len(correlation_results),
                "pairs": [(r["lesson_a"], r["lesson_b"]) for r in correlation_results]
            }
        else:
            results["correlation"] = {"enabled": False}

        # P4: Apply user feedback
        if self.config["feedback"]["enabled"]:
            feedback_results = auto_apply_feedback(
                min_dismissals=self.config["feedback"]["min_dismissals"],
                dry_run=dry_run
            )
            needing_tune = get_lessons_needing_tune(
                min_dismissals=self.config["feedback"]["min_dismissals"]
            )
            results["feedback"] = {
                "adjusted_count": len(feedback_results),
                "needing_tune_count": len(needing_tune),
                "needing_tune": [l["lesson_id"] for l in needing_tune]
            }
        else:
            results["feedback"] = {"enabled": False}

        # P5: Check A/B tests
        if self.config["ab_testing"]["enabled"]:
            active_tests = get_active_tests()
            finalized = []

            if self.config["ab_testing"]["auto_finalize"]:
                for test in active_tests:
                    metrics = test["metrics"]
                    # Auto-finalize if both versions reached target
                    if metrics["baseline"]["scans"] >= test["target_scans"] and \
                       metrics["variant"]["scans"] >= test["target_scans"]:
                        if not dry_run:
                            result = finalize_ab_test(test["test_id"])
                            finalized.append({
                                "test_id": test["test_id"],
                                "lesson_id": test["lesson_id"],
                                "winner": result["winner"]
                            })

            results["ab_testing"] = {
                "active_count": len(active_tests),
                "finalized_count": len(finalized),
                "finalized": finalized
            }
        else:
            results["ab_testing"] = {"enabled": False}

        # Summary
        results["summary"] = self._generate_summary(results)

        return results

    def _generate_summary(self, results: Dict) -> Dict:
        """Generate summary from results."""
        total_actions = 0

        if results["auto_tune"].get("tuned_count"):
            total_actions += results["auto_tune"]["tuned_count"]

        if results["decay"].get("decayed_count"):
            total_actions += results["decay"]["decayed_count"]

        if results["correlation"].get("marked_count"):
            total_actions += results["correlation"]["marked_count"]

        if results["feedback"].get("adjusted_count"):
            total_actions += results["feedback"]["adjusted_count"]

        if results["ab_testing"].get("finalized_count"):
            total_actions += results["ab_testing"]["finalized_count"]

        return {
            "total_actions": total_actions,
            "warnings": self._collect_warnings(results)
        }

    def _collect_warnings(self, results: Dict) -> List[str]:
        """Collect warnings from results."""
        warnings = []

        # Stale lessons
        if results["decay"].get("stale_count", 0) > 0:
            warnings.append(f"{results['decay']['stale_count']} lessons may be outdated (confidence < 0.50)")

        # Lessons needing tune
        if results["feedback"].get("needing_tune_count", 0) > 0:
            warnings.append(f"{results['feedback']['needing_tune_count']} lessons need regex tuning (many dismissals)")

        # Active A/B tests
        if results["ab_testing"].get("active_count", 0) > 0:
            warnings.append(f"{results['ab_testing']['active_count']} A/B tests still running")

        return warnings

    def get_health_report(self) -> Dict:
        """Get health report for all features.

        Returns:
            {
                "auto_tune": {"noisy_lessons": [...]},
                "decay": {"stale_lessons": [...]},
                "correlation": {"correlated_pairs": [...]},
                "feedback": {"needing_tune": [...]},
                "ab_testing": {"active_tests": [...]}
            }
        """
        report = {}

        # P1: Noisy lessons
        if self.config["auto_tune"]["enabled"]:
            # Get lessons with high FP rate
            from memory.db import get_connection
            conn = get_connection()
            rows = conn.execute("""
                SELECT lesson_id, false_positive_count, total_hits
                FROM lesson_confidence
                WHERE total_hits >= ?
                AND false_positive_count * 1.0 / total_hits > 0.30
                ORDER BY false_positive_count DESC
                LIMIT 10
            """, (self.config["auto_tune"]["min_hits"],)).fetchall()
            conn.close()

            report["auto_tune"] = {
                "noisy_lessons": [
                    {
                        "lesson_id": r["lesson_id"],
                        "fp_rate": round(r["false_positive_count"] / r["total_hits"], 2)
                    }
                    for r in rows
                ]
            }

        # P2: Stale lessons
        if self.config["decay"]["enabled"]:
            stale = get_stale_lessons(confidence_threshold=0.50)
            report["decay"] = {
                "stale_lessons": [
                    {
                        "lesson_id": s["lesson_id"],
                        "confidence": s["confidence"],
                        "days_since_hit": s["days_since_hit"]
                    }
                    for s in stale[:10]
                ]
            }

        # P3: Correlated pairs
        if self.config["correlation"]["enabled"]:
            correlated = find_correlated_lessons(
                min_correlation=self.config["correlation"]["min_correlation"],
                min_co_occurrences=self.config["correlation"]["min_co_occurrences"]
            )
            report["correlation"] = {
                "correlated_pairs": [
                    {
                        "lesson_a": c["lesson_a"],
                        "lesson_b": c["lesson_b"],
                        "correlation": c["correlation"]
                    }
                    for c in correlated[:10]
                ]
            }

        # P4: Lessons needing tune
        if self.config["feedback"]["enabled"]:
            needing_tune = get_lessons_needing_tune(
                min_dismissals=self.config["feedback"]["min_dismissals"]
            )
            report["feedback"] = {
                "needing_tune": [
                    {
                        "lesson_id": l["lesson_id"],
                        "dismissals": l["total_dismissals"]
                    }
                    for l in needing_tune[:10]
                ]
            }

        # P5: Active A/B tests
        if self.config["ab_testing"]["enabled"]:
            active_tests = get_active_tests()
            report["ab_testing"] = {
                "active_tests": [
                    {
                        "test_id": t["test_id"],
                        "lesson_id": t["lesson_id"],
                        "progress": f"{t['metrics']['baseline']['scans']}/{t['target_scans']}"
                    }
                    for t in active_tests
                ]
            }

        return report


if __name__ == "__main__":
    import argparse
    import json

    parser = argparse.ArgumentParser(description="Kiwi P1-P5 Integration")
    parser.add_argument("--run", action="store_true", help="Run weekly maintenance")
    parser.add_argument("--health", action="store_true", help="Get health report")
    parser.add_argument("--dry-run", action="store_true", help="Preview without applying")
    parser.add_argument("--config", help="Config file (JSON)")

    args = parser.parse_args()

    # Load config
    config = None
    if args.config:
        with open(args.config) as f:
            config = json.load(f)

    integration = KiwiIntegration(config)

    if args.run:
        print("Running weekly maintenance...\n")
        results = integration.run_weekly_maintenance(dry_run=args.dry_run)

        print(f"{'DRY RUN: ' if args.dry_run else ''}Maintenance complete")
        print(f"Timestamp: {results['timestamp']}\n")

        if results["auto_tune"].get("tuned_count"):
            print(f"P1 Auto-tune: {results['auto_tune']['tuned_count']} lessons tuned")

        if results["decay"].get("decayed_count"):
            print(f"P2 Decay: {results['decay']['decayed_count']} lessons decayed")
            if results["decay"]["stale_count"] > 0:
                print(f"  WARNING: {results['decay']['stale_count']} stale lessons")

        if results["correlation"].get("marked_count"):
            print(f"P3 Correlation: {results['correlation']['marked_count']} pairs marked")

        if results["feedback"].get("adjusted_count"):
            print(f"P4 Feedback: {results['feedback']['adjusted_count']} lessons adjusted")
            if results["feedback"]["needing_tune_count"] > 0:
                print(f"  WARNING: {results['feedback']['needing_tune_count']} lessons need tuning")

        if results["ab_testing"].get("finalized_count"):
            print(f"P5 A/B Testing: {results['ab_testing']['finalized_count']} tests finalized")
            if results["ab_testing"]["active_count"] > 0:
                print(f"  {results['ab_testing']['active_count']} tests still active")

        print(f"\nTotal actions: {results['summary']['total_actions']}")

        if results["summary"]["warnings"]:
            print("\nWarnings:")
            for warning in results["summary"]["warnings"]:
                print(f"  - {warning}")

    elif args.health:
        print("Health Report\n")
        report = integration.get_health_report()

        if report.get("auto_tune", {}).get("noisy_lessons"):
            print(f"P1 Auto-tune: {len(report['auto_tune']['noisy_lessons'])} noisy lessons")
            for l in report["auto_tune"]["noisy_lessons"][:5]:
                print(f"  - {l['lesson_id']}: FP rate {l['fp_rate']:.2f}")

        if report.get("decay", {}).get("stale_lessons"):
            print(f"\nP2 Decay: {len(report['decay']['stale_lessons'])} stale lessons")
            for l in report["decay"]["stale_lessons"][:5]:
                print(f"  - {l['lesson_id']}: confidence {l['confidence']:.2f}, {l['days_since_hit']} days")

        if report.get("correlation", {}).get("correlated_pairs"):
            print(f"\nP3 Correlation: {len(report['correlation']['correlated_pairs'])} correlated pairs")
            for p in report["correlation"]["correlated_pairs"][:5]:
                print(f"  - {p['lesson_a']} <-> {p['lesson_b']}: {p['correlation']:.2f}")

        if report.get("feedback", {}).get("needing_tune"):
            print(f"\nP4 Feedback: {len(report['feedback']['needing_tune'])} lessons need tuning")
            for l in report["feedback"]["needing_tune"][:5]:
                print(f"  - {l['lesson_id']}: {l['dismissals']} dismissals")

        if report.get("ab_testing", {}).get("active_tests"):
            print(f"\nP5 A/B Testing: {len(report['ab_testing']['active_tests'])} active tests")
            for t in report["ab_testing"]["active_tests"]:
                print(f"  - Test {t['test_id']}: {t['lesson_id']} ({t['progress']})")

    else:
        parser.print_help()