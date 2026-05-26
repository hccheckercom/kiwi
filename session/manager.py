"""Session management: save and resume agent sessions."""

import json
import os
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional


class SessionManager:
    """Manage agent session persistence."""

    def __init__(self, session_dir: str = ".kiwi_sessions"):
        """
        Initialize session manager.

        Args:
            session_dir: Directory to store session files
        """
        self.session_dir = Path(session_dir)
        self.session_dir.mkdir(exist_ok=True)

    def save_session(
        self,
        session_id: str,
        state: Dict[str, Any],
        metadata: Optional[Dict[str, Any]] = None
    ) -> str:
        """
        Save agent session to disk.

        Args:
            session_id: Unique session identifier
            state: Session state to save
            metadata: Optional metadata (path, mode, severity, etc.)

        Returns:
            Path to saved session file
        """
        session_file = self.session_dir / f"{session_id}.json"

        session_data = {
            'session_id': session_id,
            'saved_at': datetime.utcnow().isoformat(),
            'metadata': metadata or {},
            'state': state
        }

        with open(session_file, 'w', encoding='utf-8') as f:
            json.dump(session_data, f, indent=2, ensure_ascii=False)

        return str(session_file)

    def load_session(self, session_id: str) -> Optional[Dict[str, Any]]:
        """
        Load agent session from disk.

        Args:
            session_id: Session identifier

        Returns:
            Session data or None if not found
        """
        session_file = self.session_dir / f"{session_id}.json"

        if not session_file.exists():
            return None

        with open(session_file, 'r', encoding='utf-8') as f:
            return json.load(f)

    def list_sessions(self) -> List[Dict[str, Any]]:
        """
        List all saved sessions.

        Returns:
            List of session metadata
        """
        sessions = []

        for session_file in self.session_dir.glob("*.json"):
            try:
                with open(session_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    sessions.append({
                        'session_id': data['session_id'],
                        'saved_at': data['saved_at'],
                        'metadata': data.get('metadata', {})
                    })
            except Exception as e:
                import sys
                print(f"[kiwi] session load error: {e}", file=sys.stderr)
                continue

        return sorted(sessions, key=lambda x: x['saved_at'], reverse=True)

    def delete_session(self, session_id: str) -> bool:
        """
        Delete saved session.

        Args:
            session_id: Session identifier

        Returns:
            True if deleted, False if not found
        """
        session_file = self.session_dir / f"{session_id}.json"

        if session_file.exists():
            session_file.unlink()
            return True

        return False

    def resume_session(self, session_id: str) -> Optional[Dict[str, Any]]:
        """
        Resume agent session from saved state.

        Args:
            session_id: Session identifier

        Returns:
            Session state ready for agent to resume, or None if not found
        """
        session_data = self.load_session(session_id)

        if not session_data:
            return None

        return {
            'session_id': session_data['session_id'],
            'resumed_at': datetime.utcnow().isoformat(),
            'original_saved_at': session_data['saved_at'],
            'metadata': session_data['metadata'],
            'state': session_data['state']
        }


class SessionStateBuilder:
    """Build session state from agent execution."""

    def build_state(
        self,
        iteration: int,
        violations: List[Dict[str, Any]],
        history: List[Dict[str, Any]],
        fixes_applied: int,
        tokens_used: int
    ) -> Dict[str, Any]:
        """
        Build session state snapshot.

        Args:
            iteration: Current iteration number
            violations: Remaining violations
            history: Execution history
            fixes_applied: Number of fixes applied so far
            tokens_used: Total tokens used

        Returns:
            Session state dict
        """
        return {
            'iteration': iteration,
            'violations': violations,
            'history': history,
            'fixes_applied': fixes_applied,
            'tokens_used': tokens_used,
            'timestamp': datetime.utcnow().isoformat()
        }

    def restore_state(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """
        Restore agent state from saved session.

        Args:
            state: Saved session state

        Returns:
            State ready for agent to continue
        """
        return {
            'iteration': state.get('iteration', 0),
            'violations': state.get('violations', []),
            'history': state.get('history', []),
            'fixes_applied': state.get('fixes_applied', 0),
            'tokens_used': state.get('tokens_used', 0),
            'resumed': True,
            'original_timestamp': state.get('timestamp')
        }


def generate_session_id(path: str, mode: str) -> str:
    """
    Generate unique session ID.

    Args:
        path: Project path
        mode: Agent mode (review, auto, etc.)

    Returns:
        Session ID (e.g., "wezone-plugins-auto-20260524-084530")
    """
    project_name = Path(path).name
    timestamp = datetime.utcnow().strftime("%Y%m%d-%H%M%S")
    return f"{project_name}-{mode}-{timestamp}"