"""
Smart Base Selection MCP Tool - Phase 2 Implementation

Add this to mcp_server.py to enable intelligent theme suggestions.
"""

def _handle_suggest_base(args: dict) -> str:
    """
    Suggest best base theme for new project based on learned knowledge.

    Args:
        industry: Target industry (beauty, tech, fashion, food, furniture, pharma, mom-baby, pet, b2b, luxury)
        description: Brief project description (optional)

    Returns:
        JSON with suggested base theme, match score, quality score, design tokens, components, reasoning

    Example:
        kiwi_suggest_base(industry="beauty", description="Luxury skincare shop")
    """
    import json
    import sqlite3
    from pathlib import Path

    industry = args.get("industry", "unknown")
    description = args.get("description", "")

    # Query theme_knowledge.db
    db_path = KIWI_DIR / "theme_knowledge.db"

    if not db_path.exists():
        return json.dumps({
            "error": "Knowledge base not initialized. Run theme analyzers first.",
            "base_theme": None
        }, indent=2)

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # Find themes matching industry, sorted by quality
    cursor.execute("""
        SELECT theme_slug, industry, quality_score, design_tokens,
               components_used, layout_recipe, generation_count
        FROM theme_profiles
        WHERE industry = ? OR industry = 'unknown'
        ORDER BY quality_score DESC, generation_count ASC
        LIMIT 5
    """, (industry,))

    themes = cursor.fetchall()

    # Get golden patterns count
    cursor.execute("SELECT COUNT(*) FROM golden_patterns WHERE auto_apply = 1")
    golden_count = cursor.fetchone()[0]

    # Get industry stats
    cursor.execute("""
        SELECT AVG(quality_score), COUNT(*)
        FROM theme_profiles
        WHERE industry = ?
    """, (industry,))
    industry_stats = cursor.fetchone()
    avg_quality = industry_stats[0] or 0
    theme_count = industry_stats[1]

    conn.close()

    if not themes:
        # Fallback: suggest creating new theme
        return json.dumps({
            "base_theme": None,
            "match_score": 0.0,
            "quality_score": 0,
            "suggested_colors": _get_default_colors_for_industry(industry),
            "suggested_fonts": _get_default_fonts_for_industry(industry),
            "suggested_components": {},
            "golden_patterns_available": golden_count,
            "reasoning": f"No {industry} themes in knowledge base yet. Using industry DNA defaults.",
            "recommendation": "Generate first theme for this industry to populate knowledge base"
        }, indent=2)

    # Best match
    best = themes[0]
    theme_slug, theme_industry, quality, tokens_json, components_json, layout, gen_count = best

    tokens = json.loads(tokens_json) if tokens_json else {}
    components = json.loads(components_json) if components_json else {}

    # Calculate match score
    if theme_industry == industry:
        match_score = 1.0
    elif theme_industry == "unknown":
        match_score = 0.3
    else:
        match_score = 0.5

    # Adjust for quality
    quality_factor = quality / 100.0
    final_score = match_score * 0.7 + quality_factor * 0.3

    # Build reasoning
    reasoning_parts = []
    if theme_industry == industry:
        reasoning_parts.append(f"Perfect industry match ({industry})")
    else:
        reasoning_parts.append(f"Cross-industry match ({theme_industry} → {industry})")

    reasoning_parts.append(f"quality score {quality:.0f}/100")

    if gen_count > 0:
        reasoning_parts.append(f"proven base ({gen_count} generations)")

    reasoning = ", ".join(reasoning_parts)

    # Alternative suggestions
    alternatives = []
    for alt in themes[1:3]:
        alt_slug, alt_industry, alt_quality = alt[0], alt[1], alt[2]
        alternatives.append({
            "theme_slug": alt_slug,
            "industry": alt_industry,
            "quality_score": alt_quality,
            "match_score": 1.0 if alt_industry == industry else 0.5
        })

    result = {
        "base_theme": theme_slug,
        "match_score": round(final_score, 2),
        "quality_score": quality,
        "suggested_colors": tokens.get("colors", {}),
        "suggested_fonts": tokens.get("fonts", {}),
        "suggested_components": components,
        "layout_recipe": layout,
        "golden_patterns_available": golden_count,
        "reasoning": reasoning,
        "industry_stats": {
            "avg_quality": round(avg_quality, 1),
            "theme_count": theme_count
        },
        "alternatives": alternatives
    }

    return json.dumps(result, indent=2)


def _get_default_colors_for_industry(industry: str) -> dict:
    """Get default color palette for industry from DNA profiles"""
    defaults = {
        "beauty": {"primary": "#F4E4E4", "secondary": "#E8E0F0", "accent": "#B76E79"},
        "fashion": {"primary": "#1a1a1a", "secondary": "#8b7355", "accent": "#d4af37"},
        "tech": {"primary": "#105dad", "secondary": "#1e40af", "accent": "#3b82f6"},
        "food": {"primary": "#2d5016", "secondary": "#65a30d", "accent": "#84cc16"},
        "furniture": {"primary": "#78350f", "secondary": "#92400e", "accent": "#d97706"},
    }
    return defaults.get(industry, {"primary": "#105dad", "secondary": "#1e40af", "accent": "#3b82f6"})


def _get_default_fonts_for_industry(industry: str) -> dict:
    """Get default font stack for industry from DNA profiles"""
    defaults = {
        "beauty": {"primary": "Playfair Display, serif", "body": "DM Sans, sans-serif"},
        "fashion": {"primary": "Montserrat, sans-serif", "body": "Inter, sans-serif"},
        "tech": {"primary": "Inter, sans-serif", "body": "Inter, sans-serif"},
        "food": {"primary": "Merriweather, serif", "body": "Open Sans, sans-serif"},
        "furniture": {"primary": "Lora, serif", "body": "Nunito, sans-serif"},
    }
    return defaults.get(industry, {"primary": "Inter, sans-serif", "body": "Inter, sans-serif"})


# Add to TOOLS dict in mcp_server.py:
TOOLS["kiwi_suggest_base"] = {
    "handler": _handle_suggest_base,
    "description": "Suggest best base theme for new project based on learned knowledge",
    "parameters": {
        "industry": "Target industry (beauty, tech, fashion, food, furniture, pharma, mom-baby, pet, b2b, luxury)",
        "description": "Brief project description (optional)"
    }
}