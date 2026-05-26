"""Risk prediction: predict likelihood of fix failure."""

from dataclasses import dataclass
from typing import Dict, List, Optional
import re


@dataclass
class RiskPrediction:
    """Prediction of fix risk."""
    risk_score: float  # 0-1, higher = riskier
    risk_level: str    # LOW, MEDIUM, HIGH, CRITICAL
    factors: List[str]  # Contributing risk factors
    recommendation: str


class RiskPredictor:
    """Predict risk of fix failures."""

    def __init__(self, db_path: str = ".kiwi_sessions/learning.db"):
        """Initialize risk predictor."""
        self.db_path = db_path

    def predict_fix_risk(
        self,
        lesson_id: str,
        file_path: str,
        fix_content: str,
        context: Optional[Dict] = None
    ) -> RiskPrediction:
        """
        Predict risk of a fix failing.

        Args:
            lesson_id: Lesson being applied
            file_path: File being fixed
            fix_content: Proposed fix content
            context: Additional context (file size, complexity, etc.)

        Returns:
            Risk prediction with score and factors
        """
        factors = []
        risk_score = 0.0

        # Factor 1: Historical failure rate for this lesson
        lesson_risk = self._get_lesson_failure_rate(lesson_id)
        if lesson_risk > 0.3:
            factors.append(f"Lesson has {lesson_risk:.0%} historical failure rate")
            risk_score += lesson_risk * 0.3

        # Factor 2: File complexity
        file_risk = self._assess_file_complexity(file_path, context)
        if file_risk > 0.5:
            factors.append(f"File complexity is high ({file_risk:.1f})")
            risk_score += file_risk * 0.2

        # Factor 3: Fix size
        fix_size_risk = self._assess_fix_size(fix_content)
        if fix_size_risk > 0.5:
            factors.append(f"Large fix ({len(fix_content.splitlines())} lines)")
            risk_score += fix_size_risk * 0.2

        # Factor 4: Syntax complexity
        syntax_risk = self._assess_syntax_complexity(fix_content)
        if syntax_risk > 0.5:
            factors.append("Complex syntax patterns detected")
            risk_score += syntax_risk * 0.15

        # Factor 5: Dependencies
        dep_risk = self._assess_dependencies(fix_content)
        if dep_risk > 0.5:
            factors.append("Fix introduces new dependencies")
            risk_score += dep_risk * 0.15

        # Normalize risk score
        risk_score = min(risk_score, 1.0)

        # Determine risk level
        if risk_score >= 0.75:
            risk_level = "CRITICAL"
        elif risk_score >= 0.5:
            risk_level = "HIGH"
        elif risk_score >= 0.25:
            risk_level = "MEDIUM"
        else:
            risk_level = "LOW"

        # Generate recommendation
        recommendation = self._generate_recommendation(
            risk_level, factors, lesson_id
        )

        return RiskPrediction(
            risk_score=risk_score,
            risk_level=risk_level,
            factors=factors,
            recommendation=recommendation
        )

    def _get_lesson_failure_rate(self, lesson_id: str) -> float:
        """Get historical failure rate for a lesson."""
        import sqlite3

        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            cursor.execute(
                "SELECT COUNT(*) FROM failure_records WHERE lesson_id = ?",
                (lesson_id,)
            )

            failures = cursor.fetchone()[0]
            conn.close()

            # Placeholder: would also query success count
            # For now, assume 10 total attempts
            total = max(failures + 10, 1)
            return failures / total

        except Exception as e:
            import sys
            print(f"[kiwi] _get_lesson_failure_rate error: {e}", file=sys.stderr)
            return 0.0

    def _assess_file_complexity(
        self, file_path: str, context: Optional[Dict]
    ) -> float:
        """Assess file complexity risk."""
        if not context:
            return 0.3

        # Check file size
        file_size = context.get('file_size', 0)
        if file_size > 1000:
            return 0.8
        elif file_size > 500:
            return 0.5

        # Check cyclomatic complexity
        complexity = context.get('complexity', 0)
        if complexity > 20:
            return 0.9
        elif complexity > 10:
            return 0.6

        return 0.2

    def _assess_fix_size(self, fix_content: str) -> float:
        """Assess risk based on fix size."""
        lines = len(fix_content.splitlines())

        if lines > 100:
            return 0.9
        elif lines > 50:
            return 0.7
        elif lines > 20:
            return 0.5
        elif lines > 10:
            return 0.3

        return 0.1

    def _assess_syntax_complexity(self, fix_content: str) -> float:
        """Assess syntax complexity risk."""
        # Count complex patterns
        complexity_score = 0.0

        # Nested structures
        nesting_level = self._max_nesting_level(fix_content)
        if nesting_level > 4:
            complexity_score += 0.3

        # Regex patterns
        if re.search(r'preg_match|preg_replace|regex', fix_content):
            complexity_score += 0.2

        # SQL queries
        if re.search(r'SELECT|INSERT|UPDATE|DELETE', fix_content, re.IGNORECASE):
            complexity_score += 0.2

        # Anonymous functions
        if re.search(r'function\s*\(|=>\s*{', fix_content):
            complexity_score += 0.1

        return min(complexity_score, 1.0)

    def _max_nesting_level(self, code: str) -> int:
        """Calculate maximum nesting level."""
        max_level = 0
        current_level = 0

        for char in code:
            if char in '{[(':
                current_level += 1
                max_level = max(max_level, current_level)
            elif char in '}])':
                current_level = max(0, current_level - 1)

        return max_level

    def _assess_dependencies(self, fix_content: str) -> float:
        """Assess dependency risk."""
        # Check for new imports/requires
        import_patterns = [
            r'import\s+',
            r'require\s*\(',
            r'use\s+',
            r'from\s+\w+\s+import'
        ]

        for pattern in import_patterns:
            if re.search(pattern, fix_content):
                return 0.6

        return 0.1

    def _generate_recommendation(
        self, risk_level: str, factors: List[str], lesson_id: str
    ) -> str:
        """Generate recommendation based on risk level."""
        if risk_level == "CRITICAL":
            return (
                f"CRITICAL risk detected. Recommend manual review before applying. "
                f"Consider breaking fix into smaller changes. "
                f"Test thoroughly in isolated environment first."
            )

        if risk_level == "HIGH":
            return (
                f"HIGH risk detected. Recommend: "
                f"1) Review fix carefully, "
                f"2) Run comprehensive tests, "
                f"3) Have backup/rollback plan ready."
            )

        if risk_level == "MEDIUM":
            return (
                f"MEDIUM risk. Recommend running tests before applying. "
                f"Monitor for regressions after deployment."
            )

        return "LOW risk. Safe to apply with standard testing."


    def estimate_fix_time(self, risk_prediction: RiskPrediction) -> int:
        """
        Estimate time to apply fix in minutes.

        Args:
            risk_prediction: Risk prediction result

        Returns:
            Estimated minutes to complete fix
        """
        base_time = 5  # Base 5 minutes

        # Add time based on risk level
        risk_multipliers = {
            "LOW": 1.0,
            "MEDIUM": 1.5,
            "HIGH": 2.5,
            "CRITICAL": 4.0
        }

        multiplier = risk_multipliers.get(risk_prediction.risk_level, 1.0)
        return int(base_time * multiplier)
