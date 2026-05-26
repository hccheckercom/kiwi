"""Standalone rollback CLI for manual rollback operations."""
import sys
import argparse
from pathlib import Path

# Add kiwi to path
KIWI_DIR = Path(__file__).parent.parent
sys.path.insert(0, str(KIWI_DIR))

from deploy.executor import DeployExecutor
from deploy.state import get_deploy_history, log_deploy


def main():
    parser = argparse.ArgumentParser(description="Kiwi Rollback CLI")
    parser.add_argument("path", help="Project path or name")
    parser.add_argument("type", choices=["wp_theme", "wp_plugin", "nextjs"], help="Deploy type")
    parser.add_argument("--target", default="staging", choices=["staging", "production"], help="Deploy target")
    parser.add_argument("--backup-path", help="Specific backup path to rollback to (optional)")

    args = parser.parse_args()

    # Resolve path
    path = Path(args.path)
    if not path.is_absolute():
        candidates = [
            Path.cwd() / args.path,
            Path("d:/projects/wezone") / args.path,
            Path("d:/projects/wezone/themes") / args.path,
            Path("d:/projects/wezone/wezone-plugins") / args.path,
        ]
        for candidate in candidates:
            if candidate.exists():
                path = candidate
                break

    if not path.exists():
        print(f"ERROR: Path not found: {path}", file=sys.stderr)
        sys.exit(1)

    path = str(path.resolve())

    # Create executor
    executor = DeployExecutor(path, args.type, args.target)

    # Get git commit
    git_commit = executor.get_git_commit()

    # Show recent deploy history
    print(f"\nRecent deploys for {path}:", file=sys.stderr)
    history = get_deploy_history(path, limit=5)
    if history:
        for i, deploy in enumerate(history, 1):
            status = "✅" if deploy["success"] else "❌"
            rollback_flag = " [ROLLBACK]" if deploy["rollback"] else ""
            backup_info = f" (backup: {deploy['backup_path']})" if deploy.get("backup_path") else ""
            print(f"  {i}. {status} {deploy['timestamp'][:19]} — {deploy['git_commit'][:7]}{rollback_flag}{backup_info}", file=sys.stderr)
    else:
        print("  No deploy history found", file=sys.stderr)

    # Perform rollback
    print(f"\nRolling back {args.type} at {path}...", file=sys.stderr)
    result = executor.rollback(args.backup_path)

    if result.get("status") == "success":
        print(f"\n✅ Rollback successful", file=sys.stderr)
        print(f"Restored from: {result.get('backup_path', 'latest backup')}", file=sys.stderr)
        # Log rollback event
        log_deploy(
            path,
            args.type,
            args.target,
            git_commit,
            success=True,
            duration_ms=0,
            rollback=True,
            backup_path=result.get("backup_path")
        )
        sys.exit(0)
    else:
        print(f"\n❌ Rollback failed: {result.get('error', 'Unknown error')}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()