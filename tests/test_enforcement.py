"""
Test enforcement: PreToolUse hook blocks/allows correctly

Tests the hard enforcement mechanism that blocks Edit/Write without kiwi_context.
"""

import os
import sys
import json
import tempfile
from pathlib import Path

# Add kiwi to path
sys.path.insert(0, str(Path(__file__).parent.parent))

def test_state_file_creation():
    """Test that track_kiwi_context hook creates state file correctly"""
    print("=" * 60)
    print("TEST 1: State file creation")
    print("=" * 60)

    # Simulate kiwi_context call by creating state file
    from hooks.track_kiwi_context import get_state_file, get_conversation_id

    conv_id = get_conversation_id()
    state_file = get_state_file()

    print(f"Conversation ID: {conv_id}")
    print(f"State file: {state_file}")

    # Create state
    state = {
        "kiwi_context_called": True,
        "timestamp": "2026-05-24T10:00:00Z"
    }

    with open(state_file, 'w') as f:
        json.dump(state, f)

    # Verify state file exists
    assert os.path.exists(state_file), "State file should exist"

    # Read back
    with open(state_file, 'r') as f:
        loaded = json.load(f)

    assert loaded["kiwi_context_called"] == True, "State should have kiwi_context_called=True"

    print("✓ State file created and verified")

    # Cleanup
    if os.path.exists(state_file):
        os.remove(state_file)

    return True


def test_pre_edit_hook_blocks_without_context():
    """Test that pre_edit hook blocks when kiwi_context not called"""
    print("\n" + "=" * 60)
    print("TEST 2: Pre-edit hook blocks without context")
    print("=" * 60)

    from hooks.pre_edit import should_block_edit, get_state_file

    # Remove state file to simulate no kiwi_context call
    state_file = get_state_file()
    if os.path.exists(state_file):
        os.remove(state_file)

    # Test blocking for .php file
    result = should_block_edit("test.php", "Write")

    print(f"should_block_edit('test.php', 'Write') = {result}")

    assert result == True, "Should block .php file without context"

    print("✓ Pre-edit hook correctly blocks without context")

    return True


def test_pre_edit_hook_allows_with_context():
    """Test that pre_edit hook allows when kiwi_context called"""
    print("\n" + "=" * 60)
    print("TEST 3: Pre-edit hook allows with context")
    print("=" * 60)

    from hooks.pre_edit import should_block_edit, get_state_file

    # Create state file to simulate kiwi_context call
    state_file = get_state_file()
    state = {
        "kiwi_context_called": True,
        "timestamp": "2026-05-24T10:00:00Z"
    }

    with open(state_file, 'w') as f:
        json.dump(state, f)

    # Test allowing for .php file
    result = should_block_edit("test.php", "Write")

    print(f"should_block_edit('test.php', 'Write') = {result}")

    assert result == False, "Should allow .php file with context"

    print("✓ Pre-edit hook correctly allows with context")

    # Cleanup
    if os.path.exists(state_file):
        os.remove(state_file)

    return True


def test_pre_edit_hook_allows_non_code_files():
    """Test that pre_edit hook allows non-code files without context"""
    print("\n" + "=" * 60)
    print("TEST 4: Pre-edit hook allows non-code files")
    print("=" * 60)

    from hooks.pre_edit import should_block_edit, get_state_file

    # Remove state file
    state_file = get_state_file()
    if os.path.exists(state_file):
        os.remove(state_file)

    # Test allowing for non-code files
    test_files = [
        "README.md",
        "config.json",
        "data.txt",
        ".gitignore"
    ]

    for file in test_files:
        result = should_block_edit(file, "Write")
        print(f"should_block_edit('{file}', 'Write') = {result}")
        assert result == False, f"Should allow {file} without context"

    print("✓ Pre-edit hook correctly allows non-code files")

    return True


def test_conversation_id_fallback():
    """Test conversation ID fallback logic"""
    print("\n" + "=" * 60)
    print("TEST 5: Conversation ID fallback")
    print("=" * 60)

    from hooks.pre_edit import get_conversation_id

    # Remove env var to test fallback
    old_val = os.environ.get("CLAUDE_CONVERSATION_ID")
    if old_val:
        del os.environ["CLAUDE_CONVERSATION_ID"]

    conv_id = get_conversation_id()

    print(f"Conversation ID (fallback): {conv_id}")

    assert conv_id is not None, "Should return fallback conversation ID"
    assert len(conv_id) > 0, "Conversation ID should not be empty"

    print("✓ Conversation ID fallback works")

    # Restore env var
    if old_val:
        os.environ["CLAUDE_CONVERSATION_ID"] = old_val

    return True


if __name__ == "__main__":
    print("\nEnforcement Tests: PreToolUse Hook\n")

    tests = [
        test_state_file_creation,
        test_pre_edit_hook_blocks_without_context,
        test_pre_edit_hook_allows_with_context,
        test_pre_edit_hook_allows_non_code_files,
        test_conversation_id_fallback,
    ]

    passed = 0
    failed = 0

    for test in tests:
        try:
            if test():
                passed += 1
        except Exception as e:
            print(f"\nX TEST FAILED: {e}")
            failed += 1

    print("\n" + "=" * 60)
    print(f"RESULTS: {passed} passed, {failed} failed")
    print("=" * 60)

    sys.exit(0 if failed == 0 else 1)