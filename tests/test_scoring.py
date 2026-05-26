"""Test Kiwi Self-Scoring Confidence System."""
import sys
import os
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from agent.scoring import (
    score_search, score_context, score_scan, score_check,
    score_fix, score_query, score_agent, format_confidence, get_action_label
)

print("=== Test 1: score_search — good result ===")
score, dims, hints = score_search(
    query="thanh toán|checkout",
    path=r"d:\projects\wezone\themes\kiwi-production-test",
    matches=["line with thanh toán", "line with checkout"],
    rg_returncode=0,
    file_types=["php"]
)
print(format_confidence(score, dims, hints))
assert score >= 70, f"Expected >= 70, got {score}"
print()

print("=== Test 2: score_search — bad path ===")
score, dims, hints = score_search(
    query="test",
    path="/nonexistent/path",
    matches=[],
    rg_returncode=1,
    file_types=["php"]
)
print(format_confidence(score, dims, hints))
assert score < 50, f"Expected < 50, got {score}"
print()

print("=== Test 3: score_context — with task categories ===")
score, dims, hints = score_context({
    "task_categories": ["php-security", "wezone-api"],
    "signal_matched_rules": 5,
    "history_boosted": 3,
    "rules_count": 15,
    "target_file": "page-checkout.php",
})
print(format_confidence(score, dims, hints))
assert score >= 80, f"Expected >= 80, got {score}"
print()

print("=== Test 4: score_context — no task, no target ===")
score, dims, hints = score_context({
    "task_categories": [],
    "rules_count": 10,
})
print(format_confidence(score, dims, hints))
assert score < 60, f"Expected < 60, got {score}"
print()

print("=== Test 5: score_scan — healthy scan ===")
score, dims, hints = score_scan(
    violations_count=3,
    files_scanned=50,
    total_patterns=400,
    critical_count=1,
    high_count=2,
    low_confidence_violations=0,
)
print(format_confidence(score, dims, hints))
assert score >= 80, f"Expected >= 80, got {score}"
print()

print("=== Test 6: score_check — clean file ===")
score, dims, hints = score_check(
    violations=[],
    file_path=__file__,  # use this test file
    total_patterns=400,
)
print(format_confidence(score, dims, hints))
assert score >= 80, f"Expected >= 80, got {score}"
print()

print("=== Test 7: score_fix — high confidence ===")
score, dims, hints = score_fix(
    lesson_id="LES-076",
    file_path=__file__,
    applied=True,
    confidence=0.95,
    has_good_code=True,
)
print(format_confidence(score, dims, hints))
assert score >= 80, f"Expected >= 80, got {score}"
print()

print("=== Test 8: score_fix — low confidence ===")
score, dims, hints = score_fix(
    lesson_id="LES-999",
    file_path=__file__,
    applied=False,
    confidence=0.3,
    has_good_code=False,
)
print(format_confidence(score, dims, hints))
assert score < 60, f"Expected < 60, got {score}"
print()

print("=== Test 9: score_query — good results ===")
score, dims, hints = score_query(
    keyword="nonce",
    results=[
        {"title": "Missing nonce verification", "description": ""},
        {"title": "wp_nonce_field required", "description": ""},
        {"title": "CSRF protection via nonce", "description": ""},
    ]
)
print(format_confidence(score, dims, hints))
assert score >= 70, f"Expected >= 70, got {score}"
print()

print("=== Test 10: score_query — no results ===")
score, dims, hints = score_query(keyword="xyznonexistent", results=[])
print(format_confidence(score, dims, hints))
assert score == 0, f"Expected 0, got {score}"
print()

print("=== Test 11: score_agent — good run ===")
score, dims, hints = score_agent({
    "scans": 4,
    "violations_found": 10,
    "fixes_applied": 8,
    "violations_remaining": 2,
})
print(format_confidence(score, dims, hints))
assert score >= 70, f"Expected >= 70, got {score}"
print()

print("=== Test 12: Action labels ===")
for s in [95, 75, 55, 30]:
    label, advice = get_action_label(s)
    print(f"  {s}/100 -> {label}: {advice}")
print()

print("ALL 12 TESTS PASSED")