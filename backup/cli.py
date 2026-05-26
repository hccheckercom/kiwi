"""CLI entry point for kiwi-backup command."""
import sys
from .s3 import backup

def main():
    """Run backup from CLI."""
    try:
        success = backup()
        sys.exit(0 if success else 1)
    except Exception as e:
        print(f"ERROR: {e}")
        sys.exit(1)

if __name__ == '__main__':
    main()