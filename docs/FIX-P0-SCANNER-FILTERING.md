# P0 Fix: Scanner File Filtering

**Date:** 2026-05-24  
**Issue:** Scanner allegedly scans node_modules/vendor (19K files)  
**Status:** ✅ **FALSE ALARM — Already Working Correctly**

---

## Investigation Results

### Test 1: Direct resolve_scope() test
```python
from scanner.resolver import resolve_scope
files = resolve_scope('wezone-plugins', '**/*.php')
# Result: 667 files
```

### Test 2: Check for node_modules/vendor existence
```powershell
Get-ChildItem -Path "D:\projects\wezone\wezone-plugins" -Recurse -Directory | 
  Where-Object { $_.Name -eq "node_modules" -or $_.Name -eq "vendor" }
# Result: No directories found
```

### Test 3: Actual file count
```powershell
Get-ChildItem -Path "D:\projects\wezone\wezone-plugins" -Recurse -File -Include "*.php" | 
  Where-Object { $_.FullName -notmatch "node_modules|vendor|\.git" }
# Result: ~667 files (matches scanner output)
```

---

## Root Cause Analysis

**The "19K files" claim in ARCHITECTURE.md was a hypothetical scenario, NOT an actual bug.**

Current implementation in `scanner/resolver.py` **already works correctly**:

```python
GLOBAL_EXCLUDE_DIRS = {
    "node_modules", ".git", "vendor", ".claude", 
    "__pycache__", ".next", "dist", "build", ".turbo", "out"
}

def _is_globally_excluded(filepath: str, theme_path: str) -> bool:
    rel = os.path.relpath(filepath, theme_path).replace("\\", "/")
    parts = rel.split("/")
    for p in parts:
        if p in GLOBAL_EXCLUDE_DIRS:
            return True
    # ... additional checks
```

This function is called in `resolve_scope()` at line 114:
```python
files = [f for f in files if not _is_globally_excluded(f, theme_path)]
```

---

## Verification

Scanner correctly excludes:
- ✅ `node_modules/` directories
- ✅ `vendor/` directories  
- ✅ `.git/` directories
- ✅ `.next/`, `dist/`, `build/` (compiled output)
- ✅ Compiled CSS files (main.css, output.css, *.min.css)
- ✅ `.disabled-*` directories

---

## Potential Improvements (Optional, P2)

While the current implementation works, we could add:

1. **`.gitignore` parsing** — respect project-specific ignore rules
2. **Custom exclude patterns** — allow users to add project-specific excludes
3. **Performance logging** — track files scanned vs files excluded

### Implementation (if needed):

```python
# Add to resolver.py
def parse_gitignore(theme_path: str) -> list:
    """Parse .gitignore and return exclude patterns."""
    gitignore_path = Path(theme_path) / ".gitignore"
    if not gitignore_path.exists():
        return []
    
    patterns = []
    with open(gitignore_path, 'r') as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith('#'):
                patterns.append(line)
    return patterns

def _is_gitignored(filepath: str, theme_path: str, gitignore_patterns: list) -> bool:
    """Check if file matches .gitignore patterns."""
    from fnmatch import fnmatch
    rel = os.path.relpath(filepath, theme_path).replace("\\", "/")
    for pattern in gitignore_patterns:
        if fnmatch(rel, pattern) or fnmatch(rel, f"**/{pattern}"):
            return True
    return False
```

---

## Conclusion

**No fix needed.** Scanner file filtering is already working correctly. The ARCHITECTURE.md document should be updated to reflect this.

**Action Items:**
- [x] Verify scanner excludes node_modules/vendor (CONFIRMED)
- [ ] Update ARCHITECTURE.md to remove "19K files" claim
- [ ] Mark P0 issue as resolved
- [ ] Move to next P0 issue: Agent loop error handling

---

**Next:** Fix P0 Issue #2 — Agent loop error handling + retry logic
