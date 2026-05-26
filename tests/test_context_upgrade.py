"""Test kiwi_context upgrade — backwards compatibility + signal detection."""
import sys
import os
import time
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from agent.context import build_context, format_context

# Backwards compatibility: no args
t = time.time()
ctx = build_context()
ms = (time.time() - t) * 1000
print("=== BACKWARDS COMPAT: no args ===")
print(f"Time: {ms:.0f}ms, Rules: {ctx['rules_count']}, Compact: {ctx['compact']}")
print(f"Categories: {ctx['task_categories']}")
for r in ctx["rules"][:3]:
    print(f"  {r['id']} [{r['severity']}]: {r['title'][:60]}")
print()

# compact=True explicit
ctx2 = build_context(task="checkout", compact=True)
print(f"=== compact=True: Rules: {ctx2['rules_count']}, Compact: {ctx2['compact']} ===")
print(format_context(ctx2))
print()

# compact=False explicit
ctx3 = build_context(task="CSS responsive", compact=False, scope_type="theme")
print(f"=== compact=False: Rules: {ctx3['rules_count']}, Compact: {ctx3['compact']} ===")
out = format_context(ctx3)
for line in out.split("\n")[:20]:
    print(line)
print("... (truncated)")
print()

# target_file detection
tmp = tempfile.NamedTemporaryFile(suffix=".php", delete=False, mode="w", encoding="utf-8")
tmp.write('<?php\n$wpdb->query("SELECT * FROM wp_orders WHERE id = $id");\n')
tmp.close()

t = time.time()
ctx4 = build_context(task="fix bug", target_file=tmp.name, scope_type="plugin")
ms = (time.time() - t) * 1000
print(f"=== TARGET FILE detection ===")
print(f"Time: {ms:.0f}ms, Signals: {ctx4['signals_detected']}")
for r in ctx4["rules"][:5]:
    print(f"  {r['id']} [{r['severity']}] cat={r['category']}: {r['title'][:60]}")
os.unlink(tmp.name)

# F7: Dynamic snippets test
ctx5 = build_context(task="checkout page", compact=False, scope_type="theme")
print(f"\n=== DYNAMIC SNIPPETS ===")
print(f"Total snippets: {len(ctx5['snippets'])}")
for s in ctx5["snippets"]:
    print(f"  {s['name'][:60]}")
