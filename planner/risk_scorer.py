"""Risk scoring for violations based on severity and category."""

from typing import Dict, Tuple


class RiskScorer:
    """Score risk level (0.0-1.0) for violations."""

    # Risk matrix: (severity, category) -> risk score
    RISK_MATRIX: Dict[Tuple[str, str], float] = {
        # Security risks — highest priority
        ("CRITICAL", "php-security"): 0.95,
        ("CRITICAL", "api-security"): 0.95,
        ("CRITICAL", "auth-security"): 0.95,
        ("HIGH", "php-security"): 0.85,
        ("HIGH", "api-security"): 0.85,
        ("HIGH", "auth-security"): 0.85,
        ("SUGGEST", "php-security"): 0.60,

        # Performance risks — medium-high priority
        ("CRITICAL", "performance"): 0.80,
        ("CRITICAL", "db-schema"): 0.85,
        ("HIGH", "performance"): 0.60,
        ("HIGH", "db-schema"): 0.65,
        ("SUGGEST", "performance"): 0.40,

        # Code quality risks — medium priority
        ("CRITICAL", "code-quality"): 0.70,
        ("CRITICAL", "maintainability"): 0.65,
        ("HIGH", "code-quality"): 0.50,
        ("HIGH", "maintainability"): 0.45,
        ("SUGGEST", "code-quality"): 0.30,

        # UI/CSS risks — low priority
        ("CRITICAL", "css-tokens"): 0.50,
        ("CRITICAL", "responsive"): 0.55,
        ("HIGH", "css-tokens"): 0.35,
        ("HIGH", "responsive"): 0.40,
        ("SUGGEST", "css-tokens"): 0.20,
        ("SUGGEST", "responsive"): 0.25,

        # Compliance risks — medium-high priority
        ("CRITICAL", "ads-compliance"): 0.80,
        ("CRITICAL", "seo"): 0.70,
        ("HIGH", "ads-compliance"): 0.65,
        ("HIGH", "seo"): 0.55,
        ("SUGGEST", "ads-compliance"): 0.45,
    }

    # Default risk scores by severity (fallback)
    DEFAULT_RISK: Dict[str, float] = {
        "CRITICAL": 0.75,
        "HIGH": 0.50,
        "SUGGEST": 0.30,
    }

    def score(self, violation: dict) -> float:
        """
        Score risk level for a violation.

        Args:
            violation: Dict with keys:
                - severity: str (CRITICAL|HIGH|SUGGEST)
                - category: str
                - lesson_id: str (optional, for special cases)

        Returns:
            Risk score 0.0-1.0 (higher = more risky)
        """
        severity = violation.get("severity", "HIGH")
        category = violation.get("category", "")
        lesson_id = violation.get("lesson_id", "")

        # Special case: DB schema changes are always high risk
        if "schema" in lesson_id.lower() or "migration" in lesson_id.lower():
            return 0.90

        # Special case: Authentication/authorization always high risk
        if "auth" in lesson_id.lower() or "idor" in lesson_id.lower():
            return 0.95

        # Look up in risk matrix
        key = (severity, category)
        if key in self.RISK_MATRIX:
            return self.RISK_MATRIX[key]

        # Fallback to severity-based default
        return self.DEFAULT_RISK.get(severity, 0.50)

    def score_batch(self, violations: list[dict]) -> list[dict]:
        """
        Score risk for multiple violations in place.

        Args:
            violations: List of violation dicts

        Returns:
            Same list with 'risk' field added to each violation
        """
        for v in violations:
            v["risk"] = self.score(v)
        return violations