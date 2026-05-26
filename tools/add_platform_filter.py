#!/usr/bin/env python3
"""Add platform: theme metadata to theme-specific lessons."""

import re
from pathlib import Path

KIWI_ROOT = Path(__file__).parent.parent
LESSONS_DIR = KIWI_ROOT / "lessons"

# Patterns that indicate theme-specific lessons
THEME_PATTERNS = [
    r'wezone-templates/',
    r'functions\.php',
    r'style\.css',
    r'inc/wz-shims',
    r'template-parts/',
    r'header\.php',
    r'footer\.php',
    r'front-page\.php',
    r'single\.php',
    r'archive\.php',
]

def is_theme_specific(content: str) -> bool:
    """Check if lesson content contains theme-specific patterns."""
    for pattern in THEME_PATTERNS:
        if re.search(pattern, content):
            return True
    return False

def add_platform_metadata(file_path: Path) -> bool:
    """Add platform: theme to frontmatter if not present."""
    content = file_path.read_text(encoding='utf-8')

    # Check if already has platform metadata
    if re.search(r'^platform:\s*theme', content, re.MULTILINE):
        return False

    # Check if theme-specific
    if not is_theme_specific(content):
        return False

    # Find frontmatter end
    match = re.search(r'^---\n(.*?)\n---', content, re.DOTALL)
    if not match:
        return False

    frontmatter = match.group(1)

    # Add platform: theme after severity line
    if 'severity:' in frontmatter:
        new_frontmatter = re.sub(
            r'(severity:\s*\w+)',
            r'\1\nplatform: theme',
            frontmatter
        )
    else:
        # Add after category line
        new_frontmatter = re.sub(
            r'(category:\s*[\w-]+)',
            r'\1\nplatform: theme',
            frontmatter
        )

    new_content = content.replace(frontmatter, new_frontmatter)
    file_path.write_text(new_content, encoding='utf-8')
    return True

def main():
    """Process all lesson files."""
    updated = 0

    for lesson_file in LESSONS_DIR.rglob('*.md'):
        if lesson_file.name in ('README.md', '_meta.json'):
            continue

        try:
            if add_platform_metadata(lesson_file):
                print(f"✓ {lesson_file.relative_to(KIWI_ROOT)}")
                updated += 1
        except Exception as e:
            print(f"✗ {lesson_file.relative_to(KIWI_ROOT)}: {e}")

    print(f"\nUpdated {updated} lessons with platform: theme")

if __name__ == '__main__':
    main()
