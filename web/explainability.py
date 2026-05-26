"""Explainability module for Kiwi violations."""

import sys
from pathlib import Path
from typing import Optional

KIWI_DIR = Path(__file__).parent.parent
sys.path.insert(0, str(KIWI_DIR))

from scanner.loader import get_lesson_frontmatter


class ViolationExplainer:
    """Provides detailed explanations for violations."""

    def __init__(self, lessons_dir: str):
        self.lessons_dir = Path(lessons_dir)

    def explain(self, lesson_id: str, file: str, line: int, match_text: str = "") -> dict:
        """
        Generate comprehensive explanation for a violation.

        Returns:
            dict with why, alternatives, risk, fix_suggestion, related_lessons
        """
        fm, body = get_lesson_frontmatter(lesson_id, str(self.lessons_dir))

        if not fm:
            return {
                "error": f"Lesson {lesson_id} not found",
                "lesson_id": lesson_id,
                "file": file,
                "line": line,
            }

        # Extract sections from body
        sections = self._parse_lesson_body(body)

        # Calculate regression probability
        risk_score = self._calculate_risk(fm, file)

        # Find alternative approaches
        alternatives = self._find_alternatives(fm, sections)

        # Generate fix suggestion
        fix_suggestion = self._generate_fix_suggestion(fm, sections, match_text)

        # Find related lessons
        related = self._find_related_lessons(fm)

        return {
            "lesson_id": lesson_id,
            "file": file,
            "line": line,
            "title": fm.get("title", ""),
            "severity": fm.get("severity", "HIGH"),
            "category": fm.get("category", ""),
            "why": sections.get("why", "No explanation available"),
            "bad_example": sections.get("bad", ""),
            "good_example": sections.get("good", ""),
            "alternatives": alternatives,
            "risk": {
                "level": risk_score["level"],
                "probability": risk_score["probability"],
                "impact": risk_score["impact"],
                "explanation": risk_score["explanation"],
            },
            "fix_suggestion": fix_suggestion,
            "related_lessons": related,
            "pattern": fm.get("scan", {}).get("pattern", ""),
            "scope": fm.get("scan", {}).get("scope", ""),
        }

    def _parse_lesson_body(self, body: str) -> dict:
        """Parse lesson body into sections."""
        sections = {}
        current_section = None
        current_content = []

        for line in body.split("\n"):
            if line.startswith("## Why"):
                if current_section:
                    sections[current_section] = "\n".join(current_content).strip()
                current_section = "why"
                current_content = []
            elif line.startswith("## Bad"):
                if current_section:
                    sections[current_section] = "\n".join(current_content).strip()
                current_section = "bad"
                current_content = []
            elif line.startswith("## Good"):
                if current_section:
                    sections[current_section] = "\n".join(current_content).strip()
                current_section = "good"
                current_content = []
            elif current_section:
                current_content.append(line)

        if current_section:
            sections[current_section] = "\n".join(current_content).strip()

        return sections

    def _calculate_risk(self, fm: dict, file: str) -> dict:
        """Calculate regression risk for fixing this violation."""
        severity = fm.get("severity", "HIGH")
        category = fm.get("category", "")

        # High-risk categories
        high_risk_categories = ["php-security", "api-security", "auth-security", "performance"]

        if severity == "CRITICAL":
            level = "HIGH"
            probability = 0.7
            impact = "Critical functionality may break"
        elif category in high_risk_categories:
            level = "MEDIUM"
            probability = 0.5
            impact = "Security or performance regression possible"
        else:
            level = "LOW"
            probability = 0.3
            impact = "Minor regression risk"

        explanation = f"Fixing {severity} {category} violations typically has {level.lower()} regression risk."

        return {
            "level": level,
            "probability": probability,
            "impact": impact,
            "explanation": explanation,
        }

    def _find_alternatives(self, fm: dict, sections: dict) -> list[dict]:
        """Find alternative approaches to fix the violation."""
        alternatives = []

        good_example = sections.get("good", "")
        if good_example:
            alternatives.append({
                "approach": "Recommended fix",
                "description": "Use the pattern shown in the Good example",
                "code": good_example[:200],
                "tradeoffs": "Standard approach, well-tested",
            })

        # Add category-specific alternatives
        category = fm.get("category", "")
        if category == "php-security":
            alternatives.append({
                "approach": "Use framework helper",
                "description": "Leverage built-in security functions",
                "code": "",
                "tradeoffs": "More maintainable but may have performance overhead",
            })

        return alternatives

    def _generate_fix_suggestion(self, fm: dict, sections: dict, match_text: str) -> dict:
        """Generate specific fix suggestion."""
        fix_config = fm.get("fix", {})

        if not fix_config:
            return {
                "type": "manual",
                "description": "Manual fix required - see Good example",
                "steps": [
                    "Review the Bad example to understand the issue",
                    "Apply the pattern from the Good example",
                    "Test thoroughly to ensure no regressions",
                ],
            }

        fix_type = fix_config.get("type", "replace")

        if fix_type == "replace":
            return {
                "type": "auto",
                "description": "Automatic fix available",
                "steps": [
                    f"Pattern will be replaced: {fix_config.get('search', '')}",
                    f"With: {fix_config.get('replace', '')}",
                    "Run kiwi_fix to apply",
                ],
            }
        elif fix_type == "template":
            return {
                "type": "auto",
                "description": "Code template will be inserted",
                "steps": [
                    f"Template will be inserted at: {fix_config.get('position', 'before')}",
                    "Run kiwi_fix to apply",
                ],
            }
        else:
            return {
                "type": "semi-auto",
                "description": f"Fix type: {fix_type}",
                "steps": ["Run kiwi_fix to preview the change"],
            }

    def _find_related_lessons(self, fm: dict) -> list[dict]:
        """Find related lessons in the same category."""
        category = fm.get("category", "")
        severity = fm.get("severity", "")

        # This would query the lessons directory for related patterns
        # For now, return placeholder
        return [
            {
                "lesson_id": "Related lesson",
                "title": f"Other {severity} {category} patterns",
                "relevance": "Same category and severity",
            }
        ]


def explain_violation(lesson_id: str, file: str, line: int, match_text: str = "") -> dict:
    """Convenience function to explain a violation."""
    lessons_dir = KIWI_DIR / "lessons"
    explainer = ViolationExplainer(str(lessons_dir))
    return explainer.explain(lesson_id, file, line, match_text)
