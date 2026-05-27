"""Test rollback system - backup and restore verification"""

import unittest
import tempfile
import shutil
from pathlib import Path
import sys

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from rollback import GenerationRollback


class TestRollbackSystem(unittest.TestCase):
    """Test backup and restore functionality."""

    def setUp(self):
        """Create temporary directories for testing."""
        self.test_dir = Path(tempfile.mkdtemp())
        self.backup_dir = self.test_dir / ".backups"
        self.theme_dir = self.test_dir / "themes" / "test-theme"

        # Create test theme with some files
        self.theme_dir.mkdir(parents=True)
        (self.theme_dir / "style.css").write_text("/* Original CSS */", encoding="utf-8")
        (self.theme_dir / "functions.php").write_text("<?php // Original", encoding="utf-8")

        self.rollback = GenerationRollback(backup_dir=str(self.backup_dir))

    def tearDown(self):
        """Clean up test directories."""
        if self.test_dir.exists():
            shutil.rmtree(self.test_dir)

    def test_create_backup(self):
        """Test backup creation."""
        gen_id = "test-gen-001"

        backup_path = self.rollback.create_backup(gen_id, str(self.theme_dir))

        # Verify backup was created
        self.assertIsNotNone(backup_path)
        self.assertTrue(Path(backup_path).exists())

        # Verify files were copied
        backup_dir = Path(backup_path)
        self.assertTrue((backup_dir / "style.css").exists())
        self.assertTrue((backup_dir / "functions.php").exists())

        # Verify metadata
        metadata_file = backup_dir / ".backup_metadata.json"
        self.assertTrue(metadata_file.exists())

    def test_backup_nonexistent_theme(self):
        """Test backup of non-existent theme returns None."""
        gen_id = "test-gen-002"
        nonexistent = self.test_dir / "themes" / "nonexistent"

        backup_path = self.rollback.create_backup(gen_id, str(nonexistent))

        self.assertIsNone(backup_path)

    def test_rollback_restore(self):
        """Test rollback restores original files."""
        gen_id = "test-gen-003"

        # Create backup
        backup_path = self.rollback.create_backup(gen_id, str(self.theme_dir))

        # Modify theme files (simulate generation)
        (self.theme_dir / "style.css").write_text("/* Modified CSS */", encoding="utf-8")
        (self.theme_dir / "new-file.php").write_text("<?php // New", encoding="utf-8")

        # Verify modifications
        self.assertEqual(
            (self.theme_dir / "style.css").read_text(encoding="utf-8"),
            "/* Modified CSS */"
        )
        self.assertTrue((self.theme_dir / "new-file.php").exists())

        # Rollback
        success = self.rollback.rollback(gen_id, backup_path)

        self.assertTrue(success)

        # Verify original content restored
        self.assertEqual(
            (self.theme_dir / "style.css").read_text(encoding="utf-8"),
            "/* Original CSS */"
        )

        # Verify new file was removed
        self.assertFalse((self.theme_dir / "new-file.php").exists())

        # Verify metadata file was removed from restored directory
        self.assertFalse((self.theme_dir / ".backup_metadata.json").exists())

    def test_cleanup_backup(self):
        """Test backup cleanup."""
        gen_id = "test-gen-004"

        # Create backup
        backup_path = self.rollback.create_backup(gen_id, str(self.theme_dir))
        self.assertTrue(Path(backup_path).exists())

        # Cleanup
        self.rollback.cleanup_backup(backup_path)

        # Verify backup was removed
        self.assertFalse(Path(backup_path).exists())

    def test_list_backups(self):
        """Test listing available backups."""
        # Create multiple backups
        gen_id_1 = "test-gen-005"
        gen_id_2 = "test-gen-006"

        backup_1 = self.rollback.create_backup(gen_id_1, str(self.theme_dir))
        backup_2 = self.rollback.create_backup(gen_id_2, str(self.theme_dir))

        # List backups
        backups = self.rollback.list_backups()

        # Verify both backups are listed
        self.assertEqual(len(backups), 2)

        gen_ids = [b["gen_id"] for b in backups]
        self.assertIn(gen_id_1, gen_ids)
        self.assertIn(gen_id_2, gen_ids)

        # Verify sorted by timestamp (most recent first)
        self.assertEqual(backups[0]["gen_id"], gen_id_2)
        self.assertEqual(backups[1]["gen_id"], gen_id_1)


if __name__ == "__main__":
    unittest.main()