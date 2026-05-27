"""Theme Analyzer — Extract design tokens and components from existing themes"""

import json
import re
import sqlite3
from pathlib import Path
from typing import Dict, List, Optional, Any
from datetime import datetime


class ThemeAnalyzer:
    """
    Analyze existing WordPress themes to extract:
    - Design tokens (colors, fonts, spacing, breakpoints)
    - Component usage (hero, header, footer variants)
    - Layout recipes
    - Quality scores from Kiwi scans
    """

    def __init__(self, db_path: Path):
        self.db_path = db_path
        self.conn = sqlite3.connect(db_path)
        self.cursor = self.conn.cursor()

    def analyze_theme(self, theme_path: Path) -> Optional[Dict[str, Any]]:
        """
        Analyze a single theme and return profile data.

        Returns:
            Theme profile dict or None if not a valid theme
        """
        if not theme_path.exists() or not theme_path.is_dir():
            return None

        style_css = theme_path / "style.css"
        if not style_css.exists():
            return None

        theme_slug = theme_path.name
        print(f"Analyzing theme: {theme_slug}")

        profile = {
            "theme_slug": theme_slug,
            "theme_path": str(theme_path),
            "created_at": datetime.now().isoformat(),
            "last_scanned": datetime.now().isoformat(),
        }

        # Extract design tokens
        profile["design_tokens"] = self._extract_design_tokens(theme_path)

        # Detect components
        profile["components_used"] = self._detect_components(theme_path)

        # Detect industry from theme name or tokens
        profile["industry"] = self._detect_industry(theme_slug, profile["design_tokens"])

        # Detect layout recipe
        profile["layout_recipe"] = self._detect_layout_recipe(theme_path)

        # Calculate quality score (will be updated after Kiwi scan)
        profile["quality_score"] = 0

        profile["deployed"] = False
        profile["generation_count"] = 0

        return profile

    def _extract_design_tokens(self, theme_path: Path) -> Dict[str, Any]:
        """Extract design tokens from tailwind.config.js and store-config.php"""
        tokens = {
            "colors": {},
            "fonts": {},
            "spacing": {},
            "breakpoints": {}
        }

        # Try tailwind.config.js
        tailwind_config = theme_path / "tailwind.config.js"
        if tailwind_config.exists():
            content = tailwind_config.read_text(encoding="utf-8", errors="ignore")

            # Extract colors (look for var(--wz-*) references)
            color_matches = re.findall(r"['\"]--wz-([^'\"]+)['\"]", content)
            for color_var in color_matches:
                tokens["colors"][color_var] = f"var(--wz-{color_var})"

            # Extract breakpoints
            breakpoint_matches = re.findall(r"['\"](\w+)['\"]:\s*['\"](\d+px)['\"]", content)
            for name, value in breakpoint_matches:
                if name in ["sm", "md", "lg", "xl", "2xl"]:
                    tokens["breakpoints"][name] = value

        # Try store-config.php
        store_config = theme_path / "store-config.php"
        if store_config.exists():
            content = store_config.read_text(encoding="utf-8", errors="ignore")

            # Extract primary color
            primary_match = re.search(r"['\"]primary['\"].*?['\"]#([0-9A-Fa-f]{6})['\"]", content)
            if primary_match:
                tokens["colors"]["primary"] = f"#{primary_match.group(1)}"

            # Extract font family
            font_match = re.search(r"['\"]font_family['\"].*?['\"]([^'\"]+)['\"]", content)
            if font_match:
                tokens["fonts"]["primary"] = font_match.group(1)

        return tokens

    def _detect_components(self, theme_path: Path) -> Dict[str, str]:
        """Detect which component variants are used in theme"""
        components = {}

        # Check template-parts folder
        template_parts = theme_path / "template-parts"
        if template_parts.exists():
            for file in template_parts.glob("*.php"):
                component_type = file.stem

                # Read file to detect variant
                content = file.read_text(encoding="utf-8", errors="ignore")

                # Simple heuristics for variant detection
                if "hero" in component_type:
                    if "h-screen" in content or "h-[600px]" in content:
                        components["hero"] = "H1"  # Full-bleed
                    elif "carousel" in content or "slider" in content:
                        components["hero"] = "H3"  # Carousel
                    else:
                        components["hero"] = "H2"  # Split

                elif "header" in component_type:
                    if "sticky" in content or "fixed" in content:
                        components["header"] = "HD8"  # Sticky
                    else:
                        components["header"] = "HD2"  # Classic

                elif "footer" in component_type:
                    if "newsletter" in content:
                        components["footer"] = "FT3"  # Newsletter-first
                    else:
                        components["footer"] = "FT1"  # Classic

        return components

    def _detect_industry(self, theme_slug: str, tokens: Dict) -> str:
        """Detect industry from theme name or design tokens"""
        slug_lower = theme_slug.lower()

        # Industry keywords in theme name
        if any(kw in slug_lower for kw in ["beauty", "cosmetic", "spa"]):
            return "beauty"
        elif any(kw in slug_lower for kw in ["fashion", "clothing", "apparel"]):
            return "fashion"
        elif any(kw in slug_lower for kw in ["food", "restaurant", "cafe"]):
            return "food"
        elif any(kw in slug_lower for kw in ["tech", "electronic", "gadget"]):
            return "tech"
        elif any(kw in slug_lower for kw in ["furniture", "home", "decor"]):
            return "furniture"

        # Detect from color palette
        colors = tokens.get("colors", {})
        primary = colors.get("primary", "")

        if primary:
            # Pastel pink/lavender → beauty
            if any(c in primary.lower() for c in ["f4e4e4", "e8e0f0", "fde8d8"]):
                return "beauty"
            # Dark blue → tech
            elif any(c in primary.lower() for c in ["105dad", "1e40af", "1e3a8a"]):
                return "tech"

        return "unknown"

    def _detect_layout_recipe(self, theme_path: Path) -> str:
        """Detect layout recipe from homepage structure"""
        home_page = theme_path / "page-home.php"
        if not home_page.exists():
            home_page = theme_path / "front-page.php"

        if not home_page.exists():
            return "unknown"

        content = home_page.read_text(encoding="utf-8", errors="ignore")

        # Simple heuristics
        if "testimonial" in content and "trust-badge" in content:
            return "Recipe C"  # Community-driven
        elif "categories" in content and "product-grid" in content:
            return "Recipe A"  # Editorial
        else:
            return "Recipe B"  # Conversion-focused

    def save_profile(self, profile: Dict[str, Any]) -> bool:
        """Save theme profile to database"""
        try:
            self.cursor.execute("""
                INSERT OR REPLACE INTO theme_profiles (
                    theme_slug, industry, created_at, last_scanned,
                    design_tokens, components_used, layout_recipe,
                    quality_score, generation_count, deployed, theme_path
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                profile["theme_slug"],
                profile["industry"],
                profile["created_at"],
                profile["last_scanned"],
                json.dumps(profile["design_tokens"]),
                json.dumps(profile["components_used"]),
                profile["layout_recipe"],
                profile["quality_score"],
                profile["generation_count"],
                profile["deployed"],
                profile["theme_path"]
            ))
            self.conn.commit()
            return True
        except Exception as e:
            print(f"Error saving profile: {e}")
            return False

    def analyze_all_themes(self, themes_dir: Path) -> List[Dict[str, Any]]:
        """Analyze all themes in a directory"""
        profiles = []

        if not themes_dir.exists():
            print(f"Themes directory not found: {themes_dir}")
            return profiles

        for theme_path in themes_dir.iterdir():
            if not theme_path.is_dir():
                continue

            # Skip test/generated themes
            if any(skip in theme_path.name for skip in ["test", "kiwi-", "generator"]):
                continue

            profile = self.analyze_theme(theme_path)
            if profile:
                if self.save_profile(profile):
                    profiles.append(profile)
                    print(f"  [OK] Saved profile for {profile['theme_slug']}")

        return profiles

    def get_all_profiles(self) -> List[Dict[str, Any]]:
        """Get all theme profiles from database"""
        self.cursor.execute("SELECT * FROM theme_profiles")
        rows = self.cursor.fetchall()

        profiles = []
        for row in rows:
            profiles.append({
                "theme_slug": row[0],
                "industry": row[1],
                "created_at": row[2],
                "last_scanned": row[3],
                "design_tokens": json.loads(row[4]) if row[4] else {},
                "components_used": json.loads(row[5]) if row[5] else {},
                "layout_recipe": row[6],
                "quality_score": row[7],
                "generation_count": row[8],
                "deployed": bool(row[9]),
                "theme_path": row[10]
            })

        return profiles

    def close(self):
        """Close database connection"""
        self.conn.close()


if __name__ == "__main__":
    import sys

    # Get paths
    kiwi_dir = Path(__file__).parent.parent.parent
    db_path = kiwi_dir / "theme_knowledge.db"

    # Default themes directory
    themes_dir = kiwi_dir.parent.parent / "themes"

    if len(sys.argv) > 1:
        themes_dir = Path(sys.argv[1])

    print(f"Theme Analyzer")
    print(f"Database: {db_path}")
    print(f"Themes directory: {themes_dir}")
    print()

    analyzer = ThemeAnalyzer(db_path)
    profiles = analyzer.analyze_all_themes(themes_dir)

    print()
    print(f"[OK] Analyzed {len(profiles)} themes")

    if profiles:
        print("\nTheme Profiles:")
        for p in profiles:
            print(f"  - {p['theme_slug']}: {p['industry']}, {len(p['components_used'])} components")

    analyzer.close()