"""Test accessibility and dark mode patterns (a11y, ARIA, semantic HTML, dark mode)."""

import pytest
from scanner.loader import load_patterns
from scanner.checkers import check_pattern
from pathlib import Path

LESSONS_DIR = Path(__file__).parent.parent / "lessons"


def test_a11y_missing_alt_text():
    """LES-008: Images missing alt text."""
    patterns = load_patterns(str(LESSONS_DIR), platform="wp")
    pattern = next((p for p in patterns if p.lesson_id == "LES-008"), None)
    assert pattern is not None, "LES-008 not found"

    bad_code = """
<img src="product.jpg" class="w-full">
"""

    good_code = """
<img src="product.jpg" alt="Product name" class="w-full">
"""

    bad_violations = check_pattern(pattern, bad_code, "test.php")
    good_violations = check_pattern(pattern, good_code, "test.php")

    assert len(bad_violations) > 0, "Should detect missing alt text"
    assert len(good_violations) == 0, "Should pass with alt text"


def test_a11y_button_without_aria():
    """LES-009: Interactive elements missing ARIA labels."""
    patterns = load_patterns(str(LESSONS_DIR), platform="wp")
    pattern = next((p for p in patterns if p.lesson_id == "LES-009"), None)
    assert pattern is not None, "LES-009 not found"

    bad_code = """
<button class="icon-only">
    <svg>...</svg>
</button>
"""

    good_code = """
<button class="icon-only" aria-label="Add to cart">
    <svg>...</svg>
</button>
"""

    bad_violations = check_pattern(pattern, bad_code, "test.php")
    good_violations = check_pattern(pattern, good_code, "test.php")

    assert len(bad_violations) > 0, "Should detect missing ARIA label"
    assert len(good_violations) == 0, "Should pass with ARIA label"


def test_a11y_non_semantic_html():
    """LES-010: Using div/span instead of semantic HTML."""
    patterns = load_patterns(str(LESSONS_DIR), platform="wp")
    pattern = next((p for p in patterns if p.lesson_id == "LES-010"), None)
    assert pattern is not None, "LES-010 not found"

    bad_code = """
<div class="header">
    <div class="nav">
        <div class="nav-item">Home</div>
    </div>
</div>
"""

    good_code = """
<header>
    <nav>
        <a href="/" class="nav-item">Home</a>
    </nav>
</header>
"""

    bad_violations = check_pattern(pattern, bad_code, "test.php")
    good_violations = check_pattern(pattern, good_code, "test.php")

    assert len(bad_violations) > 0, "Should detect non-semantic HTML"
    assert len(good_violations) == 0, "Should pass with semantic HTML"


def test_dark_mode_missing_variant():
    """LES-011: Colors without dark mode variants."""
    patterns = load_patterns(str(LESSONS_DIR), platform="wp")
    pattern = next((p for p in patterns if p.lesson_id == "LES-011"), None)
    assert pattern is not None, "LES-011 not found"

    bad_code = """
<div class="bg-white text-gray-900">
    Content
</div>
"""

    good_code = """
<div class="bg-white dark:bg-gray-900 text-gray-900 dark:text-white">
    Content
</div>
"""

    bad_violations = check_pattern(pattern, bad_code, "test.php")
    good_violations = check_pattern(pattern, good_code, "test.php")

    assert len(bad_violations) > 0, "Should detect missing dark mode variant"
    assert len(good_violations) == 0, "Should pass with dark mode variant"


def test_dark_mode_hardcoded_colors():
    """LES-012: Hardcoded colors that don't adapt to dark mode."""
    patterns = load_patterns(str(LESSONS_DIR), platform="wp")
    pattern = next((p for p in patterns if p.lesson_id == "LES-012"), None)
    assert pattern is not None, "LES-012 not found"

    bad_code = """
<div style="background: #ffffff; color: #000000;">
    Content
</div>
"""

    good_code = """
<div class="bg-white dark:bg-gray-900 text-gray-900 dark:text-white">
    Content
</div>
"""

    bad_violations = check_pattern(pattern, bad_code, "test.php")
    good_violations = check_pattern(pattern, good_code, "test.php")

    assert len(bad_violations) > 0, "Should detect hardcoded colors"
    assert len(good_violations) == 0, "Should pass with dark mode classes"


def test_a11y_focus_visible():
    """LES-013: Interactive elements missing focus-visible styles."""
    patterns = load_patterns(str(LESSONS_DIR), platform="wp")
    pattern = next((p for p in patterns if p.lesson_id == "LES-013"), None)
    assert pattern is not None, "LES-013 not found"

    bad_code = """
<button class="outline-none">
    Click me
</button>
"""

    good_code = """
<button class="focus-visible:ring-2 focus-visible:ring-primary">
    Click me
</button>
"""

    bad_violations = check_pattern(pattern, bad_code, "test.php")
    good_violations = check_pattern(pattern, good_code, "test.php")

    assert len(bad_violations) > 0, "Should detect missing focus styles"
    assert len(good_violations) == 0, "Should pass with focus-visible"


def test_a11y_heading_hierarchy():
    """LES-014: Skipping heading levels (h1 to h3)."""
    patterns = load_patterns(str(LESSONS_DIR), platform="wp")
    pattern = next((p for p in patterns if p.lesson_id == "LES-014"), None)
    assert pattern is not None, "LES-014 not found"

    bad_code = """
<h1>Page Title</h1>
<h3>Section Title</h3>
"""

    good_code = """
<h1>Page Title</h1>
<h2>Section Title</h2>
"""

    bad_violations = check_pattern(pattern, bad_code, "test.php")
    good_violations = check_pattern(pattern, good_code, "test.php")

    assert len(bad_violations) > 0, "Should detect skipped heading level"
    assert len(good_violations) == 0, "Should pass with proper hierarchy"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
