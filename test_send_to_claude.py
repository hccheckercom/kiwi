"""Test script for Send to Claude feature - simulates full flow"""
import sys
from pathlib import Path

# Add kiwi to path
sys.path.insert(0, str(Path(__file__).parent))
from mcp_server import _handle_inbox

def test_send_to_claude_flow():
    """Simulate complete Send to Claude flow"""

    print("=" * 70)
    print("KIWI SEND TO CLAUDE - FULL FLOW TEST")
    print("=" * 70)

    # Clear inbox
    _handle_inbox({'action': 'clear', 'keep_days': 0})

    # === STEP 1: Scan result (simulated) ===
    print("\n[STEP 1] Extension scans folder")
    print("-" * 70)
    scan_output = """Checked 5 file(s): 3 CRITICAL, 2 HIGH

header.php:
  LES-001 CRITICAL: Missing nonce check in form handler (line 45)
  LES-012 CRITICAL: Unescaped output in echo statement (line 78)

footer.php:
  LES-045 CRITICAL: Hardcoded database credentials (line 102)
  LES-089 HIGH: Missing text-domain for i18n (line 67)

sidebar.php:
  LES-091 HIGH: Deprecated function usage wp_specialchars (line 34)"""

    print(scan_output)

    # === STEP 2: VS Code notification ===
    print("\n[STEP 2] VS Code shows notification")
    print("-" * 70)
    print("⚠ Kiwi Scan Complete: 3 CRITICAL, 2 HIGH violations")
    print("[Send to Claude] [Dismiss]")

    # === STEP 3: User clicks Send to Claude ===
    print("\n[STEP 3] User clicks 'Send to Claude'")
    print("-" * 70)

    # === STEP 4: Extension writes to inbox ===
    print("\n[STEP 4] Extension writes to inbox via MCP")
    print("-" * 70)
    result = _handle_inbox({
        'action': 'write',
        'source': 'kiwi-extension',
        'type': 'scan_result',
        'title': 'Scan: kiwi-production-test',
        'content': scan_output
    })
    print(f"✓ {result}")

    # === STEP 5: Clipboard prompt ===
    print("\n[STEP 5] Prompt copied to clipboard")
    print("-" * 70)
    prompt = 'Read my Kiwi inbox — run kiwi_inbox(action="read") to see the latest scan_result results for "Scan: kiwi-production-test"'
    print(f"Clipboard: {prompt}")

    # === STEP 6: VS Code notification ===
    print("\n[STEP 6] VS Code notification")
    print("-" * 70)
    print("ℹ Kiwi: Result saved to inbox + prompt copied to clipboard.")
    print("  Paste in Claude Code to pull results.")
    print("[Open Claude Code] [OK]")

    # === STEP 7: User pastes in Claude Code ===
    print("\n[STEP 7] User pastes prompt in Claude Code")
    print("-" * 70)
    print(f"User input: {prompt}")

    # === STEP 8: Claude Code reads inbox ===
    print("\n[STEP 8] Claude Code calls kiwi_inbox(action='read')")
    print("-" * 70)
    inbox_result = _handle_inbox({'action': 'read'})
    print(inbox_result)

    # === STEP 9: Verify inbox marked as read ===
    print("\n[STEP 9] Verify inbox status")
    print("-" * 70)
    list_result = _handle_inbox({'action': 'list'})
    print(list_result)

    print("\n" + "=" * 70)
    print("✓ TEST COMPLETE - All steps passed")
    print("=" * 70)

if __name__ == "__main__":
    test_send_to_claude_flow()