"""Test LES-474 integration in validator."""

from pathlib import Path
from validator import Validator

def test_constant_with_hyphen():
    """Test that validator detects PHP constant names with hyphens."""
    v = Validator(Path('.'))

    # Bad: constant with hyphen
    bad_content = '''<?php
define('THEME-NAME_VERSION', '1.0.0');
define('MY-PLUGIN_DIR', __DIR__);
'''

    result = v.validate_content(bad_content, 'test.php')
    assert not result.passed, "Should fail for constants with hyphens"
    assert 'LES-474' in result.message, "Should mention LES-474"
    assert 'THEME-NAME_VERSION' in result.message, "Should list the bad constant"
    print(f"[PASS] Bad constant detected: {result.message}")

    # Good: constant with underscore
    good_content = '''<?php
define('THEME_NAME_VERSION', '1.0.0');
define('MY_PLUGIN_DIR', __DIR__);
'''

    result = v.validate_content(good_content, 'test.php')
    assert result.passed, f"Should pass for constants with underscores: {result.message}"
    print(f"[PASS] Good constant passed: {result.message}")

    print("\n[SUCCESS] All LES-474 validation tests passed!")

if __name__ == '__main__':
    test_constant_with_hyphen()