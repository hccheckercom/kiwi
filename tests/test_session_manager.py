"""Test session save/resume functionality."""

import json
import sys
from pathlib import Path

# Add kiwi to path
KIWI_DIR = Path(__file__).parent.parent
sys.path.insert(0, str(KIWI_DIR))

from session.manager import SessionManager, SessionStateBuilder, generate_session_id


def test_session_save_and_load():
    """Test basic save and load."""
    manager = SessionManager(session_dir=".kiwi_sessions_test")

    # Create test state
    state = {
        'iteration': 3,
        'violations': [{'lesson_id': 'LES-001', 'file': 'test.php'}],
        'history': [{'action': 'scan', 'detail': 'found 5 violations'}],
        'fixes_applied': 2,
        'tokens_used': 15000
    }

    metadata = {
        'path': 'wezone-plugins',
        'mode': 'auto',
        'severity': 'CRITICAL'
    }

    # Save session
    session_id = 'test-session-001'
    session_file = manager.save_session(session_id, state, metadata)

    print(f"[PASS] Session saved to: {session_file}")

    # Load session
    loaded = manager.load_session(session_id)

    assert loaded is not None
    assert loaded['session_id'] == session_id
    assert loaded['state']['iteration'] == 3
    assert loaded['state']['fixes_applied'] == 2
    assert loaded['metadata']['path'] == 'wezone-plugins'

    print("[PASS] Session loaded successfully")

    # Cleanup
    manager.delete_session(session_id)
    print("[PASS] Session deleted")


def test_session_resume():
    """Test resume functionality."""
    manager = SessionManager(session_dir=".kiwi_sessions_test")

    state = {
        'iteration': 5,
        'violations': [],
        'history': [],
        'fixes_applied': 10,
        'tokens_used': 50000
    }

    session_id = 'test-resume-001'
    manager.save_session(session_id, state)

    # Resume session
    resumed = manager.resume_session(session_id)

    assert resumed is not None
    assert resumed['state']['iteration'] == 5
    assert resumed['state']['fixes_applied'] == 10
    assert 'resumed_at' in resumed

    print("[PASS] Session resumed successfully")

    # Cleanup
    manager.delete_session(session_id)


def test_list_sessions():
    """Test listing sessions."""
    manager = SessionManager(session_dir=".kiwi_sessions_test")

    # Create multiple sessions
    for i in range(3):
        session_id = f'test-list-{i:03d}'
        state = {'iteration': i}
        manager.save_session(session_id, state)

    # List sessions
    sessions = manager.list_sessions()

    assert len(sessions) >= 3
    assert all('session_id' in s for s in sessions)
    assert all('saved_at' in s for s in sessions)

    print(f"[PASS] Listed {len(sessions)} sessions")

    # Cleanup
    for i in range(3):
        manager.delete_session(f'test-list-{i:03d}')


def test_session_state_builder():
    """Test state builder."""
    builder = SessionStateBuilder()

    state = builder.build_state(
        iteration=2,
        violations=[{'lesson_id': 'LES-001'}],
        history=[{'action': 'scan'}],
        fixes_applied=5,
        tokens_used=10000
    )

    assert state['iteration'] == 2
    assert state['fixes_applied'] == 5
    assert 'timestamp' in state

    print("[PASS] State builder works")

    # Test restore
    restored = builder.restore_state(state)

    assert restored['iteration'] == 2
    assert restored['resumed'] is True
    assert 'original_timestamp' in restored

    print("[PASS] State restore works")


def test_generate_session_id():
    """Test session ID generation."""
    session_id = generate_session_id('wezone-plugins', 'auto')

    assert 'wezone-plugins' in session_id
    assert 'auto' in session_id
    assert len(session_id) > 20  # Should include timestamp

    print(f"[PASS] Generated session ID: {session_id}")


if __name__ == "__main__":
    print("Running session manager tests...")
    print("=" * 60)

    try:
        test_session_save_and_load()
        test_session_resume()
        test_list_sessions()
        test_session_state_builder()
        test_generate_session_id()

        print("=" * 60)
        print("[SUCCESS] All session manager tests passed!")

        # Cleanup test directory
        import shutil
        test_dir = Path(".kiwi_sessions_test")
        if test_dir.exists():
            shutil.rmtree(test_dir)
            print("[CLEANUP] Test directory removed")

    except AssertionError as e:
        print(f"[FAIL] Test failed: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"[ERROR] {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)