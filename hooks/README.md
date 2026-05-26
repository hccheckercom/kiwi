# Kiwi Git Hooks

Git hooks for automated code quality checks.

## Pre-commit Hook

Scans staged files for CRITICAL violations before allowing commit.

### Installation

**Linux/Mac:**
```bash
cd /path/to/your/repo
ln -s ../../.claude/kiwi/hooks/pre-commit .git/hooks/pre-commit
chmod +x .git/hooks/pre-commit
```

**Windows (PowerShell):**
```powershell
cd D:\projects\wezone
Copy-Item .claude\kiwi\hooks\pre-commit .git\hooks\pre-commit
```

### Usage

Once installed, the hook runs automatically on `git commit`:

```bash
git add file.php
git commit -m "Fix bug"

# Output:
# [Kiwi] Scanning 1 staged files for CRITICAL violations...
# [Kiwi] ✓ No CRITICAL violations found
```

If violations found:
```bash
# [Kiwi] ✗ Found 2 CRITICAL violations:
#
#   src/header.php:42 — LES-001: Missing nonce verification
#   src/footer.php:18 — LES-015: SQL injection vulnerability
#
# Fix violations before committing, or use --no-verify to skip this check.
```

### Bypass Hook (Emergency Only)

```bash
# Skip pre-commit hook (NOT recommended)
git commit --no-verify -m "Emergency fix"
```

### Configuration

Edit [pre-commit](pre-commit) to customize:
- Severity filter (default: CRITICAL)
- File extensions scanned
- Max violations shown

### Uninstall

```bash
rm .git/hooks/pre-commit
```

---

## How It Works

1. **Get staged files**: `git diff --cached --name-only`
2. **Filter scannable**: Only `.php`, `.js`, `.css`, `.ts`, `.tsx`, `.jsx`
3. **Scan each file**: Run Kiwi scanner with `severity=CRITICAL`
4. **Block if violations**: Exit code 1 prevents commit
5. **Allow if clean**: Exit code 0 allows commit

---

## Performance

- **Typical scan**: 1-5 files, < 1 second
- **Large commit**: 20+ files, 2-5 seconds
- **Only scans staged files** (not entire project)

---

## Troubleshooting

### Hook not running

1. **Check hook exists:**
   ```bash
   ls -la .git/hooks/pre-commit
   ```

2. **Check executable:**
   ```bash
   chmod +x .git/hooks/pre-commit
   ```

3. **Check Python path:**
   ```bash
   which python3
   # Should be in PATH
   ```

### Hook fails with import error

1. **Check Kiwi path:**
   ```python
   # In pre-commit hook
   KIWI_DIR = Path(__file__).parent.parent
   print(f"Kiwi dir: {KIWI_DIR}")
   ```

2. **Check scanner module:**
   ```bash
   cd .claude/kiwi
   python -c "from scanner.cli import scan_theme; print('OK')"
   ```

### Hook too slow

1. **Reduce file count** (commit smaller changes)
2. **Skip hook for large commits:**
   ```bash
   git commit --no-verify
   ```

---

## Best Practices

1. **Run scan before staging:**
   ```bash
   # Scan before commit
   cd .claude/kiwi
   python -m scanner.cli --theme /path/to/files --severity CRITICAL
   ```

2. **Fix violations incrementally:**
   - Don't accumulate violations
   - Fix as you code

3. **Use --no-verify sparingly:**
   - Only for emergencies
   - Create follow-up issue to fix violations

4. **Combine with CI/CD:**
   - Pre-commit hook = fast feedback
   - CI scan = comprehensive check

---

## Related

- [Kiwi Scanner](../scanner/README.md)
- [Kiwi Lessons](../lessons/)
- [Deployment Hooks](../deploy/)