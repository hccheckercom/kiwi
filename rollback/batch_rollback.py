"""Batch rollback wrapper for multi-file fixes."""

from pathlib import Path
from typing import List, Tuple
import sys

# Add kiwi to path
kiwi_dir = Path(__file__).parent.parent
sys.path.insert(0, str(kiwi_dir))

from scanner.models import Violation
from scanner.fixer import apply_fix, FixResult


class BatchRollback:
    """Manages batch rollback for multiple file fixes."""

    def __init__(self, project_path: str):
        self.project_path = Path(project_path)
        self.original_contents = {}  # file_path -> original_content
        self.fixed_files = []  # List of successfully fixed files

    def save_checkpoint(self, file_path: str) -> bool:
        """Save original content before fix."""
        try:
            content = Path(file_path).read_text(encoding="utf-8")
            self.original_contents[file_path] = content
            return True
        except Exception:
            return False

    def apply_fix_batch(
        self,
        violation: Violation,
        fix_config: dict,
        dry_run: bool = False
    ) -> FixResult:
        """Apply fix without running tests (deferred to batch end)."""
        # Save checkpoint before fix
        if not dry_run:
            self.save_checkpoint(violation.file)

        # Apply fix with rollback disabled (we handle it at batch level)
        result = apply_fix(violation, fix_config, dry_run=dry_run, enable_rollback=False)

        if result.success and not dry_run:
            self.fixed_files.append(violation.file)

        return result

    def verify_and_commit(self) -> Tuple[bool, str]:
        """Run tests once for all fixes. Rollback all if tests fail."""
        if not self.fixed_files:
            return True, "No files to verify"

        try:
            from rollback.test_verifier import TestVerifier

            # Run tests once for all fixes
            verifier = TestVerifier(str(self.project_path))
            test_safe, test_reason = verifier.verify_fix_safe(self.fixed_files[0])

            if not test_safe:
                # Tests failed, rollback ALL files
                self.rollback_all()
                return False, f"Tests failed after batch fixes ({test_reason}), rolled back {len(self.fixed_files)} files"

            # Tests passed, clear checkpoints
            self.original_contents.clear()
            self.fixed_files.clear()
            return True, f"All tests passed for {len(self.fixed_files)} files"

        except Exception as e:
            # Verification error, rollback to be safe
            self.rollback_all()
            return False, f"Verification error: {e}, rolled back {len(self.fixed_files)} files"

    def rollback_all(self) -> int:
        """Rollback all fixed files to original content."""
        rolled_back = 0
        for file_path, original_content in self.original_contents.items():
            try:
                Path(file_path).write_text(original_content, encoding="utf-8")
                rolled_back += 1
            except Exception:
                pass

        self.original_contents.clear()
        self.fixed_files.clear()
        return rolled_back