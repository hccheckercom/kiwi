"""Test multi-file rollback functionality."""

import sys
from pathlib import Path

# Add kiwi to path
KIWI_DIR = Path(__file__).parent.parent
sys.path.insert(0, str(KIWI_DIR))

from rollback.git_rollback import GitRollback


def test_multi_file_rollback():
    """Test batch mode for multi-file rollback."""
    rollback = GitRollback(str(KIWI_DIR.parent.parent))

    # Start batch mode
    rollback.start_batch()
    assert rollback.batch_mode is True
    print("[PASS] Batch mode started")

    # Simulate multiple file fixes
    files = ["file1.php", "file2.php", "file3.php"]
    rollback.create_checkpoint(files)

    assert len(rollback.batch_files) == 3
    print(f"[PASS] Tracked {len(rollback.batch_files)} files in batch")

    # End batch with success
    rollback.end_batch(success=True)
    assert rollback.batch_mode is False
    assert len(rollback.batch_files) == 0
    print("[PASS] Batch ended successfully")


def test_multi_file_rollback_on_failure():
    """Test rollback all files when one fails."""
    rollback = GitRollback(str(KIWI_DIR.parent.parent))

    rollback.start_batch()
    files = ["file1.php", "file2.php"]
    rollback.create_checkpoint(files)

    # Simulate failure - should rollback all
    rollback.end_batch(success=False)

    assert rollback.batch_mode is False
    print("[PASS] Batch rollback on failure")


if __name__ == "__main__":
    print("Running multi-file rollback tests...")
    print("=" * 60)

    try:
        test_multi_file_rollback()
        test_multi_file_rollback_on_failure()

        print("=" * 60)
        print("[SUCCESS] All multi-file rollback tests passed!")

    except AssertionError as e:
        print(f"[FAIL] Test failed: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"[ERROR] {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)