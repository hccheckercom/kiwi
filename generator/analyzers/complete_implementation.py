"""
Complete Phase 1 + Phase 2 Implementation Script

This script:
1. Generates 3 standardized themes (beauty, fashion, tech)
2. Analyzes them to populate golden patterns
3. Implements Phase 2: Smart Base Selection + DNA-Driven Design
"""

import sys
from pathlib import Path

# Add kiwi to path
kiwi_dir = Path(__file__).parent.parent
sys.path.insert(0, str(kiwi_dir))

from generator.analyzers.theme_analyzer import ThemeAnalyzer
from generator.analyzers.pattern_extractor import PatternExtractor
from generator.analyzers.bug_learner import BugPatternLearner


def generate_standardized_themes():
    """Generate 3 standardized themes using Kiwi generator"""
    print("=" * 60)
    print("STEP 1: Generate Standardized Themes")
    print("=" * 60)

    from generator.orchestrator import ThemeGenerator

    themes_to_generate = [
        {
            "name": "learning-beauty",
            "industry": "beauty",
            "input_spec": {
                "shop_name": "Beauty Haven",
                "primary_color": "#F4E4E4",
                "secondary_color": "#E8E0F0",
                "font_family": "Playfair Display, serif"
            }
        },
        {
            "name": "learning-fashion",
            "industry": "fashion",
            "input_spec": {
                "shop_name": "Fashion Forward",
                "primary_color": "#1a1a1a",
                "secondary_color": "#8b7355",
                "font_family": "Montserrat, sans-serif"
            }
        },
        {
            "name": "learning-tech",
            "industry": "tech",
            "input_spec": {
                "shop_name": "Tech Store",
                "primary_color": "#105dad",
                "secondary_color": "#1e40af",
                "font_family": "Inter, sans-serif"
            }
        }
    ]

    generated = []
    for theme_config in themes_to_generate:
        print(f"\nGenerating theme: {theme_config['name']}")
        try:
            generator = ThemeGenerator(
                theme_name=theme_config["name"],
                input_spec=theme_config["input_spec"],
                auto_fix=True,
                dry_run=False
            )

            # Generate foundation only (faster for learning)
            report = generator.generate_foundation()

            if report.success:
                generated.append({
                    "name": theme_config["name"],
                    "path": generator.output_dir,
                    "industry": theme_config["industry"]
                })
                print(f"  [OK] Generated {len(report.files_created)} files")
            else:
                print(f"  [ERROR] {report.error_message}")
        except Exception as e:
            print(f"  [ERROR] {e}")

    return generated


def analyze_generated_themes(themes):
    """Analyze generated themes to populate knowledge base"""
    print("\n" + "=" * 60)
    print("STEP 2: Analyze Generated Themes")
    print("=" * 60)

    db_path = kiwi_dir / "theme_knowledge.db"

    # Theme Analyzer
    print("\nRunning Theme Analyzer...")
    analyzer = ThemeAnalyzer(db_path)

    profiles = []
    for theme in themes:
        print(f"  Analyzing: {theme['name']}")
        profile = analyzer.analyze_theme(theme["path"])
        if profile:
            # Override industry detection with known industry
            profile["industry"] = theme["industry"]
            if analyzer.save_profile(profile):
                profiles.append(profile)
                print(f"    [OK] Saved profile")

    analyzer.close()

    # Pattern Extractor
    print("\nRunning Pattern Extractor...")
    extractor = PatternExtractor(db_path)

    total_patterns = 0
    for theme in themes:
        print(f"  Extracting patterns: {theme['name']}")
        count = extractor.analyze_theme_patterns(theme["path"], theme["name"])
        total_patterns += count
        print(f"    [OK] Found {count} patterns")

    promoted = extractor.promote_to_golden(min_usage=2)
    print(f"\n  [OK] Promoted {promoted} patterns to auto-apply")

    stats = extractor.get_stats()
    print(f"  Total patterns: {stats['total_patterns']}")
    print(f"  Auto-apply: {stats['auto_apply_patterns']}")

    extractor.close()

    # Bug Pattern Learner
    print("\nRunning Bug Pattern Learner...")
    kiwi_db = kiwi_dir / "kiwi.db"
    learner = BugPatternLearner(db_path, kiwi_db)

    learner.update_pattern_bug_counts()
    learner.calculate_quality_scores()

    stats = learner.get_stats()
    print(f"  Themes analyzed: {stats['themes_analyzed']}")
    print(f"  Avg quality: {stats['avg_quality_score']}/100")

    learner.close()

    return profiles


