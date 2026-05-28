#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Migrate existing themes to knowledge base.
Extract design tokens, components, layouts and calculate quality scores.
"""

import sys
import io

# Force UTF-8 encoding for stdout
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

import json
import re
import sqlite3
from pathlib import Path
from typing import Dict, List, Optional, Tuple

# Add kiwi root to path for imports
KIWI_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(KIWI_ROOT))


class ThemeMigrator:
    def __init__(self, db_path: str = "memory/theme_knowledge.db"):
        self.db_path = Path(__file__).parent.parent / db_path
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(self.db_path)
        self._ensure_schema()

    def _ensure_schema(self):
        """Ensure database schema exists."""
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS themes (
                theme_name TEXT PRIMARY KEY,
                industry TEXT NOT NULL,
                tokens TEXT NOT NULL,
                components TEXT NOT NULL,
                layout TEXT NOT NULL,
                quality_score INTEGER NOT NULL,
                generation_count INTEGER DEFAULT 0,
                last_used_at TIMESTAMP,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS generation_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                gen_id TEXT UNIQUE NOT NULL,
                theme_name TEXT NOT NULL,
                base_theme TEXT,
                industry TEXT,
                accepted INTEGER,
                quality_delta INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (theme_name) REFERENCES themes(theme_name)
            )
        """)
        # Add last_used_at column to existing DBs that predate this schema
        try:
            self.conn.execute("ALTER TABLE themes ADD COLUMN last_used_at TIMESTAMP")
        except Exception:
            pass
        self.conn.commit()

    def extract_tokens(self, theme_path: Path) -> Dict:
        """Extract design tokens from theme."""
        tokens = {
            "colors": {},
            "fonts": {},
            "spacing": {},
            "breakpoints": {}
        }

        # Try tailwind.config.js
        tailwind_config = theme_path / "tailwind.config.js"
        if tailwind_config.exists():
            content = tailwind_config.read_text(encoding='utf-8')

            # Extract colors — both quoted and unquoted keys
            for color in ['primary', 'secondary', 'accent']:
                match = re.search(rf"['\"]?{color}['\"]?\s*:\s*['\"]([^'\"]+)['\"]", content)
                if match:
                    tokens['colors'][color] = match.group(1)

            # Extract fontFamily — handle both array and object formats
            fonts_match = re.search(r'fontFamily:\s*\{(.+?)\}(?=\s*,?\s*\w+:|\s*\})', content, re.DOTALL)
            if fonts_match:
                fonts_str = fonts_match.group(1)
                # Array format: sans: ['Inter', ...]
                for font_key in ['sans', 'serif', 'heading', 'body']:
                    arr_match = re.search(rf"['\"]?{font_key}['\"]?\s*:\s*\[\s*['\"]([^'\"]+)['\"]", fonts_str)
                    if arr_match:
                        tokens['fonts'][font_key] = arr_match.group(1)
                # Object format: 'body-lg': { value: 'Inter' }
                if not tokens['fonts']:
                    val_match = re.search(r"value:\s*['\"]([^'\"]+)['\"]", fonts_str)
                    if val_match:
                        tokens['fonts']['primary'] = val_match.group(1)

        # Try store-config.json
        store_config = theme_path / "store-config.json"
        if store_config.exists():
            try:
                # Use utf-8-sig to handle BOM
                config = json.loads(store_config.read_text(encoding='utf-8-sig'))
                if 'colors' in config:
                    tokens['colors'].update(config['colors'])
                if 'fonts' in config:
                    tokens['fonts'].update(config['fonts'])
            except (json.JSONDecodeError, OSError, KeyError):
                pass

        # Fallback: extract from style.css
        if not tokens['colors'] or not tokens['fonts']:
            style_css = theme_path / "style.css"
            if style_css.exists():
                try:
                    content = style_css.read_text(encoding='utf-8')

                    # Extract CSS variables for colors
                    if not tokens['colors']:
                        color_vars = re.findall(r'--color-(\w+):\s*([^;]+);', content)
                        for name, value in color_vars[:3]:  # Take first 3
                            tokens['colors'][name] = value.strip()

                    # Extract font-family declarations
                    if not tokens['fonts']:
                        font_matches = re.findall(r'font-family:\s*([^;]+);', content)
                        if font_matches:
                            tokens['fonts']['primary'] = font_matches[0].strip()
                except (OSError, re.error):
                    pass

        return tokens

    def detect_components(self, theme_path: Path) -> List[str]:
        """Detect which components are implemented."""
        components = []

        # Check template-parts
        parts_dir = theme_path / "template-parts"
        if parts_dir.exists():
            for part_file in parts_dir.rglob("*.php"):
                name = part_file.stem
                if name in ['hero', 'header', 'footer', 'product-card', 'product-grid',
                           'categories', 'flash-sale', 'trust-badges', 'filter-bar',
                           'breadcrumb', 'sidebar', 'account', 'checkout']:
                    components.append(name)

        # Check pages
        pages_dir = theme_path / "pages"
        if pages_dir.exists():
            for page_file in pages_dir.rglob("*.php"):
                name = page_file.stem
                if name not in components:
                    components.append(f"page-{name}")

        return list(set(components))

    def analyze_layout(self, theme_path: Path) -> str:
        """Analyze layout pattern."""
        # Check home.php for layout structure
        home_php = theme_path / "pages" / "home.php"
        if not home_php.exists():
            home_php = theme_path / "home.php"

        if home_php.exists():
            content = home_php.read_text(encoding='utf-8')

            # Detect layout type
            if 'hero' in content.lower() and 'categories' in content.lower():
                if 'flash-sale' in content.lower():
                    return "hero-categories-flash-products"
                return "hero-categories-products"
            elif 'slider' in content.lower():
                return "slider-categories-products"
            else:
                return "standard-grid"

        return "unknown"

    def calculate_quality_score(self, theme_path: Path, tokens: Dict,
                                components: List[str]) -> int:
        """Calculate quality score (0-100)."""
        score = 0

        # 1. Foundation files: +20 (search root + subdirs)
        required_foundation = [
            'functions.php', 'style.css', 'wezoneconfig.php'
        ]
        foundation_count = sum(
            1 for f in required_foundation if (theme_path / f).exists()
        )
        # tailwind.config.js can be in root or subdirs
        if list(theme_path.rglob('tailwind.config.js')):
            foundation_count += 1
        # store-config.json or store-config.php
        if (theme_path / 'store-config.json').exists() or \
           list(theme_path.rglob('store-config.php')):
            foundation_count += 1
        score += int((foundation_count / 5) * 20)

        # 2. Pages coded: +2 per page, max +40
        pages_dir = theme_path / "pages"
        if pages_dir.exists():
            page_count = len(list(pages_dir.rglob("*.php")))
            score += min(page_count * 2, 40)

        # 3. Components: +1 per component, max +15
        score += min(len(components), 15)

        # 4. Design tokens: +10 for colors, +5 for fonts
        if tokens['colors']:
            score += 10
        if tokens['fonts']:
            score += 5

        # 5. Demo HTML available: +5
        if list(theme_path.rglob('code.html')) or \
           list(theme_path.rglob('demo*.html')):
            score += 5

        # 6. Built assets: +5
        if list(theme_path.rglob('assets/css/*.css')) or \
           list(theme_path.rglob('assets/js/*.js')):
            score += 5

        return min(score, 100)

    def scan_theme_for_violations(self, theme_path: Path) -> Tuple[int, int]:
        """Quick scan for CRITICAL violations."""
        from scanner.cli import scan_theme

        try:
            results = scan_theme(
                str(theme_path),
                platform='wp',
                severity='CRITICAL',
                max_per_lesson=1
            )

            critical_count = len([v for v in results['violations']
                                 if v['severity'] == 'CRITICAL'])
            total_count = len(results['violations'])

            return critical_count, total_count
        except Exception:
            return 0, 0

    def migrate_theme(self, theme_path: Path, industry: str,
                     dry_run: bool = False) -> Dict:
        """Migrate single theme to knowledge base."""
        theme_name = theme_path.name

        print(f"\n{'[DRY RUN] ' if dry_run else ''}Migrating: {theme_name}")
        print(f"  Industry: {industry}")

        # Extract data
        tokens = self.extract_tokens(theme_path)
        components = self.detect_components(theme_path)
        layout = self.analyze_layout(theme_path)
        quality_score = self.calculate_quality_score(theme_path, tokens, components)

        # Scan for violations
        critical, total = self.scan_theme_for_violations(theme_path)

        # Adjust quality score based on violations
        if critical > 0:
            quality_score = max(0, quality_score - (critical * 5))

        print(f"  Tokens: {len(tokens['colors'])} colors, {len(tokens['fonts'])} fonts")
        print(f"  Components: {len(components)} detected")
        print(f"  Layout: {layout}")
        print(f"  Quality: {quality_score}/100")
        print(f"  Violations: {critical} CRITICAL, {total} total")

        result = {
            'theme_name': theme_name,
            'industry': industry,
            'tokens': json.dumps(tokens),
            'components': json.dumps(components),
            'layout': layout,
            'quality_score': quality_score,
            'violations': {'critical': critical, 'total': total}
        }

        if not dry_run:
            # Insert or update
            self.conn.execute("""
                INSERT INTO themes (theme_name, industry, tokens, components, layout, quality_score)
                VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(theme_name) DO UPDATE SET
                    industry = excluded.industry,
                    tokens = excluded.tokens,
                    components = excluded.components,
                    layout = excluded.layout,
                    quality_score = excluded.quality_score,
                    updated_at = CURRENT_TIMESTAMP
            """, (theme_name, industry, result['tokens'], result['components'],
                  layout, quality_score))
            self.conn.commit()
            print(f"  ✓ Saved to database")

        return result

    def migrate_batch(self, themes_dir: Path, industry_map: Dict[str, str],
                     dry_run: bool = False) -> List[Dict]:
        """Migrate multiple themes."""
        results = []

        for theme_name, industry in industry_map.items():
            theme_path = themes_dir / theme_name
            if not theme_path.exists():
                print(f"WARNING: Theme not found: {theme_name}")
                continue

            try:
                result = self.migrate_theme(theme_path, industry, dry_run)
                results.append(result)
            except Exception as e:
                print(f"ERROR: Error migrating {theme_name}: {e}")

        return results

    def list_themes(self) -> List[Dict]:
        """List all themes in knowledge base."""
        cursor = self.conn.execute("""
            SELECT theme_name, industry, quality_score, generation_count, created_at
            FROM themes
            ORDER BY quality_score DESC, generation_count DESC
        """)

        return [
            {
                'theme_name': row[0],
                'industry': row[1],
                'quality_score': row[2],
                'generation_count': row[3],
                'created_at': row[4]
            }
            for row in cursor.fetchall()
        ]

    def close(self):
        self.conn.close()


