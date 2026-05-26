"""
Kiwi Generator — Theme Code Generation Module

Extends Kiwi from bug scanner/fixer to WordPress theme code generator.
Generates Wezone Core + Tailwind themes following Blueprint specifications.

Phase 1 (MVP): Foundation Generator (G0)
- Generate config, design tokens, Tailwind pipeline, WP bootstrap
- 15 foundation files with zero CRITICAL violations
- Theme activates without errors

Architecture:
- orchestrator.py: Main generation coordinator
- file_builder.py: Jinja2 template rendering engine
- blueprint_reader.py: Parse Blueprint markdown specs
- validator.py: Multi-layer validation (syntax, Kiwi scan, GATE compliance)
- templates/: Jinja2 templates for code generation

Integration:
- Reuses scanner/ for post-generation validation
- Reuses agent/context.py for rule injection
- Reuses memory/db.py for generation history tracking
"""

__version__ = "0.1.0"
__phase__ = "Phase 1: Foundation Generator (MVP)"

from pathlib import Path

GENERATOR_DIR = Path(__file__).parent
TEMPLATES_DIR = GENERATOR_DIR / "templates"
FOUNDATION_TEMPLATES_DIR = TEMPLATES_DIR / "foundation"

__all__ = [
    "GENERATOR_DIR",
    "TEMPLATES_DIR",
    "FOUNDATION_TEMPLATES_DIR",
]