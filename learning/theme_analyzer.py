"""Theme analyzer for knowledge base auto-population."""

import json
import os
from pathlib import Path
from typing import Dict, List, Optional


def analyze_theme(theme_path: str, theme_name: str, industry: str = "unknown") -> Dict:
    """
    Analyze generated theme and extract knowledge for database.

    Args:
        theme_path: Path to theme directory
        theme_name: Theme slug
        industry: Industry classification

    Returns:
        Dict with extracted theme profile data
    """
    theme_dir = Path(theme_path)

    if not theme_dir.exists():
        return {"error": f"Theme directory not found: {theme_path}"}

    # Extract design tokens from store-config.json
    config_path = theme_dir / "store-config.json"
    tokens = {}
    if config_path.exists():
        try:
            config = json.loads(config_path.read_text(encoding="utf-8"))
            tokens = {
                "colors": config.get("colors", {}),
                "fonts": config.get("fonts", {}),
                "spacing": config.get("spacing", {}),
            }
        except (json.JSONDecodeError, OSError):
            pass

    # Detect components from template-parts
    components = _detect_components(theme_dir)

    # Extract layout patterns from page templates
    layout = _detect_layout_pattern(theme_dir)

    # Count golden patterns (reusable sections)
    golden_count = _count_golden_patterns(theme_dir)

    return {
        "theme_slug": theme_name,
        "industry": industry,
        "tokens": tokens,
        "components": components,
        "layout": layout,
        "golden_patterns_count": golden_count,
        "quality_score": 0,  # Will be updated based on feedback
        "generation_count": 1,
    }


def _detect_components(theme_dir: Path) -> Dict[str, bool]:
    """Detect which components are present in theme."""
    components = {}

    template_parts = theme_dir / "template-parts"
    if not template_parts.exists():
        return components

    # Check for common components
    component_files = {
        "header": "header.php",
        "footer": "footer.php",
        "hero": "hero.php",
        "product-card": "product-card.php",
        "breadcrumb": "breadcrumb.php",
        "filter-bar": "filter-bar.php",
        "trust-badges": "trust-badges.php",
    }

    for comp_name, filename in component_files.items():
        components[comp_name] = (template_parts / filename).exists()

    return components


def _detect_layout_pattern(theme_dir: Path) -> str:
    """Detect layout pattern from page templates."""
    # Check homepage structure
    home_php = theme_dir / "home.php"
    if not home_php.exists():
        return "unknown"

    try:
        content = home_php.read_text(encoding="utf-8")

        # Detect layout patterns based on section order
        if "hero" in content and "categories" in content and "product-grid" in content:
            return "hero-categories-grid"
        elif "hero" in content and "product-grid" in content:
            return "hero-grid"
        elif "categories" in content and "product-grid" in content:
            return "categories-grid"
        else:
            return "custom"
    except OSError:
        return "unknown"


def _count_golden_patterns(theme_dir: Path) -> int:
    """Count reusable golden patterns in theme."""
    count = 0

    template_parts = theme_dir / "template-parts"
    if not template_parts.exists():
        return 0

    # Count PHP files in template-parts (each is a reusable pattern)
    for file in template_parts.glob("*.php"):
        if file.is_file():
            count += 1

    return count


def save_theme_profile(profile: Dict, db_path: str) -> bool:
    """
    Save theme profile to knowledge base database.

    Args:
        profile: Theme profile dict from analyze_theme()
        db_path: Path to theme_knowledge.db

    Returns:
        True if saved successfully
    """
    import sqlite3

    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        # Create table if not exists
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS theme_profiles (
                theme_slug TEXT PRIMARY KEY,
                industry TEXT NOT NULL,
                tokens TEXT,
                components TEXT,
                layout TEXT,
                golden_patterns_count INTEGER DEFAULT 0,
                quality_score INTEGER DEFAULT 0,
                generation_count INTEGER DEFAULT 1,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Insert or update profile
        cursor.execute("""
            INSERT INTO theme_profiles (
                theme_slug, industry, tokens, components, layout,
                golden_patterns_count, quality_score, generation_count
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(theme_slug) DO UPDATE SET
                industry = excluded.industry,
                tokens = excluded.tokens,
                components = excluded.components,
                layout = excluded.layout,
                golden_patterns_count = excluded.golden_patterns_count,
                generation_count = generation_count + 1,
                updated_at = CURRENT_TIMESTAMP
        """, (
            profile["theme_slug"],
            profile["industry"],
            json.dumps(profile["tokens"]),
            json.dumps(profile["components"]),
            profile["layout"],
            profile["golden_patterns_count"],
            profile["quality_score"],
            profile["generation_count"],
        ))

        conn.commit()
        conn.close()
        return True

    except sqlite3.Error as e:
        print(f"Database error: {e}")
        return False