"""Rollback Mechanism for Failed Generations"""

from pathlib import Path
from typing import Dict, Any, List
import shutil
import json
from datetime import datetime


class GenerationRollback:
    """Handle rollback of failed generations."""

    def __init__(self, backup_dir: str = ".claude/kiwi/generator/.backups"):
        self.backup_dir = Path(backup_dir)
        self.backup_dir.mkdir(parents=True, exist_ok=True)

    def create_backup(self, gen_id: str, theme_path: str) -> str:
        """
        Create backup of theme directory before generation.

        Args:
            gen_id: Generation ID
            theme_path: Path to theme directory

        Returns:
            Backup path
        """
        theme_dir = Path(theme_path)

        if not theme_dir.exists():
            # No existing theme, no backup needed
            return None

        # Create backup directory
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_path = self.backup_dir / f"{gen_id}_{timestamp}"

        # Copy theme directory
        shutil.copytree(theme_dir, backup_path)

        # Save metadata
        metadata = {
            "gen_id": gen_id,
            "theme_path": str(theme_dir),
            "backup_path": str(backup_path),
            "timestamp": timestamp,
            "files_count": sum(1 for _ in backup_path.rglob("*") if _.is_file())
        }

        metadata_file = backup_path / ".backup_metadata.json"
        with open(metadata_file, "w", encoding="utf-8") as f:
            json.dump(metadata, f, indent=2)

        return str(backup_path)

    def rollback(self, gen_id: str, backup_path: str) -> bool:
        """
        Rollback to backup.

        Args:
            gen_id: Generation ID
            backup_path: Path to backup directory

        Returns:
            True if rollback successful
        """
        backup_dir = Path(backup_path)

        if not backup_dir.exists():
            raise ValueError(f"Backup not found: {backup_path}")

        # Load metadata
        metadata_file = backup_dir / ".backup_metadata.json"
        if not metadata_file.exists():
            raise ValueError(f"Backup metadata not found: {metadata_file}")

        with open(metadata_file, "r", encoding="utf-8") as f:
            metadata = json.load(f)

        theme_path = Path(metadata["theme_path"])

        # Remove current theme directory
        if theme_path.exists():
            shutil.rmtree(theme_path)

        # Restore from backup
        shutil.copytree(backup_dir, theme_path)

        # Remove metadata file from restored directory
        (theme_path / ".backup_metadata.json").unlink(missing_ok=True)

        return True

    def cleanup_backup(self, backup_path: str):
        """Remove backup after successful generation."""
        backup_dir = Path(backup_path)

        if backup_dir.exists():
            shutil.rmtree(backup_dir)

    def list_backups(self) -> List[Dict[str, Any]]:
        """List all available backups."""
        backups = []

        for backup_dir in self.backup_dir.iterdir():
            if not backup_dir.is_dir():
                continue

            metadata_file = backup_dir / ".backup_metadata.json"
            if not metadata_file.exists():
                continue

            with open(metadata_file, "r", encoding="utf-8") as f:
                metadata = json.load(f)

            backups.append(metadata)

        return sorted(backups, key=lambda x: x["timestamp"], reverse=True)


def format_backup_report(backups: List[Dict[str, Any]]) -> str:
    """Format backup list for display."""
    if not backups:
        return "No backups found"

    lines = [
        "Available Backups:",
        "",
        f"{'Gen ID':<15} {'Timestamp':<20} {'Theme Path':<40} {'Files':<10}",
        "-" * 90
    ]

    for backup in backups:
        lines.append(
            f"{backup['gen_id']:<15} "
            f"{backup['timestamp']:<20} "
            f"{backup['theme_path']:<40} "
            f"{backup['files_count']:<10}"
        )

    return "\n".join(lines)