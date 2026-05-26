"""Conflict detection and resolution for concurrent edits."""

from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Dict, List, Optional, Set
import hashlib


class ConflictType(Enum):
    """Types of conflicts that can occur."""
    SAME_FILE_EDIT = "same_file_edit"           # Two users editing same file
    SAME_LINE_EDIT = "same_line_edit"           # Two users editing same lines
    DISMISS_CONFLICT = "dismiss_conflict"       # One dismissed, one fixed
    FIX_CONFLICT = "fix_conflict"               # Two different fixes applied


@dataclass
class FileEdit:
    """Record of a file edit."""
    user_id: int
    file_path: str
    content_hash: str
    timestamp: datetime
    line_start: Optional[int] = None
    line_end: Optional[int] = None


@dataclass
class Conflict:
    """Detected conflict between concurrent edits."""
    conflict_type: ConflictType
    file_path: str
    user1_id: int
    user2_id: int
    user1_edit: FileEdit
    user2_edit: FileEdit
    detected_at: datetime
    resolved: bool = False
    resolution: Optional[str] = None


class ConflictDetector:
    """Detect conflicts between concurrent user actions."""

    def __init__(self):
        """Initialize conflict detector."""
        self.active_edits: Dict[str, List[FileEdit]] = {}
        self.file_locks: Dict[str, int] = {}  # file_path -> user_id

    def register_edit(
        self,
        user_id: int,
        file_path: str,
        content: str,
        line_start: Optional[int] = None,
        line_end: Optional[int] = None
    ) -> Optional[Conflict]:
        """
        Register a file edit and detect conflicts.

        Args:
            user_id: User making the edit
            file_path: Path to file being edited
            content: New file content
            line_start: Optional start line of edit
            line_end: Optional end line of edit

        Returns:
            Conflict if detected, None otherwise
        """
        content_hash = self._hash_content(content)
        edit = FileEdit(
            user_id=user_id,
            file_path=file_path,
            content_hash=content_hash,
            timestamp=datetime.utcnow(),
            line_start=line_start,
            line_end=line_end
        )

        # Check for conflicts with active edits
        if file_path in self.active_edits:
            for existing_edit in self.active_edits[file_path]:
                if existing_edit.user_id != user_id:
                    conflict = self._detect_conflict(existing_edit, edit)
                    if conflict:
                        return conflict

        # Register this edit
        if file_path not in self.active_edits:
            self.active_edits[file_path] = []
        self.active_edits[file_path].append(edit)

        return None

    def _detect_conflict(self, edit1: FileEdit, edit2: FileEdit) -> Optional[Conflict]:
        """Detect conflict between two edits."""
        # Same file, different users
        if edit1.file_path != edit2.file_path:
            return None

        if edit1.user_id == edit2.user_id:
            return None

        # Check for line overlap
        if edit1.line_start and edit1.line_end and edit2.line_start and edit2.line_end:
            if self._lines_overlap(
                edit1.line_start, edit1.line_end,
                edit2.line_start, edit2.line_end
            ):
                return Conflict(
                    conflict_type=ConflictType.SAME_LINE_EDIT,
                    file_path=edit1.file_path,
                    user1_id=edit1.user_id,
                    user2_id=edit2.user_id,
                    user1_edit=edit1,
                    user2_edit=edit2,
                    detected_at=datetime.utcnow()
                )

        # Same file edit (no line info or no overlap)
        return Conflict(
            conflict_type=ConflictType.SAME_FILE_EDIT,
            file_path=edit1.file_path,
            user1_id=edit1.user_id,
            user2_id=edit2.user_id,
            user1_edit=edit1,
            user2_edit=edit2,
            detected_at=datetime.utcnow()
        )

    def _lines_overlap(
        self, start1: int, end1: int, start2: int, end2: int
    ) -> bool:
        """Check if two line ranges overlap."""
        return not (end1 < start2 or end2 < start1)

    def _hash_content(self, content: str) -> str:
        """Hash file content for comparison."""
        return hashlib.sha256(content.encode('utf-8')).hexdigest()

    def acquire_lock(self, user_id: int, file_path: str) -> bool:
        """
        Acquire exclusive lock on a file.

        Args:
            user_id: User requesting lock
            file_path: Path to file

        Returns:
            True if lock acquired, False if already locked by another user
        """
        if file_path in self.file_locks:
            if self.file_locks[file_path] != user_id:
                return False

        self.file_locks[file_path] = user_id
        return True

    def release_lock(self, user_id: int, file_path: str) -> bool:
        """
        Release lock on a file.

        Args:
            user_id: User releasing lock
            file_path: Path to file

        Returns:
            True if lock released, False if not held by this user
        """
        if file_path not in self.file_locks:
            return False

        if self.file_locks[file_path] != user_id:
            return False

        del self.file_locks[file_path]
        return True

    def clear_edits(self, file_path: str):
        """Clear edit history for a file."""
        if file_path in self.active_edits:
            del self.active_edits[file_path]


class ConflictResolver:
    """Resolve conflicts between concurrent edits."""

    def merge_fixes(
        self, fix1: str, fix2: str, original: str
    ) -> Optional[str]:
        """
        Attempt to merge two fixes to the same file.

        Args:
            fix1: First fix content
            fix2: Second fix content
            original: Original file content

        Returns:
            Merged content if successful, None if manual resolution needed
        """
        # Simple line-based merge
        lines_original = original.splitlines()
        lines_fix1 = fix1.splitlines()
        lines_fix2 = fix2.splitlines()

        # If both fixes are identical, no conflict
        if fix1 == fix2:
            return fix1

        # If one fix is a superset of the other, use the larger one
        if fix1 in fix2:
            return fix2
        if fix2 in fix1:
            return fix1

        # Try three-way merge (simplified)
        try:
            merged = self._three_way_merge(
                lines_original, lines_fix1, lines_fix2
            )
            return "\n".join(merged)
        except Exception as e:
            import sys
            print(f"[kiwi] merge_fixes error: {e}", file=sys.stderr)
            return None

    def _three_way_merge(
        self, base: List[str], left: List[str], right: List[str]
    ) -> List[str]:
        """
        Simplified three-way merge.

        Args:
            base: Original lines
            left: First fix lines
            right: Second fix lines

        Returns:
            Merged lines

        Raises:
            Exception if merge conflict detected
        """
        # This is a simplified implementation
        # Real implementation would use diff3 or similar algorithm

        if left == right:
            return left

        # If one side unchanged, use the other
        if left == base:
            return right
        if right == base:
            return left

        # Both sides changed - conflict
        raise Exception("Merge conflict: both sides modified")

    def suggest_resolution(self, conflict: Conflict) -> str:
        """
        Suggest resolution strategy for a conflict.

        Args:
            conflict: Detected conflict

        Returns:
            Human-readable resolution suggestion
        """
        if conflict.conflict_type == ConflictType.SAME_LINE_EDIT:
            return (
                f"Manual merge required: both users edited lines "
                f"{conflict.user1_edit.line_start}-{conflict.user1_edit.line_end}. "
                f"Review both changes and create a merged version."
            )

        if conflict.conflict_type == ConflictType.SAME_FILE_EDIT:
            return (
                f"File lock recommended: both users editing {conflict.file_path}. "
                f"Consider using file locks to prevent concurrent edits."
            )

        return "Manual review required."