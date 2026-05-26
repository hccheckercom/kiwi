"""Git Commit and Push Module — Integrated into Kiwi."""
import subprocess
import sys
from pathlib import Path

def find_project_root():
    """Find git project root by looking for .git/."""
    current = Path.cwd()
    for parent in [current] + list(current.parents):
        if (parent / '.git').exists():
            return parent
    raise RuntimeError("Not in git repository. Cannot find .git/")

def get_git_status():
    """Get git status."""
    result = subprocess.run(
        ['git', 'status', '--short'],
        capture_output=True,
        text=True,
        check=True,
        timeout=30,
    )
    return result.stdout.strip()

def get_git_branch():
    """Get current branch name."""
    result = subprocess.run(
        ['git', 'branch', '--show-current'],
        capture_output=True,
        text=True,
        check=True,
        timeout=30,
    )
    return result.stdout.strip()

def git_add_all():
    """Stage all changes."""
    subprocess.run(['git', 'add', '-A'], check=True, timeout=30)

def git_commit(message):
    """Create commit with message."""
    subprocess.run(['git', 'commit', '-m', message], check=True, timeout=30)

def git_push():
    """Push to remote with auto-setup upstream."""
    result = subprocess.run(['git', 'push'], capture_output=True, text=True, encoding='utf-8', timeout=60)
    if result.returncode != 0:
        # Check if it's the "no upstream" error
        if 'has no upstream branch' in result.stderr:
            # Get current branch
            branch = get_git_branch()
            print(f"Setting upstream for branch: {branch}")
            subprocess.run(['git', 'push', '--set-upstream', 'origin', branch], check=True, timeout=60)
        else:
            # Re-raise other errors
            raise subprocess.CalledProcessError(result.returncode, 'git push', result.stdout, result.stderr)

def commit_and_push(message=None, auto_message=False):
    """
    Commit and push changes.

    Args:
        message: Commit message (optional if auto_message=True)
        auto_message: Generate commit message from git status

    Returns:
        bool: Success status
    """
    try:
        root = find_project_root()
        print(f"Git root: {root}")

        # Check status
        status = get_git_status()
        if not status:
            print("No changes to commit.")
            return True

        print(f"\nChanges to commit:\n{status}\n")

        # Get branch
        branch = get_git_branch()
        print(f"Current branch: {branch}")

        # Generate message if needed
        if auto_message and not message:
            lines = status.split('\n')
            modified = sum(1 for l in lines if l.startswith(' M'))
            added = sum(1 for l in lines if l.startswith('??'))
            deleted = sum(1 for l in lines if l.startswith(' D'))

            parts = []
            if modified:
                parts.append(f"{modified} modified")
            if added:
                parts.append(f"{added} added")
            if deleted:
                parts.append(f"{deleted} deleted")

            message = f"chore: {', '.join(parts)}\n\nCo-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>"

        if not message:
            print("ERROR: No commit message provided. Use --message or --auto")
            return False

        print(f"\nCommit message:\n{message}\n")

        # Stage all
        print("Staging changes...")
        git_add_all()

        # Commit
        print("Creating commit...")
        git_commit(message)

        # Push
        print("Pushing to remote...")
        git_push()

        print(f"\n[SUCCESS] Committed and pushed to {branch}")
        return True

    except subprocess.CalledProcessError as e:
        print(f"ERROR: Git command failed: {e}")
        return False
    except Exception as e:
        print(f"ERROR: {e}")
        return False


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(description='Kiwi Git - Commit and Push')
    parser.add_argument('-m', '--message', help='Commit message')
    parser.add_argument('--auto', action='store_true', help='Auto-generate commit message')
    args = parser.parse_args()

    success = commit_and_push(message=args.message, auto_message=args.auto)
    sys.exit(0 if success else 1)
