"""Merge KiwiPW into Kiwi Core — Unified Knowledge Base v3.0

Migrates all KiwiPW lessons, checkers, and infrastructure into Kiwi core.

Steps:
1. Rename PW-XXX → LES-XXX (674-726)
2. Move lessons to .claude/kiwi/lessons/
3. Move checkers to .claude/kiwi/scanner/checkers/
4. Merge _meta.json
5. Update MCP server
6. Rebuild index
7. Archive old KiwiPW folder

Usage:
    python .claude/kiwi/tools/merge_kiwipw.py [--dry-run] [--backup]
"""

import json
import re
import shutil
import sys
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Tuple

KIWI_DIR = Path(__file__).parent.parent
KIWIPW_DIR = KIWI_DIR.parent / "kiwipw"
BACKUP_DIR = KIWI_DIR.parent / "kiwipw.backup"


def load_json(path: Path) -> Dict:
    """Load JSON file with BOM handling."""
    with open(path, 'r', encoding='utf-8-sig') as f:
        return json.load(f)


def save_json(path: Path, data: Dict):
    """Save JSON file with pretty formatting."""
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    print(f"  ✓ Saved {path.name}")


def get_pw_lessons() -> List[Path]:
    """Get all PW-XXX.md lesson files."""
    lessons = []
    for md_file in (KIWIPW_DIR / "lessons").rglob("*.md"):
        if re.match(r'^PW-\d+\.md$', md_file.name):
            lessons.append(md_file)
    return sorted(lessons)


def rename_lesson_id(content: str, old_id: str, new_id: str) -> str:
    """Rename lesson ID in frontmatter and content."""
    # Update frontmatter
    content = re.sub(
        r'^id:\s*' + re.escape(old_id),
        f'id: {new_id}',
        content,
        flags=re.MULTILINE
    )

    # Update any references in content
    content = content.replace(old_id, new_id)

    return content


def migrate_lessons(dry_run: bool = False) -> Tuple[int, Dict[str, str]]:
    """Migrate PW-XXX lessons to LES-XXX.

    Returns:
        (count, mapping) where mapping is {old_id: new_id}
    """
    print("\n=== Step 1: Migrating Lessons ===")

    kiwi_meta = load_json(KIWI_DIR / "_meta.json")
    next_id = kiwi_meta['next_id']

    pw_lessons = get_pw_lessons()
    print(f"Found {len(pw_lessons)} KiwiPW lessons")
    print(f"Next Kiwi ID: LES-{next_id}")

    mapping = {}
    migrated = 0

    for pw_file in pw_lessons:
        # Extract PW-XXX
        old_id = pw_file.stem  # PW-002
        new_id = f"LES-{next_id}"
        mapping[old_id] = new_id

        # Read content
        content = pw_file.read_text(encoding='utf-8')

        # Rename ID
        new_content = rename_lesson_id(content, old_id, new_id)

        # Determine target path
        category = pw_file.parent.name
        target_dir = KIWI_DIR / "lessons" / category
        target_file = target_dir / f"{new_id}.md"

        if not dry_run:
            target_dir.mkdir(parents=True, exist_ok=True)
            target_file.write_text(new_content, encoding='utf-8')

        print(f"  {old_id} → {new_id} ({category})")

        next_id += 1
        migrated += 1

    print(f"\n✓ Migrated {migrated} lessons")
    return migrated, mapping


def migrate_checkers(dry_run: bool = False) -> int:
    """Migrate KiwiPW checkers to Kiwi core.

    Returns:
        Number of checkers migrated
    """
    print("\n=== Step 2: Migrating Checkers ===")

    source_dir = KIWIPW_DIR / "scanner" / "checkers"
    target_dir = KIWI_DIR / "scanner" / "checkers"

    checkers = [
        "responsive_coverage.py",
        "dark_coverage.py",
        "sibling_consistency.py",
        "class_conflict.py",
        "pattern_presence.py"  # May conflict with existing
    ]

    migrated = 0
    for checker in checkers:
        source = source_dir / checker
        target = target_dir / checker

        if not source.exists():
            print(f"  ⚠ {checker} not found, skipping")
            continue

        if target.exists():
            print(f"  ⚠ {checker} already exists in Kiwi, skipping")
            continue

        if not dry_run:
            shutil.copy2(source, target)

        print(f"  ✓ {checker}")
        migrated += 1

    print(f"\n✓ Migrated {migrated} checkers")
    return migrated


def merge_meta(dry_run: bool = False) -> Dict:
    """Merge KiwiPW _meta.json into Kiwi _meta.json.

    Returns:
        Merged metadata
    """
    print("\n=== Step 3: Merging Metadata ===")

    kiwi_meta = load_json(KIWI_DIR / "_meta.json")
    kiwipw_meta = load_json(KIWIPW_DIR / "_meta.json")

    # Update next_id
    old_next_id = kiwi_meta['next_id']
    new_next_id = old_next_id + kiwipw_meta['stats']['total']
    kiwi_meta['next_id'] = new_next_id

    print(f"  next_id: {old_next_id} → {new_next_id}")

    # Merge categories
    for cat, info in kiwipw_meta['categories'].items():
        if cat in kiwi_meta.get('categories', {}):
            # Category exists, update count
            kiwi_meta['categories'][cat]['count'] += info['count']
            print(f"  Updated category: {cat} (+{info['count']})")
        else:
            # New category
            if 'categories' not in kiwi_meta:
                kiwi_meta['categories'] = {}
            kiwi_meta['categories'][cat] = info
            print(f"  Added category: {cat} ({info['count']} lessons)")

    # Update platforms
    for platform, cats in kiwipw_meta['platforms'].items():
        if platform not in kiwi_meta['platforms']:
            kiwi_meta['platforms'][platform] = []

        for cat in cats:
            if cat not in kiwi_meta['platforms'][platform]:
                kiwi_meta['platforms'][platform].append(cat)
                print(f"  Added {cat} to {platform} platform")

    # Update last_updated
    kiwi_meta['last_updated'] = datetime.now().strftime("%Y-%m-%d")

    if not dry_run:
        save_json(KIWI_DIR / "_meta.json", kiwi_meta)

    print(f"\n✓ Merged metadata")
    return kiwi_meta


