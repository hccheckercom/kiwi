"""Pattern Extractor — Find recurring code patterns across themes"""

import re
import sqlite3
from pathlib import Path
from typing import Dict, List, Set, Tuple
from collections import defaultdict
from datetime import datetime
import hashlib


class PatternExtractor:
    """
    Extract recurring code patterns from themes:
    - PHP functions (wz_* helpers, guards, data fetching)
    - CSS utilities (custom Tailwind classes, animations)
    - JS modules (cart, wishlist, popup handlers)

    Identify "golden patterns" (3+ uses, 0 bugs) for auto-injection.
    """

    def __init__(self, db_path: Path):
        self.db_path = db_path
        self.conn = sqlite3.connect(db_path)
        self.cursor = self.conn.cursor()

    def extract_php_functions(self, theme_path: Path) -> List[Dict]:
        """Extract reusable PHP functions from theme"""
        patterns = []

        # Scan functions.php and includes/
        php_files = []

        functions_php = theme_path / "functions.php"
        if functions_php.exists():
            php_files.append(functions_php)

        includes_dir = theme_path / "includes"
        if includes_dir.exists():
            php_files.extend(includes_dir.glob("**/*.php"))

        for php_file in php_files:
            content = php_file.read_text(encoding="utf-8", errors="ignore")

            # Extract function definitions
            func_pattern = r'function\s+(wz_\w+)\s*\([^)]*\)\s*\{([^}]+(?:\{[^}]*\}[^}]*)*)\}'
            matches = re.finditer(func_pattern, content, re.MULTILINE | re.DOTALL)

            for match in matches:
                func_name = match.group(1)
                func_body = match.group(0)

                # Skip if too long (likely not reusable)
                if len(func_body) > 500:
                    continue

                # Calculate hash for deduplication
                code_hash = hashlib.md5(func_body.encode()).hexdigest()[:8]

                patterns.append({
                    "pattern_type": "php_function",
                    "pattern_name": func_name,
                    "code": func_body,
                    "code_hash": code_hash,
                    "category": self._categorize_php_function(func_name, func_body)
                })

        return patterns

    def _categorize_php_function(self, name: str, code: str) -> str:
        """Categorize PHP function by purpose"""
        if "guard" in name or "is_active" in name or "function_exists" in code:
            return "security"
        elif "get_product" in name or "get_order" in name:
            return "wezone-api"
        elif "sanitize" in name or "escape" in name:
            return "php-security"
        elif "cache" in name or "transient" in name:
            return "performance"
        else:
            return "utility"

    def extract_css_utilities(self, theme_path: Path) -> List[Dict]:
        """Extract custom CSS utilities from theme"""
        patterns = []

        # Check src/main.css for custom utilities
        main_css = theme_path / "src" / "main.css"
        if not main_css.exists():
            return patterns

        content = main_css.read_text(encoding="utf-8", errors="ignore")

        # Extract custom @layer utilities
        utility_pattern = r'@layer\s+utilities\s*\{([^}]+(?:\{[^}]*\}[^}]*)*)\}'
        matches = re.finditer(utility_pattern, content, re.MULTILINE | re.DOTALL)

        for match in matches:
            utilities_block = match.group(1)

            # Extract individual utility classes
            class_pattern = r'\.([\w-]+)\s*\{([^}]+)\}'
            class_matches = re.finditer(class_pattern, utilities_block)

            for class_match in class_matches:
                class_name = class_match.group(1)
                class_body = class_match.group(0)

                code_hash = hashlib.md5(class_body.encode()).hexdigest()[:8]

                patterns.append({
                    "pattern_type": "css_utility",
                    "pattern_name": class_name,
                    "code": class_body,
                    "code_hash": code_hash,
                    "category": "css-tokens"
                })

        return patterns

    def extract_js_modules(self, theme_path: Path) -> List[Dict]:
        """Extract reusable JS modules from theme"""
        patterns = []

        # Check assets/js/ for modules
        js_dir = theme_path / "assets" / "js"
        if not js_dir.exists():
            return patterns

        for js_file in js_dir.glob("*.js"):
            # Skip minified files
            if ".min." in js_file.name:
                continue

            content = js_file.read_text(encoding="utf-8", errors="ignore")

            # Extract IIFE modules
            iife_pattern = r'\(function\s*\(\s*\$?\s*\)\s*\{([^}]+(?:\{[^}]*\}[^}]*)*)\}\)\s*\([^)]*\)'
            matches = re.finditer(iife_pattern, content, re.MULTILINE | re.DOTALL)

            for match in matches:
                module_body = match.group(0)

                # Skip if too long
                if len(module_body) > 1000:
                    continue

                code_hash = hashlib.md5(module_body.encode()).hexdigest()[:8]
                module_name = js_file.stem

                patterns.append({
                    "pattern_type": "js_module",
                    "pattern_name": module_name,
                    "code": module_body,
                    "code_hash": code_hash,
                    "category": "js-contract"
                })

        return patterns

    def find_golden_patterns(self, min_usage: int = 3) -> List[Dict]:
        """
        Find golden patterns (used 3+ times, 0 bugs).

        Returns:
            List of golden patterns with usage stats
        """
        # Get all patterns from database
        self.cursor.execute("""
            SELECT pattern_type, pattern_name, code, usage_count, bug_count, themes_used
            FROM golden_patterns
            WHERE usage_count >= ? AND bug_count = 0
            ORDER BY usage_count DESC, confidence DESC
        """, (min_usage,))

        rows = self.cursor.fetchall()

        golden = []
        for row in rows:
            golden.append({
                "pattern_type": row[0],
                "pattern_name": row[1],
                "code": row[2],
                "usage_count": row[3],
                "bug_count": row[4],
                "themes_used": row[5].split(",") if row[5] else []
            })

        return golden

    def analyze_theme_patterns(self, theme_path: Path, theme_slug: str) -> int:
        """
        Extract all patterns from a theme and update database.

        Returns:
            Number of patterns found
        """
        all_patterns = []

        # Extract patterns
        all_patterns.extend(self.extract_php_functions(theme_path))
        all_patterns.extend(self.extract_css_utilities(theme_path))
        all_patterns.extend(self.extract_js_modules(theme_path))

        # Update database
        for pattern in all_patterns:
            self._upsert_pattern(pattern, theme_slug)

        return len(all_patterns)

    def _upsert_pattern(self, pattern: Dict, theme_slug: str):
        """Insert or update pattern in database"""
        # Check if pattern exists (by type + name)
        self.cursor.execute("""
            SELECT id, usage_count, themes_used FROM golden_patterns
            WHERE pattern_type = ? AND pattern_name = ?
        """, (pattern["pattern_type"], pattern["pattern_name"]))

        existing = self.cursor.fetchone()

        if existing:
            # Update usage count and themes list
            pattern_id, usage_count, themes_used = existing
            themes_set = set(themes_used.split(",")) if themes_used else set()
            themes_set.add(theme_slug)

            self.cursor.execute("""
                UPDATE golden_patterns
                SET usage_count = ?, themes_used = ?, last_used = ?
                WHERE id = ?
            """, (
                usage_count + 1,
                ",".join(sorted(themes_set)),
                datetime.now().isoformat(),
                pattern_id
            ))
        else:
            # Insert new pattern
            self.cursor.execute("""
                INSERT INTO golden_patterns (
                    pattern_type, pattern_name, code, usage_count,
                    bug_count, themes_used, auto_apply, confidence,
                    category, created_at, last_used
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                pattern["pattern_type"],
                pattern["pattern_name"],
                pattern["code"],
                1,  # usage_count
                0,  # bug_count (will be updated by bug learner)
                theme_slug,
                False,  # auto_apply (will be set after 5+ uses)
                0.5,  # confidence
                pattern["category"],
                datetime.now().isoformat(),
                datetime.now().isoformat()
            ))

        self.conn.commit()

    def promote_to_golden(self, min_usage: int = 5):
        """Promote patterns with 5+ uses and 0 bugs to auto-apply"""
        self.cursor.execute("""
            UPDATE golden_patterns
            SET auto_apply = 1, confidence = 0.9
            WHERE usage_count >= ? AND bug_count = 0 AND auto_apply = 0
        """, (min_usage,))

        promoted = self.cursor.rowcount
        self.conn.commit()

        return promoted

    def get_stats(self) -> Dict:
        """Get pattern extraction statistics"""
        self.cursor.execute("SELECT COUNT(*) FROM golden_patterns")
        total = self.cursor.fetchone()[0]

        self.cursor.execute("SELECT COUNT(*) FROM golden_patterns WHERE auto_apply = 1")
        auto_apply = self.cursor.fetchone()[0]

        self.cursor.execute("SELECT pattern_type, COUNT(*) FROM golden_patterns GROUP BY pattern_type")
        by_type = dict(self.cursor.fetchall())

        return {
            "total_patterns": total,
            "auto_apply_patterns": auto_apply,
            "by_type": by_type
        }

    def close(self):
        """Close database connection"""
        self.conn.close()


if __name__ == "__main__":
    import sys
    from pathlib import Path

    kiwi_dir = Path(__file__).parent.parent.parent
    db_path = kiwi_dir / "theme_knowledge.db"

    print("Pattern Extractor")
    print(f"Database: {db_path}")
    print()

    extractor = PatternExtractor(db_path)

    # Get theme profiles from database
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute("SELECT theme_slug, theme_path FROM theme_profiles")
    themes = cursor.fetchall()
    conn.close()

    if not themes:
        print("No themes found in database. Run theme_analyzer.py first.")
        sys.exit(1)

    # Extract patterns from all themes
    total_patterns = 0
    for theme_slug, theme_path in themes:
        print(f"Extracting patterns from: {theme_slug}")
        count = extractor.analyze_theme_patterns(Path(theme_path), theme_slug)
        total_patterns += count
        print(f"  [OK] Found {count} patterns")

    print()
    print(f"[OK] Extracted {total_patterns} patterns total")

    # Promote golden patterns
    promoted = extractor.promote_to_golden(min_usage=2)  # Lower threshold for testing
    print(f"[OK] Promoted {promoted} patterns to auto-apply")

    # Show stats
    stats = extractor.get_stats()
    print()
    print("Pattern Statistics:")
    print(f"  Total patterns: {stats['total_patterns']}")
    print(f"  Auto-apply patterns: {stats['auto_apply_patterns']}")
    if stats['by_type']:
        print(f"  By type:")
        for ptype, count in stats['by_type'].items():
            print(f"    - {ptype}: {count}")

    extractor.close()