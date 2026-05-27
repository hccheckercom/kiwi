-- Theme Knowledge Database Schema
-- Purpose: Store learned patterns from existing themes for intelligent generation

CREATE TABLE IF NOT EXISTS theme_profiles (
    theme_slug TEXT PRIMARY KEY,
    industry TEXT,  -- beauty, tech, fashion, food, furniture, pharma, mom-baby, pet, b2b, luxury
    created_at TEXT NOT NULL,
    last_scanned TEXT,
    design_tokens TEXT,  -- JSON: {colors, fonts, spacing, breakpoints}
    components_used TEXT,  -- JSON: {hero: 'H1', header: 'HD8', footer: 'FT3', ...}
    layout_recipe TEXT,  -- Recipe A, B, C, etc.
    quality_score REAL DEFAULT 0,  -- 0-100 based on Kiwi scan (100 - violations)
    generation_count INTEGER DEFAULT 0,  -- how many times used as base
    deployed BOOLEAN DEFAULT 0,
    theme_path TEXT,
    notes TEXT
);

CREATE INDEX IF NOT EXISTS idx_theme_industry ON theme_profiles(industry);
CREATE INDEX IF NOT EXISTS idx_theme_quality ON theme_profiles(quality_score DESC);

CREATE TABLE IF NOT EXISTS component_usage (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    theme_slug TEXT NOT NULL,
    component_type TEXT NOT NULL,  -- hero, header, footer, product-card, categories, etc.
    variant TEXT,  -- H1, HD8, FT3, PC3, CAT2, etc.
    html_snippet TEXT,
    css_classes TEXT,  -- comma-separated Tailwind classes
    php_code TEXT,  -- PHP template code
    confidence REAL DEFAULT 0.5,  -- how well it matches the variant (0-1)
    user_rating INTEGER,  -- 1-5 stars from feedback
    bug_count INTEGER DEFAULT 0,  -- violations found in this component
    usage_count INTEGER DEFAULT 1,
    detected_at TEXT NOT NULL,
    FOREIGN KEY (theme_slug) REFERENCES theme_profiles(theme_slug)
);

CREATE INDEX IF NOT EXISTS idx_component_type ON component_usage(component_type);
CREATE INDEX IF NOT EXISTS idx_component_theme ON component_usage(theme_slug);
CREATE INDEX IF NOT EXISTS idx_component_confidence ON component_usage(confidence DESC);

CREATE TABLE IF NOT EXISTS golden_patterns (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    pattern_type TEXT NOT NULL,  -- php_function, css_utility, js_module, template_part
    pattern_name TEXT NOT NULL,
    code TEXT NOT NULL,
    usage_count INTEGER DEFAULT 1,
    bug_count INTEGER DEFAULT 0,
    themes_used TEXT,  -- comma-separated theme slugs
    auto_apply BOOLEAN DEFAULT 0,  -- auto-inject in future generations
    confidence REAL DEFAULT 0.5,
    category TEXT,  -- security, performance, responsive, etc.
    created_at TEXT NOT NULL,
    last_used TEXT,
    UNIQUE(pattern_type, pattern_name)
);

CREATE INDEX IF NOT EXISTS idx_golden_type ON golden_patterns(pattern_type);
CREATE INDEX IF NOT EXISTS idx_golden_auto ON golden_patterns(auto_apply);
CREATE INDEX IF NOT EXISTS idx_golden_confidence ON golden_patterns(confidence DESC);

-- Migration tracking
CREATE TABLE IF NOT EXISTS schema_version (
    version INTEGER PRIMARY KEY,
    applied_at TEXT NOT NULL
);

INSERT OR IGNORE INTO schema_version (version, applied_at) VALUES (1, datetime('now'));
