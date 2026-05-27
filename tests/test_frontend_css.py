"""Test CSS and responsive design patterns (mobile-first, breakpoints, tokens)."""

import pytest
from scanner.loader import load_patterns
from scanner.checkers import check_pattern
from pathlib import Path

LESSONS_DIR = Path(__file__).parent.parent / "lessons"


def test_css_hardcoded_colors():
    """LES-001: Hardcoded hex colors instead of CSS tokens."""
    patterns = load_patterns(str(LESSONS_DIR), platform="wp")
    pattern = next((p for p in patterns if p.lesson_id == "LES-001"), None)
    assert pattern is not None, "LES-001 not found"

    bad_code = """
<div class="bg-[#3b82f6] text-[#ffffff]">
    <h1 class="text-[#1e293b]">Title</h1>
</div>
"""

    good_code = """
<div class="bg-primary text-white">
    <h1 class="text-gray-900">Title</h1>
</div>
"""

    bad_violations = check_pattern(pattern, bad_code, "test.php")
    good_violations = check_pattern(pattern, good_code, "test.php")

    assert len(bad_violations) > 0, "Should detect hardcoded colors"
    assert len(good_violations) == 0, "Should pass with CSS tokens"


def test_css_hardcoded_spacing():
    """LES-002: Hardcoded px values instead of spacing tokens."""
    patterns = load_patterns(str(LESSONS_DIR), platform="wp")
    pattern = next((p for p in patterns if p.lesson_id == "LES-002"), None)
    assert pattern is not None, "LES-002 not found"

    bad_code = """
<div class="p-[24px] m-[16px]">
    <div class="gap-[12px]">Content</div>
</div>
"""

    good_code = """
<div class="p-6 m-4">
    <div class="gap-3">Content</div>
</div>
"""

    bad_violations = check_pattern(pattern, bad_code, "test.php")
    good_violations = check_pattern(pattern, good_code, "test.php")

    assert len(bad_violations) > 0, "Should detect hardcoded spacing"
    assert len(good_violations) == 0, "Should pass with spacing tokens"


def test_responsive_mobile_first():
    """LES-003: Desktop-first breakpoints instead of mobile-first."""
    patterns = load_patterns(str(LESSONS_DIR), platform="wp")
    pattern = next((p for p in patterns if p.lesson_id == "LES-003"), None)
    assert pattern is not None, "LES-003 not found"

    bad_code = """
<div class="grid-cols-4 md:grid-cols-2 sm:grid-cols-1">
    Products
</div>
"""

    good_code = """
<div class="grid-cols-1 md:grid-cols-2 lg:grid-cols-4">
    Products
</div>
"""

    bad_violations = check_pattern(pattern, bad_code, "test.php")
    good_violations = check_pattern(pattern, good_code, "test.php")

    assert len(bad_violations) > 0, "Should detect desktop-first approach"
    assert len(good_violations) == 0, "Should pass with mobile-first"


def test_responsive_breakpoint_order():
    """LES-004: Breakpoints in wrong order (lg before md)."""
    patterns = load_patterns(str(LESSONS_DIR), platform="wp")
    pattern = next((p for p in patterns if p.lesson_id == "LES-004"), None)
    assert pattern is not None, "LES-004 not found"

    bad_code = """
<div class="text-sm lg:text-xl md:text-base">
    Text
</div>
"""

    good_code = """
<div class="text-sm md:text-base lg:text-xl">
    Text
</div>
"""

    bad_violations = check_pattern(pattern, bad_code, "test.php")
    good_violations = check_pattern(pattern, good_code, "test.php")

    assert len(bad_violations) > 0, "Should detect wrong breakpoint order"
    assert len(good_violations) == 0, "Should pass with correct order"


def test_css_bem_classes():
    """LES-005: BEM class names (__ or --) instead of utility classes."""
    patterns = load_patterns(str(LESSONS_DIR), platform="wp")
    pattern = next((p for p in patterns if p.lesson_id == "LES-005"), None)
    assert pattern is not None, "LES-005 not found"

    bad_code = """
<div class="product-card__header">
    <h2 class="product-card__title--large">Title</h2>
</div>
"""

    good_code = """
<div class="flex items-center">
    <h2 class="text-xl font-bold">Title</h2>
</div>
"""

    bad_violations = check_pattern(pattern, bad_code, "test.php")
    good_violations = check_pattern(pattern, good_code, "test.php")

    assert len(bad_violations) > 0, "Should detect BEM classes"
    assert len(good_violations) == 0, "Should pass with utility classes"


def test_css_important_overuse():
    """LES-006: Overuse of !important in inline styles."""
    patterns = load_patterns(str(LESSONS_DIR), platform="wp")
    pattern = next((p for p in patterns if p.lesson_id == "LES-006"), None)
    assert pattern is not None, "LES-006 not found"

    bad_code = """
<div style="color: red !important; margin: 10px !important;">
    Content
</div>
"""

    good_code = """
<div class="text-red-500 m-2.5">
    Content
</div>
"""

    bad_violations = check_pattern(pattern, bad_code, "test.php")
    good_violations = check_pattern(pattern, good_code, "test.php")

    assert len(bad_violations) > 0, "Should detect !important overuse"
    assert len(good_violations) == 0, "Should pass without !important"


def test_responsive_hidden_classes():
    """LES-007: Using display:none instead of responsive hidden classes."""
    patterns = load_patterns(str(LESSONS_DIR), platform="wp")
    pattern = next((p for p in patterns if p.lesson_id == "LES-007"), None)
    assert pattern is not None, "LES-007 not found"

    bad_code = """
<div style="display: none;">
    Mobile menu
</div>
"""

    good_code = """
<div class="hidden md:block">
    Mobile menu
</div>
"""

    bad_violations = check_pattern(pattern, bad_code, "test.php")
    good_violations = check_pattern(pattern, good_code, "test.php")

    assert len(bad_violations) > 0, "Should detect inline display:none"
    assert len(good_violations) == 0, "Should pass with responsive classes"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
