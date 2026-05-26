"""Effort estimation for violations based on historical data."""

import sqlite3
from pathlib import Path
from typing import Dict, Optional


class EffortEstimator:
    """Estimate effort (in minutes) for fixing violations."""

    def __init__(self, db_path: Optional[Path] = None):
        """
        Initialize effort estimator.

        Args:
            db_path: Path to confidence.db (optional, auto-detected if None)
        """
        if db_path is None:
            # Auto-detect confidence.db in memory/
            kiwi_dir = Path(__file__).parent.parent
            db_path = kiwi_dir / "memory" / "confidence.db"

        self.db_path = db_path
        self.cache: Dict[str, float] = {}

    def estimate(self, violation: dict) -> int:
        """
        Estimate effort in minutes to fix a violation.

        Args:
            violation: Dict with keys:
                - lesson_id: str
                - severity: str (CRITICAL|HIGH|SUGGEST)
                - category: str

        Returns:
            Estimated effort in minutes
        """
        lesson_id = violation.get("lesson_id", "")
        severity = violation.get("severity", "HIGH")
        category = violation.get("category", "")

        # Check cache first
        if lesson_id in self.cache:
            return int(self.cache[lesson_id])

        # Try to get historical average from confidence.db
        avg_time = self._get_avg_fix_time(lesson_id)
        if avg_time is not None:
            self.cache[lesson_id] = avg_time
            return int(avg_time)

        # Fallback: estimate by severity and category
        effort = self._estimate_by_severity_category(severity, category)
        self.cache[lesson_id] = effort
        return effort

    def _get_avg_fix_time(self, lesson_id: str) -> Optional[float]:
        """
        Get average fix time from confidence.db.

        Args:
            lesson_id: Lesson ID

        Returns:
            Average fix time in minutes, or None if no data
        """
        if not self.db_path.exists():
            return None

        try:
            conn = sqlite3.connect(str(self.db_path))
            cursor = conn.cursor()

            # Query: average fix time for successful fixes
            cursor.execute("""
                SELECT AVG(fix_duration_seconds) / 60.0
                FROM fix_outcomes
                WHERE lesson_id = ? AND success = 1 AND fix_duration_seconds IS NOT NULL
            """, (lesson_id,))

            result = cursor.fetchone()
            conn.close()

            if result and result[0] is not None:
                return float(result[0])

            return None

        except Exception:
            return None

    def _estimate_by_severity_category(self, severity: str, category: str) -> int:
        """
        Estimate effort based on severity and category.

        Args:
            severity: CRITICAL|HIGH|SUGGEST
            category: Category name

        Returns:
            Estimated effort in minutes
        """
        # Base effort by severity
        base_effort = {
            "CRITICAL": 15,
            "HIGH": 8,
            "SUGGEST": 5,
        }

        effort = base_effort.get(severity, 8)

        # Adjust by category complexity
        category_multipliers = {
            "php-security": 1.5,      # Security fixes need careful testing
            "api-security": 1.5,
            "auth-security": 1.8,     # Auth is critical and complex
            "db-schema": 2.0,         # DB changes need migration + testing
            "performance": 1.3,       # Performance fixes need profiling
            "code-quality": 0.8,      # Usually straightforward refactors
            "css-tokens": 0.6,        # CSS changes are quick
            "responsive": 0.7,
        }

        multiplier = category_multipliers.get(category, 1.0)
        return int(effort * multiplier)

    def estimate_batch(self, violations: list[dict]) -> list[dict]:
        """
        Estimate effort for multiple violations in place.

        Args:
            violations: List of violation dicts

        Returns:
            Same list with 'effort' field added to each violation
        """
        for v in violations:
            v["effort"] = self.estimate(v)
        return violations