def update_mcp_server(dry_run: bool = False):
    """Update MCP server to support UI pattern checkers."""
    print("\n=== Step 4: Updating MCP Server ===")

    mcp_file = KIWI_DIR / "mcp_server.py"
    content = mcp_file.read_text(encoding='utf-8')

    # Check if already updated
    if 'responsive_coverage' in content:
        print("  ⚠ MCP server already supports UI checkers")
        return

    # Add import for new checkers
    import_section = """from scanner.checkers.responsive_coverage import ResponsiveCoverageChecker
from scanner.checkers.dark_coverage import DarkCoverageChecker
from scanner.checkers.sibling_consistency import SiblingConsistencyChecker
from scanner.checkers.class_conflict import ClassConflictChecker"""

    # Find import section and add
    if 'from scanner.checkers' in content:
        # Add after existing checker imports
        content = content.replace(
            'from scanner.checkers import get_checker',
            f'from scanner.checkers import get_checker\n{import_section}'
        )

    if not dry_run:
        mcp_file.write_text(content, encoding='utf-8')

    print("  ✓ Updated MCP server imports")


def rebuild_index(dry_run: bool = False):
    """Rebuild README.md index."""
    print("\n=== Step 5: Rebuilding Index ===")

    if dry_run:
        print("  (Skipped in dry-run mode)")
        return

    import subprocess
    result = subprocess.run(
        [sys.executable, str(KIWI_DIR / "tools" / "rebuild_index.py")],
        capture_output=True,
        text=True,
        cwd=str(KIWI_DIR)
    )

    if result.returncode == 0:
        print("  ✓ Index rebuilt successfully")
    else:
        print(f"  ⚠ Index rebuild failed: {result.stderr}")


def create_backup():
    """Create backup of KiwiPW before migration."""
    print("\n=== Creating Backup ===")

    if BACKUP_DIR.exists():
        print(f"  ⚠ Backup already exists at {BACKUP_DIR}")
        return

    shutil.copytree(KIWIPW_DIR, BACKUP_DIR)
    print(f"  ✓ Backup created at {BACKUP_DIR}")


def archive_kiwipw(dry_run: bool = False):
    """Archive old KiwiPW folder."""
    print("\n=== Step 6: Archiving KiwiPW ===")

    if dry_run:
        print("  (Skipped in dry-run mode)")
        return

    archive_path = KIWI_DIR.parent / f"kiwipw.archived.{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    shutil.move(str(KIWIPW_DIR), str(archive_path))
    print(f"  ✓ Archived to {archive_path.name}")


def main():
    import argparse

    parser = argparse.ArgumentParser(description="Merge KiwiPW into Kiwi Core")
    parser.add_argument('--dry-run', action='store_true', help='Preview changes without applying')
    parser.add_argument('--backup', action='store_true', help='Create backup before migration')
    parser.add_argument('--no-archive', action='store_true', help='Keep KiwiPW folder after migration')

    args = parser.parse_args()

    print("=" * 60)
    print("Kiwi + KiwiPW Merge — Unified Knowledge Base v3.0")
    print("=" * 60)

    if args.dry_run:
        print("\n⚠ DRY RUN MODE — No changes will be made\n")

    # Validate paths
    if not KIWIPW_DIR.exists():
        print(f"❌ KiwiPW not found at {KIWIPW_DIR}")
        sys.exit(1)

    if not KIWI_DIR.exists():
        print(f"❌ Kiwi not found at {KIWI_DIR}")
        sys.exit(1)

    # Create backup if requested
    if args.backup and not args.dry_run:
        create_backup()

    # Execute migration steps
    try:
        lesson_count, mapping = migrate_lessons(args.dry_run)
        checker_count = migrate_checkers(args.dry_run)
        merged_meta = merge_meta(args.dry_run)
        update_mcp_server(args.dry_run)
        rebuild_index(args.dry_run)

        if not args.no_archive and not args.dry_run:
            archive_kiwipw(args.dry_run)

        # Summary
        print("\n" + "=" * 60)
        print("Migration Complete!")
        print("=" * 60)
        print(f"✓ Migrated {lesson_count} lessons (PW-XXX → LES-XXX)")
        print(f"✓ Migrated {checker_count} checkers")
        print(f"✓ Updated _meta.json (next_id: {merged_meta['next_id']})")
        print(f"✓ Total lessons: {merged_meta['next_id'] - 1}")

        if args.dry_run:
            print("\n⚠ This was a dry run. Run without --dry-run to apply changes.")
        else:
            print("\n✓ All changes applied successfully!")
            print("\nNext steps:")
            print("  1. Test unified scanner: python -m scanner.cli --theme <path>")
            print("  2. Update CLAUDE.md to remove KiwiPW references")
            print("  3. Commit changes: git add . && git commit -m 'feat(kiwi): merge KiwiPW into core'")

    except Exception as e:
        print(f"\n❌ Migration failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
