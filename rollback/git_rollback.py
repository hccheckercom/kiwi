"""Git-based rollback system for Kiwi auto-fix."""

import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Optional


@dataclass
class RollbackState:
    """Tracks rollback state for a fix operation."""
    stash_ref: Optional[str] = None
    files_modified: list[str] = None
    can_rollback: bool = False

    def __post_init__(self):
        if self.files_modified is None:
            self.files_modified = []


class GitRollback:
    """Manages git stash-based rollback for fixes."""

    def __init__(self, project_path: str):
        self.project_path = Path(project_path)
        self.state = RollbackState()
        self.batch_mode = False  # Track if in batch/multi-file mode
        self.batch_files = []  # Files in current batch

    def start_batch(self):
        """Start batch mode for multi-file rollback."""
        self.batch_mode = True
        self.batch_files = []

    def end_batch(self, success: bool):
        """
        End batch mode and cleanup or rollback.

        Args:
            success: True if all fixes succeeded, False to rollback all
        """
        if not self.batch_mode:
            return

        if success:
            self.cleanup()
        else:
            self.rollback()

        self.batch_mode = False
        self.batch_files = []

    def create_checkpoint(self, files: list[str]) -> bool:
        """
        Create git stash checkpoint before applying fixes.

        Args:
            files: List of file paths that will be modified

        Returns:
            True if checkpoint created successfully
        """
        # Track files in batch mode
        if self.batch_mode:
            self.batch_files.extend(files)

        try:
            # Check if we're in a git repo
            result = subprocess.run(
                ["git", "rev-parse", "--git-dir"],
                cwd=self.project_path,
                capture_output=True,
                text=True,
                timeout=5,
            )
            if result.returncode != 0:
                return False

            # Check if there are any changes to stash
            status_result = subprocess.run(
                ["git", "status", "--porcelain"],
                cwd=self.project_path,
                capture_output=True,
                text=True,
                timeout=5,
            )

            if not status_result.stdout.strip():
                # No changes to stash, but we can still track files
                self.state.files_modified = files
                self.state.can_rollback = False
                return True

            # Create stash with descriptive message
            stash_message = f"kiwi-checkpoint: before fixing {len(files)} file(s)"
            stash_result = subprocess.run(
                ["git", "stash", "push", "-m", stash_message, "--"] + files,
                cwd=self.project_path,
                capture_output=True,
                text=True,
                timeout=10,
            )

            if stash_result.returncode == 0:
                # Get stash ref
                ref_result = subprocess.run(
                    ["git", "rev-parse", "stash@{0}"],
                    cwd=self.project_path,
                    capture_output=True,
                    text=True,
                    timeout=5,
                )

                if ref_result.returncode == 0:
                    self.state.stash_ref = ref_result.stdout.strip()
                    self.state.files_modified = files
                    self.state.can_rollback = True
                    return True

            return False

        except (subprocess.TimeoutExpired, subprocess.SubprocessError, FileNotFoundError):
            return False

    def rollback(self) -> tuple[bool, str]:
        """
        Rollback to checkpoint by applying stashed changes.

        Returns:
            (success, message) tuple
        """
        if not self.state.can_rollback:
            return False, "No checkpoint available for rollback"

        try:
            # Apply stash
            result = subprocess.run(
                ["git", "stash", "pop"],
                cwd=self.project_path,
                capture_output=True,
                text=True,
                timeout=10,
            )

            if result.returncode == 0:
                self.state.can_rollback = False
                self.state.stash_ref = None
                return True, f"Rolled back {len(self.state.files_modified)} file(s)"
            else:
                error = result.stderr.strip() or result.stdout.strip()
                return False, f"Rollback failed: {error}"

        except subprocess.TimeoutExpired:
            return False, "Rollback timed out"
        except (subprocess.SubprocessError, FileNotFoundError) as e:
            return False, f"Rollback error: {e}"

    def cleanup(self):
        """Clean up stash if rollback wasn't needed."""
        if self.state.can_rollback and self.state.stash_ref:
            try:
                # Drop the stash
                subprocess.run(
                    ["git", "stash", "drop", "stash@{0}"],
                    cwd=self.project_path,
                    capture_output=True,
                    timeout=5,
                )
            except (subprocess.SubprocessError, OSError):
                pass  # Best effort cleanup

        self.state = RollbackState()


def verify_fix_safety(file_path: str, original_content: str) -> tuple[bool, str]:
    """
    Verify that a fix didn't break the file.

    Args:
        file_path: Path to fixed file
        original_content: Original file content before fix

    Returns:
        (is_safe, reason) tuple
    """
    try:
        path = Path(file_path)
        if not path.exists():
            return False, "File was deleted"

        new_content = path.read_text(encoding="utf-8")

        # Check 1: File not empty
        if not new_content.strip():
            return False, "File is now empty"

        # Check 2: File size didn't change drastically (>50% change is suspicious)
        size_ratio = len(new_content) / max(len(original_content), 1)
        if size_ratio < 0.5 or size_ratio > 2.0:
            return False, f"File size changed drastically ({size_ratio:.1%})"

        # Check 3: PHP syntax check (if PHP file)
        if file_path.endswith(".php"):
            result = subprocess.run(
                ["php", "-l", file_path],
                capture_output=True,
                text=True,
                timeout=5,
            )
            if result.returncode != 0:
                error = result.stderr.strip() or result.stdout.strip()
                return False, f"PHP syntax error: {error}"

        # Check 4: JS syntax check (if JS file)
        if file_path.endswith((".js", ".jsx")):
            # Basic check: count braces
            open_braces = new_content.count("{")
            close_braces = new_content.count("}")
            if abs(open_braces - close_braces) > 2:  # Allow small mismatch in strings
                return False, f"Unbalanced braces: {open_braces} open, {close_braces} close"

        return True, "File appears safe"

    except Exception as e:
        return False, f"Verification error: {e}"