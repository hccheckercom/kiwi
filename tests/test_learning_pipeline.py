"""Test kiwi_context with full learning pipeline activated."""
import sys
import os
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

# Ensure DB tables exist
from memory.db import init_db
init_db()

from agent.context import build_context, format_context

print("=== Test 1: Basic build_context (no semantic) ===")
t = time.time()
ctx = build_context(task="checkout page", scope_type="theme", platform="wp")
ms = (time.time() - t) * 1000
print(f"Time: {ms:.0f}ms")
print(f"Rules: {ctx['rules_count']}, Categories: {ctx['task_categories']}")
print(f"Contextual rules: {len(ctx['contextual_rules'])}")
print(f"Anomalies: {len(ctx['anomalies'])}")
print(f"Semantic matches: {ctx['semantic_matches']}")
print()

print("=== Test 2: Semantic search (loads model first time) ===")
t = time.time()
from agent.context import _get_semantic_scores
from scanner.loader import load_patterns
patterns = load_patterns(os.path.join(os.path.dirname(os.path.dirname(__file__)), "lessons"), platform="wp")
scores = _get_semantic_scores("SQL injection security database query", patterns)
ms = (time.time() - t) * 1000
print(f"Time: {ms:.0f}ms (includes model load)")
print(f"Matches (sim > 0.4): {len(scores)}")
if scores:
    top5 = sorted(scores.items(), key=lambda x: -x[1])[:5]
    for lid, sim in top5:
        print(f"  {lid}: {sim:.3f}")
print()

print("=== Test 3: build_context WITH semantic ===")
t = time.time()
ctx2 = build_context(task="SQL injection security", scope_type="plugin", platform="wp")
ms = (time.time() - t) * 1000
print(f"Time: {ms:.0f}ms (model already loaded)")
print(f"Rules: {ctx2['rules_count']}, Semantic matches: {ctx2['semantic_matches']}")
for r in ctx2['rules'][:5]:
    print(f"  {r['id']} [{r['severity']}] {r['category']}: {r['title'][:60]}")
print()

print("=== Test 4: Format output with new sections ===")
out = format_context(ctx2)
for line in out.split("\n")[:5]:
    print(line)
print("...")
print()

print("=== Test 5: Compact format with anomaly/contextual info ===")
ctx3 = build_context(task="checkout", compact=True, scope_type="plugin")
print(format_context(ctx3))
print()

print("ALL TESTS PASSED")
