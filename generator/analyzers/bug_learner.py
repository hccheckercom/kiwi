"""Bug Pattern Learner — Cross-reference Kiwi scan history with theme files"""

import sqlite3
import json
from pathlib import Path
from typing import Dict, List, Tuple
from datetime import datetime
import sys

# Add parent to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))


class BugPatternLearner:
    """
    Learn from bug patterns across themes:
    - Query Kiwi scan history for violations
    - Find bugs fixed in some themes but not others
    - Auto-create new Kiwi lessons for recurring bugs
    - Update confidence scores based on fix success rate
    """

    def __init__(self, knowledge_db: Path, kiwi_db: Path):
        self.knowledge_db = knowledge_db
        self.kiwi_db = kiwi_db

        self.knowledge_conn = sqlite3.connect(knowledge_db)
        self.knowledge_cursor = self.knowledge_conn.cursor()

        self.kiwi_conn = sqlite3.connect(kiwi_db)
        self.kiwi_cursor = self.kiwi_conn.cursor()

    def get_theme_violations(self, theme_path: str) -> List[Dict]:
        """Get all violations from Kiwi scan history for a theme"""
        # Query scan_history for this theme
        self.kiwi_cursor.execute("""
            SELECT id, timestamp, violations_critical, violations_high, violations_suggest
            FROM scan_history
            WHERE path LIKE ?
            ORDER BY timestamp DESC
            LIMIT 1
        """, (f"%{Path(theme_path).name}%",))

        scan = self.kiwi_cursor.fetchone()
        if not scan:
            return []

        scan_id = scan[0]

        # Get violation details (if stored)
        # Note: Current Kiwi DB doesn't store individual violations, only counts
        # This is a placeholder for future enhancement

        return []

    def find_recurring_bugs(self) -> List[Dict]:
        """
        Find bug patterns that appear in multiple themes.

        Returns:
            List of recurring bug patterns with occurrence counts
        """
        recurring = []

        # Get all theme profiles
        self.knowledge_cursor.execute("SELECT theme_slug, theme_path FROM theme_profiles")
        themes = self.knowledge_cursor.fetchall()

        if len(themes) < 2:
            return recurring

        # For now, return placeholder
        # Full implementation would:
        # 1. Scan each theme with Kiwi
        # 2. Compare violations across themes
        # 3. Find patterns that appear 3+ times
        # 4. Suggest new Kiwi lessons

        return recurring

    def update_pattern_bug_counts(self):
        """Update bug_count for golden patterns based on scan results"""
        # Get all golden patterns
        self.knowledge_cursor.execute("""
            SELECT id, pattern_name, themes_used FROM golden_patterns
        """)
        patterns = self.knowledge_cursor.fetchall()

        updated = 0
        for pattern_id, pattern_name, themes_used in patterns:
            # For each theme using this pattern, check if it has bugs
            # This is a simplified version - full implementation would:
            # 1. Scan theme files containing this pattern
            # 2. Count violations in those files
            # 3. Update bug_count

            # Placeholder: assume 0 bugs for now
            bug_count = 0

            self.knowledge_cursor.execute("""
                UPDATE golden_patterns
                SET bug_count = ?
                WHERE id = ?
            """, (bug_count, pattern_id))
            updated += 1

        self.knowledge_conn.commit()
        return updated

    def calculate_quality_scores(self):
        """Calculate quality scores for themes based on Kiwi scan results"""
        self.knowledge_cursor.execute("SELECT theme_slug, theme_path FROM theme_profiles")
        themes = self.knowledge_cursor.fetchall()

        updated = 0
        for theme_slug, theme_path in themes:
            # Get latest scan results
            self.kiwi_cursor.execute("""
                SELECT violations_critical, violations_high, violations_suggest
                FROM scan_history
                WHERE path LIKE ?
                ORDER BY timestamp DESC
                LIMIT 1
            """, (f"%{Path(theme_path).name}%",))

            scan = self.kiwi_cursor.fetchone()
            if not scan:
                continue

            critical, high, suggest = scan

            # Calculate quality score (100 - weighted violations)
            # CRITICAL = -10 points, HIGH = -2 points, SUGGEST = -0.5 points
            quality_score = max(0, 100 - (critical * 10 + high * 2 + suggest * 0.5))

            self.knowledge_cursor.execute("""
                UPDATE theme_profiles
                SET quality_score = ?
                WHERE theme_slug = ?
            """, (quality_score, theme_slug))
            updated += 1

        self.knowledge_conn.commit()
        return updated

    def get_stats(self) -> Dict:
        """Get bug learning statistics"""
        # Get theme count
        self.knowledge_cursor.execute("SELECT COUNT(*) FROM theme_profiles")
        theme_count = self.knowledge_cursor.fetchone()[0]

        # Get avg quality score
        self.knowledge_cursor.execute("SELECT AVG(quality_score) FROM theme_profiles WHERE quality_score > 0")
        avg_quality = self.knowledge_cursor.fetchone()[0] or 0

        # Get scan count
        self.kiwi_cursor.execute("SELECT COUNT(*) FROM scan_history")
        scan_count = self.kiwi_cursor.fetchone()[0]

        return {
            "themes_analyzed": theme_count,
            "avg_quality_score": round(avg_quality, 1),
            "total_scans": scan_count
        }

    def close(self):
        """Close database connections"""
        self.knowledge_conn.close()
        self.kiwi_conn.close()


if __name__ == "__main__":
    kiwi_dir = Path(__file__).parent.parent.parent
    knowledge_db = kiwi_dir / "theme_knowledge.db"
    kiwi_db = kiwi_dir / "kiwi.db"

    print("Bug Pattern Learner")
    print(f"Knowledge DB: {knowledge_db}")
    print(f"Kiwi DB: {kiwi_db}")
    print()

    if not kiwi_db.exists():
        print(f"[WARN] Kiwi database not found: {kiwi_db}")
        print("       Bug counts and quality scores will be 0")
        print()

    learner = BugPatternLearner(knowledge_db, kiwi_db)

    # Update pattern bug counts
    print("Updating pattern bug counts...")
    updated = learner.update_pattern_bug_counts()
    print(f"  [OK] Updated {updated} patterns")

    # Calculate quality scores
    print("Calculating theme quality scores...")
    updated = learner.calculate_quality_scores()
    print(f"  [OK] Updated {updated} themes")

    # Show stats
    stats = learner.get_stats()
    print()
    print("Bug Learning Statistics:")
    print(f"  Themes analyzed: {stats['themes_analyzed']}")
    print(f"  Avg quality score: {stats['avg_quality_score']}/100")
    print(f"  Total scans: {stats['total_scans']}")

    learner.close()