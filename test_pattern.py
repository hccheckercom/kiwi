#!/usr/bin/env python3
"""Test LES-306 pattern matching."""

import re

# Pattern từ LES-306
pattern = r"orderby['\"]?\s*=>\s*['\"]rand['\"]"

# Test line từ thankyou/recommended.php
test_line = "\t\t'orderby' => 'rand',"

print(f"Pattern: {pattern}")
print(f"Test line: {test_line}")
print()

match = re.search(pattern, test_line)
if match:
    print(f"✅ MATCH FOUND")
    print(f"Matched text: {match.group()}")
else:
    print(f"❌ NO MATCH")

# Test với file thực
print("\n" + "="*60)
print("Testing with actual file:")
print("="*60)

file_path = r"D:\projects\wezone\themes\fashion-apparel\wezone-trunganh-v2\template-parts\thankyou\recommended.php"

try:
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()
        matches = re.findall(pattern, content, re.MULTILINE)
        if matches:
            print(f"✅ Found {len(matches)} match(es) in file")
            for m in matches:
                print(f"  - {m}")
        else:
            print(f"❌ No matches in file")

        # Try simpler pattern
        simple_pattern = r"orderby.*rand"
        simple_matches = re.findall(simple_pattern, content)
        if simple_matches:
            print(f"\n✅ Simpler pattern 'orderby.*rand' found {len(simple_matches)} match(es):")
            for m in simple_matches:
                print(f"  - {m}")
except Exception as e:
    print(f"Error: {e}")