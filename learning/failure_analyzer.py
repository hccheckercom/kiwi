"""Failure analysis and learning from failed fixes."""

from dataclasses import dataclass
from datetime import datetime
from typing import Dict, List, Optional
import json


@dataclass
class FailureRecord:
    """Record of a failed fix attempt."""
    lesson_id: str
    file_path: str
    line: int
    fix_attempted: str
    error_message: str
    timestamp: datetime
    user_id: Optional[int] = None
    context: Optional[Dict] = None


class FailureAnalyzer:
    """Analyze failed fixes to improve future attempts."""

    def __init__(self, db_path: str = ".kiwi_sessions/learning.db"):
        """Initialize failure analyzer."""
        self.db_path = db_path
        self._init_db()

    def _init_db(self):
        """Initialize database schema."""
        import sqlite3

        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        # Failure records table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS failure_records (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                lesson_id TEXT NOT NULL,
                file_path TEXT NOT NULL,
                line INTEGER,
                fix_attempted TEXT,
                error_message TEXT,
                context TEXT,
                user_id INTEGER,
                timestamp TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Learned patterns table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS learned_patterns (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                pattern_type TEXT NOT NULL,
                pattern_data TEXT NOT NULL,
                confidence REAL DEFAULT 0.5,
                occurrences INTEGER DEFAULT 1,
                last_seen TEXT DEFAULT CURRENT_TIMESTAMP,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)

        conn.commit()
        conn.close()

    def record_failure(
        self,
        lesson_id: str,
        file_path: str,
        line: int,
        fix_attempted: str,
        error_message: str,
        context: Optional[Dict] = None,
        user_id: Optional[int] = None
    ):
        """Record a failed fix attempt."""
        import sqlite3

        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute(
            """INSERT INTO failure_records
               (lesson_id, file_path, line, fix_attempted, error_message, context, user_id)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (
                lesson_id,
                file_path,
                line,
                fix_attempted,
                error_message,
                json.dumps(context) if context else None,
                user_id
            )
        )

        conn.commit()
        conn.close()

    def analyze_failures(self, lesson_id: str) -> Dict:
        """
        Analyze failures for a specific lesson.

        Returns:
            {
                'total_failures': int,
                'common_errors': [(error_pattern, count)],
                'failure_rate': float,
                'recommendations': [str]
            }
        """
        import sqlite3

        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        # Get all failures for this lesson
        cursor.execute(
            """SELECT error_message, fix_attempted, context
               FROM failure_records
               WHERE lesson_id = ?""",
            (lesson_id,)
        )

        failures = cursor.fetchall()
        conn.close()

        if not failures:
            return {
                'total_failures': 0,
                'common_errors': [],
                'failure_rate': 0.0,
                'recommendations': []
            }

        # Analyze error patterns
        error_counts = {}
        for error_msg, _, _ in failures:
            # Extract error type (first line of error message)
            error_type = error_msg.split('\n')[0] if error_msg else 'Unknown'
            error_counts[error_type] = error_counts.get(error_type, 0) + 1

        common_errors = sorted(
            error_counts.items(),
            key=lambda x: x[1],
            reverse=True
        )[:5]

        # Generate recommendations
        recommendations = self._generate_recommendations(
            lesson_id, failures, common_errors
        )

        return {
            'total_failures': len(failures),
            'common_errors': common_errors,
            'failure_rate': self._calculate_failure_rate(lesson_id),
            'recommendations': recommendations
        }

    def _calculate_failure_rate(self, lesson_id: str) -> float:
        """Calculate failure rate for a lesson."""
        import sqlite3
        from pathlib import Path

        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute(
            "SELECT COUNT(*) FROM failure_records WHERE lesson_id = ?",
            (lesson_id,)
        )
        failures = cursor.fetchone()[0]

        memory_db = Path(self.db_path).parent.parent / "memory" / "db.sqlite"
        if not memory_db.exists():
            conn.close()
            return 0.0

        memory_conn = sqlite3.connect(str(memory_db))
        memory_cursor = memory_conn.cursor()

        try:
            memory_cursor.execute(
                """SELECT COUNT(*) FROM scan_history
                   WHERE violations LIKE ?""",
                (f'%{lesson_id}%',)
            )
            total_scans = memory_cursor.fetchone()[0]
        except Exception as e:
            import sys
            print(f"[kiwi] failure_analyzer DB error: {e}", file=sys.stderr)
            total_scans = 0

        memory_conn.close()
        conn.close()

        if total_scans == 0:
            return 0.0

        return failures / total_scans

    def _generate_recommendations(
        self,
        lesson_id: str,
        failures: List,
        common_errors: List
    ) -> List[str]:
        """Generate recommendations based on failure analysis."""
        recommendations = []

        # Check for syntax errors
        syntax_errors = sum(
            1 for error_msg, _, _ in failures
            if 'SyntaxError' in error_msg or 'ParseError' in error_msg
        )

        if syntax_errors > len(failures) * 0.3:
            recommendations.append(
                "High syntax error rate detected. Consider validating fix syntax before applying."
            )

        # Check for import errors
        import_errors = sum(
            1 for error_msg, _, _ in failures
            if 'ImportError' in error_msg or 'ModuleNotFoundError' in error_msg
        )

        if import_errors > 0:
            recommendations.append(
                "Import errors detected. Verify all required imports are present in fix."
            )

        # Check for type errors
        type_errors = sum(
            1 for error_msg, _, _ in failures
            if 'TypeError' in error_msg or 'AttributeError' in error_msg
        )

        if type_errors > 0:
            recommendations.append(
                "Type errors detected. Consider adding type validation to fix logic."
            )

        return recommendations

    def update_lesson_from_failures(self, lesson_id: str) -> Optional[str]:
        """
        Update lesson based on failure analysis.

        Returns:
            Suggested lesson update or None
        """
        analysis = self.analyze_failures(lesson_id)

        if analysis['total_failures'] < 3:
            return None

        if analysis['failure_rate'] > 0.5:
            return (
                f"Lesson {lesson_id} has high failure rate ({analysis['failure_rate']:.1%}). "
                f"Common errors: {', '.join(e[0] for e in analysis['common_errors'][:3])}. "
                f"Consider revising fix logic or adding validation."
            )

        return None
