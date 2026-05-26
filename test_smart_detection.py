"""Test script for Kiwi smart detection and token optimization."""

# Test Case 1: Should trigger kiwi_context
test_prompts_trigger = [
    "Tạo Logger.php",
    "Fix SQL injection trong search.php",
    "Thêm function validate vào utils.js",
    "Sửa CSS responsive cho header",
    "Update API endpoint trong controller.php",
]

# Test Case 2: Should NOT trigger kiwi_context (exclusions)
test_prompts_no_trigger = [
    "Giải thích code này",
    "Đọc file config.json",
    "Research bug trong scanner và fix",
    "Fix crash trong .claude/kiwi/scanner/",
    "Debug deployment script",
    "Commit changes",
    "Update README.md",
]

# Test Case 3: Edge cases
test_prompts_edge = [
    "Fix bug trong themes/sfvn/functions.php",  # Should trigger (user code)
    "Fix bug trong .claude/kiwi/mcp_server.py",  # Should NOT trigger (infrastructure)
    "Tạo test.php trong wezone-plugins",  # Should trigger (user code)
    "Tạo test.py trong .claude/kiwi/tools/",  # Should NOT trigger (Kiwi tools)
]

print("Test cases created. Use these prompts to verify smart detection.")
print("\nExpected behavior:")
print("- Trigger cases: Claude should auto-call kiwi_context before Write/Edit")
print("- No-trigger cases: Claude should proceed directly without kiwi_context")
print("- PostToolUse hook: Should scan CRITICAL after every Write/Edit on code files")