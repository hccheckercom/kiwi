"""CLI entry point for kiwi-compu command."""
import sys
from .git import commit_and_push

def main():
    """Run commit and push from CLI."""
    import argparse
    parser = argparse.ArgumentParser(description='Kiwi Commit and Push')
    parser.add_argument('-m', '--message', help='Commit message')
    parser.add_argument('--auto', action='store_true', help='Auto-generate commit message from git status')
    args = parser.parse_args()

    try:
        success = commit_and_push(message=args.message, auto_message=args.auto)
        sys.exit(0 if success else 1)
    except Exception as e:
        print(f"ERROR: {e}")
        sys.exit(1)

if __name__ == '__main__':
    main()
