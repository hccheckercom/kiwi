"""Fix 4 — project-signature lesson filtering (requires:/conflicts:).

Self-contained: builds throwaway project trees in tempdirs so there are no
machine-specific paths. Covers the two safety properties that make the
classification non-regressive:

  1. A Wezone project keeps every tagged lesson (it has the wezone-commerce cap)
     → scan output cannot change. This is the regression guard, in unit form.
  2. A non-Wezone project sheds requires:/conflicts: lessons → the false-positive
     classes ("use wz_*", "don't use WC()") disappear.
"""
import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from scanner.loader import load_patterns, invalidate_cache, _matches_stack
from scanner import project_profile


def _fresh():
    invalidate_cache()
    project_profile.invalidate()


def _mk_wezone_theme():
    d = tempfile.mkdtemp()
    os.makedirs(os.path.join(d, "inc"))
    open(os.path.join(d, "style.css"), "w").write("/* Theme */")
    # wz-shims.php is the canonical Wezone-theme structural marker
    open(os.path.join(d, "inc", "wz-shims.php"), "w").write("<?php // shims")
    return d


def _mk_plain_wp():
    d = tempfile.mkdtemp()
    open(os.path.join(d, "style.css"), "w").write("/* Theme */")
    open(os.path.join(d, "functions.php"), "w").write("<?php esc_html('x');")
    return d


def _mk_woocommerce():
    d = tempfile.mkdtemp()
    os.makedirs(os.path.join(d, "wp-content", "plugins", "woocommerce"))
    open(os.path.join(d, "style.css"), "w").write("/* Theme */")
    return d


def test_matches_stack_unit():
    # universal lesson (no requires/conflicts) — always loads
    assert _matches_stack({}, set())
    assert _matches_stack({}, {"woocommerce"})
    # requires
    assert _matches_stack({"requires": "wezone-commerce"}, {"wezone-commerce"})
    assert not _matches_stack({"requires": "wezone-commerce"}, set())
    assert not _matches_stack({"requires": "wezone-commerce"}, {"woocommerce"})
    # conflicts
    assert _matches_stack({"conflicts": "woocommerce"}, {"wezone-commerce"})
    assert not _matches_stack({"conflicts": "woocommerce"}, {"woocommerce"})
    # list form
    assert _matches_stack({"requires": ["wezone-commerce", "x"]}, {"x"})
    print("  PASS: test_matches_stack_unit")


def test_detect_stack():
    wez = _mk_wezone_theme()
    assert project_profile.detect_stack(wez, use_cache=False) == {"wezone-commerce"}, \
        "wz-shims.php must flag a Wezone theme"
    plain = _mk_plain_wp()
    assert project_profile.detect_stack(plain, use_cache=False) == set(), \
        "plain WP must have no Wezone cap"
    woo = _mk_woocommerce()
    assert "woocommerce" in project_profile.detect_stack(woo, use_cache=False)
    print("  PASS: test_detect_stack")


def test_legacy_no_filtering():
    """No project_path → no filtering (every existing caller is unaffected)."""
    _fresh()
    all_p = load_patterns(platform="wp")
    api = [p for p in all_p if p["category"] == "wezone-api"]
    assert api, "wezone-api lessons must load when no project_path given"
    print(f"  PASS: test_legacy_no_filtering (wezone-api={len(api)})")


def test_wezone_keeps_all():
    """Regression guard, unit form: Wezone project loads tagged lessons."""
    _fresh()
    base = load_patterns(platform="wp")
    _fresh()
    wez = load_patterns(platform="wp", project_path=_mk_wezone_theme())
    base_ids = {p["id"] for p in base}
    wez_ids = {p["id"] for p in wez}
    # Wezone project must not lose any lesson vs the unfiltered baseline.
    assert base_ids == wez_ids, f"Wezone scan dropped lessons: {base_ids - wez_ids}"
    print(f"  PASS: test_wezone_keeps_all ({len(wez_ids)} lessons)")


def test_non_wezone_drops_tagged():
    _fresh()
    plain = load_patterns(platform="wp", project_path=_mk_plain_wp())
    assert not [p for p in plain if p["category"] == "wezone-api"], \
        "plain WP must drop wezone-api (requires: wezone-commerce)"
    assert [p for p in plain if p["category"] == "woocommerce-migration"], \
        "plain WP must KEEP woo-migration (catches leftover WC during migration)"

    _fresh()
    woo = load_patterns(platform="wp", project_path=_mk_woocommerce())
    assert not [p for p in woo if p["category"] == "wezone-api"], \
        "WooCommerce shop must drop wezone-api"
    assert not [p for p in woo if p["category"] == "woocommerce-migration"], \
        "WooCommerce shop must drop woo-migration (conflicts: woocommerce)"
    print("  PASS: test_non_wezone_drops_tagged")


if __name__ == "__main__":
    test_matches_stack_unit()
    test_detect_stack()
    test_legacy_no_filtering()
    test_wezone_keeps_all()
    test_non_wezone_drops_tagged()
    print("\nAll stack-filter tests passed.")