def main():
    import argparse

    parser = argparse.ArgumentParser(description='Migrate themes to knowledge base')
    parser.add_argument('--theme', help='Single theme path')
    parser.add_argument('--industry', help='Industry for single theme')
    parser.add_argument('--batch', help='Batch migrate from JSON map file')
    parser.add_argument('--list', action='store_true', help='List themes in KB')
    parser.add_argument('--dry-run', action='store_true', help='Preview without saving')

    args = parser.parse_args()

    migrator = ThemeMigrator()

    try:
        if args.list:
            themes = migrator.list_themes()
            print(f"\n{len(themes)} themes in knowledge base:\n")
            for t in themes:
                print(f"  {t['theme_name']:30} {t['industry']:10} "
                      f"Q:{t['quality_score']:3} G:{t['generation_count']:2} "
                      f"{t['created_at']}")

        elif args.theme and args.industry:
            theme_path = Path(args.theme)
            migrator.migrate_theme(theme_path, args.industry, args.dry_run)

        elif args.batch:
            batch_file = Path(args.batch)
            if not batch_file.exists():
                print(f"Batch file not found: {batch_file}")
                return

            industry_map = json.loads(batch_file.read_text())
            themes_dir = Path('themes')

            results = migrator.migrate_batch(themes_dir, industry_map, args.dry_run)

            print(f"\n{'[DRY RUN] ' if args.dry_run else ''}Migration complete:")
            print(f"  Total: {len(results)}")
            print(f"  Avg quality: {sum(r['quality_score'] for r in results) / len(results):.1f}")

        else:
            parser.print_help()

    finally:
        migrator.close()


if __name__ == '__main__':
    main()