def implement_phase2():
    """Implement Phase 2: Smart Base Selection"""
    print("\n" + "=" * 60)
    print("STEP 3: Implement Phase 2 - Smart Base Selection")
    print("=" * 60)

    # This will be implemented in the MCP server
    print("\nCreating kiwi_suggest_base() MCP tool...")

    mcp_code = '''
def _handle_suggest_base(args: dict) -> str:
    """
    Suggest best base theme for new project.

    Args:
        industry: Target industry (beauty, tech, fashion, etc.)
        description: Brief project description

    Returns:
        JSON with suggested base theme, colors, components, reasoning
    """
    import json
    from pathlib import Path

    industry = args.get("industry", "unknown")
    description = args.get("description", "")

    # Query theme_knowledge.db for best match
    db_path = KIWI_DIR / "theme_knowledge.db"
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # Find themes matching industry
    cursor.execute("""
        SELECT theme_slug, industry, quality_score, design_tokens, components_used
        FROM theme_profiles
        WHERE industry = ? OR industry = 'unknown'
        ORDER BY quality_score DESC
        LIMIT 3
    """, (industry,))

    themes = cursor.fetchall()
    conn.close()

    if not themes:
        return json.dumps({
            "base_theme": None,
            "match_score": 0,
            "reasoning": "No themes found in knowledge base"
        })

    # Best match
    best = themes[0]
    theme_slug, theme_industry, quality, tokens_json, components_json = best

    tokens = json.loads(tokens_json) if tokens_json else {}
    components = json.loads(components_json) if components_json else {}

    # Calculate match score
    match_score = 1.0 if theme_industry == industry else 0.5

    result = {
        "base_theme": theme_slug,
        "match_score": match_score,
        "quality_score": quality,
        "suggested_colors": tokens.get("colors", {}),
        "suggested_fonts": tokens.get("fonts", {}),
        "suggested_components": components,
        "reasoning": f"{industry.title()} industry match, quality score {quality}/100"
    }

    return json.dumps(result, indent=2)
'''

    print(f"\n[OK] MCP tool code ready")
    print(f"     Add to mcp_server.py: _handle_suggest_base()")

    return mcp_code


if __name__ == "__main__":
    print("Kiwi Learning System - Complete Implementation")
    print("=" * 60)

    # Step 1: Generate themes
    themes = generate_standardized_themes()

    if not themes:
        print("\n[ERROR] No themes generated. Check generator errors above.")
        sys.exit(1)

    # Step 2: Analyze themes
    profiles = analyze_generated_themes(themes)

    # Step 3: Implement Phase 2
    mcp_code = implement_phase2()

    # Summary
    print("\n" + "=" * 60)
    print("COMPLETE - Summary")
    print("=" * 60)
    print(f"\nPhase 1:")
    print(f"  - Generated {len(themes)} standardized themes")
    print(f"  - Analyzed {len(profiles)} theme profiles")
    print(f"  - Knowledge base populated")

    print(f"\nPhase 2:")
    print(f"  - Smart Base Selection: Ready to implement")
    print(f"  - DNA-Driven Design: Ready to implement")

    print(f"\nNext steps:")
    print(f"  1. Add kiwi_suggest_base() to mcp_server.py")
    print(f"  2. Test with: kiwi_suggest_base(industry='beauty')")
    print(f"  3. Generate new theme using suggestions")
