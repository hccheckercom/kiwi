# Learn from Folder Guide — Kiwi v2.1

**Last updated:** 2026-05-24  
**Status:** Production-ready

## Overview

`kiwi_learn_from_folder` automatically scans any folder and detects 15 common bug patterns using built-in detectors. Unlike pattern mining (which learns from scan history), this tool analyzes raw code files directly and suggests lessons based on what it finds.

**When to use:**
- Bootstrap knowledge base for new projects
- Audit external themes/plugins before integration
- Learn from legacy codebases
- Quick security assessment of downloaded code
- Extract patterns from competitor code (if you have source access)

**Key benefits:**
- Zero scan history required — works on any folder
- 15 built-in detectors (10 PHP + 5 JS/TS)
- Multi-language support (PHP, JavaScript, TypeScript)
- Auto-approval workflow for batch lesson creation
- Progress reporting for large folders

---

## 15 Built-in Detectors

### PHP Detectors (10)

| # | Pattern | Severity | Category | Description |
|---|---------|----------|----------|-------------|
| 1 | Hardcoded Credentials | CRITICAL | security | `password = "hardcoded"` in source code |
| 2 | SQL Injection | CRITICAL | security | String concatenation in SQL queries |
| 3 | XSS Risk | HIGH | security | Unescaped output (`echo $var` without `esc_`) |
| 4 | Missing Nonce | HIGH | security | Form handlers without CSRF protection |
| 5 | File Inclusion | CRITICAL | security | Dynamic `include($var)` with user input |
| 6 | Hardcoded URLs | HIGH | portability | `https://example.com` instead of `home_url()` |
| 7 | Missing Error Handling | HIGH | reliability | External calls without error checks |
| 8 | Deprecated Functions | HIGH | compatibility | `mysql_query()`, `ereg()`, `create_function()` |
| 9 | Inefficient Loops | SUGGEST | performance | `count()` in loop condition (O(n²)) |
| 10 | Missing Sanitization | HIGH | security | `$_GET/$_POST` without `sanitize_*()` |

### JavaScript/TypeScript Detectors (5)

| # | Pattern | Severity | Category | Description |
|---|---------|----------|----------|-------------|
| 11 | Hardcoded API Keys | CRITICAL | security | API keys in client-side code |
| 12 | eval() Usage | CRITICAL | security | Code injection via `eval()` |
| 13 | innerHTML XSS | HIGH | security | Setting `innerHTML` without sanitization |
| 14 | Missing Error Handling | HIGH | reliability | `fetch()`/`axios()` without `.catch()` |
| 15 | console.log | SUGGEST | code-quality | Debug statements in production code |

---

## Production Workflow

### Step 1: Scan Folder

```javascript
kiwi_learn_from_folder({
  path: "/path/to/folder",
  min_occurrences: 3,
  auto_approve: false,
  categories: null  // or ["security", "performance"]
})
```

**Parameters:**
- `path` — Folder to scan (can be outside project)
- `min_occurrences` — Minimum times pattern must appear (default: 3)
- `auto_approve` — If true, auto-create lessons (default: false)
- `categories` — Filter by categories (optional)

**Output:**
```
Scanning 42 PHP files and 18 JS/TS files in /path/to/folder...

{
  "scanned_files": 60,
  "patterns_found": 8,
  "suggestions": [
    {
      "pattern_type": "hardcoded_credentials",
      "severity": "CRITICAL",
      "category": "security",
      "title": "Hardcoded Credentials in Source Code",
      "pattern": "(password|secret|api_key|token)\\s*=\\s*[\"'][^\"']+[\"']",
      "why": "Hardcoded credentials in source code can be exposed via version control",
      "bad_code": "define(\"API_KEY\", \"sk_live_abc123\");",
      "good_code": "define(\"API_KEY\", getenv(\"API_KEY\"));",
      "occurrences": 5,
      "files": ["config.php", "settings.php", ...],
      "examples": [
        {"file": "config.php", "line": 12, "code": "define('SECRET', 'hardcoded');"},
        ...
      ]
    },
    ...
  ]
}
```

### Step 2: Review Suggestions

Manually review each suggestion:
- Check if pattern is valid (not a false positive)
- Verify severity is appropriate
- Ensure examples are representative
- Decide whether to create lesson

### Step 3: Approve or Reject

**Option A: Manual approval (recommended)**
```javascript
// Review first
kiwi_review_suggestions({status: "pending"})

// Approve specific suggestion
kiwi_approve_suggestion({
  suggestion_id: 1,
  severity: "CRITICAL",  // optional override
  category: "security"   // optional override
})
```

**Option B: Auto-approve (use with caution)**
```javascript
kiwi_learn_from_folder({
  path: "/path/to/folder",
  min_occurrences: 5,  // Higher threshold for auto-approve
  auto_approve: true,
  categories: ["security"]  // Focus on security only
})
```

**Result:**
- Creates lesson files in `.claude/kiwi/lessons/{category}/`
- Updates `_meta.json` with new lesson IDs
- Rebuilds `README.md` index
- Lessons immediately active in next scan

---

## Use Cases

### Use Case 1: Bootstrap New Project

**Scenario:** Starting a new WordPress theme, want to learn common patterns from existing themes.

```javascript
// Scan 3 similar themes
kiwi_learn_from_folder({
  path: "D:/reference-themes/theme1",
  min_occurrences: 2,
  categories: ["security", "portability"]
})

kiwi_learn_from_folder({
  path: "D:/reference-themes/theme2",
  min_occurrences: 2,
  categories: ["security", "portability"]
})

kiwi_learn_from_folder({
  path: "D:/reference-themes/theme3",
  min_occurrences: 2,
  categories: ["security", "portability"]
})

// Review all suggestions
kiwi_review_suggestions({status: "pending"})

// Approve high-confidence patterns
kiwi_approve_suggestion({suggestion_id: 1})
kiwi_approve_suggestion({suggestion_id: 3})
kiwi_approve_suggestion({suggestion_id: 5})

// Now scan your new theme with learned patterns
kiwi_scan({path: "themes/my-new-theme", severity: "ALL"})
```

### Use Case 2: Audit External Plugin

**Scenario:** Downloaded a plugin from WordPress.org, want to check for security issues before installing.

```javascript
// Scan downloaded plugin
kiwi_learn_from_folder({
  path: "D:/downloads/suspicious-plugin",
  min_occurrences: 1,  // Low threshold for security audit
  categories: ["security"]
})

// Output shows:
// - 3 SQL injection patterns (12 occurrences)
// - 2 XSS risks (8 occurrences)
// - 1 hardcoded credential (1 occurrence)

// Decision: DO NOT install this plugin
```

### Use Case 3: Learn from Legacy Codebase

**Scenario:** Inheriting a 5-year-old project, want to understand common issues.

```javascript
// Scan entire legacy project
kiwi_learn_from_folder({
  path: "D:/legacy-project",
  min_occurrences: 10,  // High threshold (only widespread issues)
  auto_approve: false
})

// Output shows:
// - 47 deprecated function calls
// - 23 missing error handling
// - 15 inefficient loops

// Create lessons for top 3 issues
kiwi_approve_suggestion({suggestion_id: 1})  // Deprecated functions
kiwi_approve_suggestion({suggestion_id: 2})  // Missing error handling
kiwi_approve_suggestion({suggestion_id: 3})  // Inefficient loops

// Now scan to find all occurrences
kiwi_scan({path: "D:/legacy-project", severity: "HIGH"})
// → 85 violations found, prioritize fixes
```

### Use Case 4: Monthly Security Audit

**Scenario:** Regular security review of all client projects.

```bash
# Bash script for monthly audit
for project in /var/www/clients/*; do
  echo "Auditing $project..."
  
  # Learn security patterns
  python -c "
from agent.learn import learn_from_folder
result = learn_from_folder(
    path='$project',
    min_occurrences=1,
    categories=['security']
)
print(f'Found {len(result[\"suggestions\"])} security issues')
for sug in result['suggestions']:
    print(f'  [{sug[\"severity\"]}] {sug[\"title\"]}: {sug[\"occurrences\"]} occurrences')
"
done
```

---

## Multi-Language Support

### PHP Files (*.php)

**Detectors:** 1-10 (see table above)

**Scope:** `**/*.php`

**Example:**
```php
// Detected: hardcoded_credentials
define('API_KEY', 'sk_live_abc123');

// Detected: sql_injection
$wpdb->query("SELECT * FROM users WHERE id = " . $_GET['id']);

// Detected: xss_risk
echo $user_input;

// Detected: missing_nonce
if (isset($_POST['action'])) { process(); }
```

### JavaScript/TypeScript Files (*.js, *.ts, *.jsx, *.tsx)

**Detectors:** 11-15 (see table above)

**Scope:** `**/*.{js,ts,jsx,tsx}`

**Example:**
```javascript
// Detected: js_hardcoded_api_key
const apiKey = "sk_live_abc123def456ghi789";

// Detected: js_eval_usage
eval(userInput);

// Detected: js_innerhtml_xss
element.innerHTML = userInput;

// Detected: js_missing_error_handling
fetch('/api/data').then(r => r.json());

// Detected: js_console_log
console.log("Debug:", data);
```

---

## Progress Reporting

For large folders (>50 files), progress is reported every 10 files:

```javascript
kiwi_learn_from_folder({
  path: "/large/project",
  min_occurrences: 3
})

// Output:
// Scanning 500 PHP files and 200 JS/TS files in /large/project...
// [10/700] Scanned: src/auth.php
// [20/700] Scanned: src/api.php
// [30/700] Scanned: src/utils.php
// ...
```

**Implementation:**
```python
def progress_callback(files_scanned, total_files, current_file):
    print(f"[{files_scanned}/{total_files}] Scanned: {current_file}")

learn_from_folder(
    path="/large/project",
    progress_callback=progress_callback
)
```

---

## Tuning Guide

### min_occurrences Selection

| Use Case | Recommended | Rationale |
|----------|-------------|-----------|
| Security audit | 1 | Catch every security issue |
| Bootstrap KB | 2-3 | Balance coverage vs noise |
| Legacy analysis | 5-10 | Focus on widespread issues |
| Auto-approve | 10+ | High confidence only |

### Category Filtering

**Focus on specific categories:**
```javascript
// Security-only audit
kiwi_learn_from_folder({
  path: "/project",
  categories: ["security"]
})

// Performance optimization
kiwi_learn_from_folder({
  path: "/project",
  categories: ["performance"]
})

// Code quality review
kiwi_learn_from_folder({
  path: "/project",
  categories: ["code-quality", "compatibility"]
})
```

**Available categories:**
- `security` — SQL injection, XSS, CSRF, etc.
- `performance` — Inefficient loops, N+1 queries
- `reliability` — Missing error handling
- `portability` — Hardcoded URLs, paths
- `compatibility` — Deprecated functions
- `code-quality` — Console.log, debug statements

---

## Integration Examples

### Pre-commit Hook

```bash
#!/bin/bash
# .git/hooks/pre-commit

# Learn from staged PHP files
STAGED_PHP=$(git diff --cached --name-only --diff-filter=ACM | grep '\.php$')

if [ -n "$STAGED_PHP" ]; then
    echo "Learning from staged PHP files..."
    
    # Create temp directory with staged files
    TEMP_DIR=$(mktemp -d)
    for file in $STAGED_PHP; do
        mkdir -p "$TEMP_DIR/$(dirname $file)"
        git show ":$file" > "$TEMP_DIR/$file"
    done
    
    # Learn patterns
    cd .claude/kiwi
    python -c "
from agent.learn import learn_from_folder
result = learn_from_folder('$TEMP_DIR', min_occurrences=1, categories=['security'])
if result['suggestions']:
    print(f'⚠ Found {len(result[\"suggestions\"])} security patterns in staged files')
    for sug in result['suggestions']:
        print(f'  - {sug[\"title\"]}: {sug[\"occurrences\"]} occurrences')
    exit(1)
"
    
    # Cleanup
    rm -rf "$TEMP_DIR"
fi
```

### CI/CD Pipeline

```yaml
# .github/workflows/security-audit.yml
name: Security Audit

on:
  pull_request:
    paths:
      - '**.php'
      - '**.js'
      - '**.ts'

jobs:
  audit:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      
      - name: Setup Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.11'
      
      - name: Learn security patterns
        run: |
          cd .claude/kiwi
          python -c "
          from agent.learn import learn_from_folder
          result = learn_from_folder(
              path='../../',
              min_occurrences=1,
              categories=['security']
          )
          
          if result['suggestions']:
              print(f'## Security Issues Found')
              print(f'')
              for sug in result['suggestions']:
                  print(f'### [{sug[\"severity\"]}] {sug[\"title\"]}')
                  print(f'Occurrences: {sug[\"occurrences\"]}')
                  print(f'')
                  for ex in sug['examples'][:3]:
                      print(f'- {ex[\"file\"]}:{ex[\"line\"]}')
                  print(f'')
              exit(1)
          else:
              print('✓ No security issues detected')
          "
      
      - name: Comment on PR
        if: failure()
        uses: actions/github-script@v6
        with:
          script: |
            github.rest.issues.createComment({
              issue_number: context.issue.number,
              owner: context.repo.owner,
              repo: context.repo.repo,
              body: '⚠ Security patterns detected. Review the workflow logs.'
            })
```

---

## Performance Benchmarks

### Test Environment
- CPU: Intel i7-10700K
- RAM: 32GB
- Storage: NVMe SSD
- Python: 3.11

### Results

| Files | PHP | JS/TS | Patterns | Duration | Throughput |
|-------|-----|-------|----------|----------|------------|
| 50 | 50 | 0 | 12 | 0.8s | 62 files/s |
| 100 | 70 | 30 | 18 | 1.5s | 67 files/s |
| 500 | 350 | 150 | 45 | 7.2s | 69 files/s |
| 1000 | 700 | 300 | 87 | 14.5s | 69 files/s |
| 5000 | 3500 | 1500 | 210 | 72s | 69 files/s |

**Observations:**
- Linear time complexity: O(n) for file scanning
- Consistent throughput: ~70 files/second
- Memory usage: ~50MB for 5000 files
- Multi-language overhead: <5% (JS/TS detection is fast)

---

## Troubleshooting

### Issue: No patterns found

**Causes:**
- min_occurrences too high
- Category filter too restrictive
- Code is actually clean (rare!)

**Solutions:**
1. Lower min_occurrences:
   ```javascript
   kiwi_learn_from_folder({path: "/project", min_occurrences: 1})
   ```

2. Remove category filter:
   ```javascript
   kiwi_learn_from_folder({path: "/project", categories: null})
   ```

3. Check file count:
   ```bash
   find /project -name "*.php" | wc -l
   find /project -name "*.js" -o -name "*.ts" | wc -l
   ```

### Issue: Too many false positives

**Causes:**
- Detectors too aggressive
- Legacy code with intentional patterns
- Test files included in scan

**Solutions:**
1. Increase min_occurrences:
   ```javascript
   kiwi_learn_from_folder({path: "/project", min_occurrences: 5})
   ```

2. Exclude test files:
   ```bash
   # Scan only src/ directory
   kiwi_learn_from_folder({path: "/project/src"})
   ```

3. Review and reject false positives:
   ```javascript
   kiwi_reject_suggestion({
     suggestion_id: 3,
     reason: "Intentional for backward compatibility"
   })
   ```

### Issue: Scan too slow

**Causes:**
- Too many files (>10k)
- Network-mounted directories
- Antivirus scanning files

**Solutions:**
1. Scan subdirectories separately:
   ```javascript
   kiwi_learn_from_folder({path: "/project/src"})
   kiwi_learn_from_folder({path: "/project/lib"})
   ```

2. Use local copy (not network drive):
   ```bash
   rsync -av /network/project /local/project
   kiwi_learn_from_folder({path: "/local/project"})
   ```

3. Exclude large directories:
   ```bash
   # Scan only relevant directories
   kiwi_learn_from_folder({path: "/project/src"})
   # Skip node_modules, vendor, etc.
   ```

---

## Advanced Usage

### Custom Detector Integration

Want to add your own detector? Extend `_extract_code_patterns()` or `_extract_js_patterns()`:

```python
# In agent/learn.py

def _extract_code_patterns(file_path: str) -> List[Tuple[str, int, str]]:
    patterns = []
    # ... existing detectors ...
    
    # Custom detector: Hardcoded IP addresses
    if re.search(r'\b\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}\b', stripped):
        patterns.append(('hardcoded_ip', i, stripped))
    
    return patterns

# Add metadata in _generate_lesson_suggestion()
pattern_meta = {
    # ... existing patterns ...
    'hardcoded_ip': {
        'category': 'portability',
        'severity': 'HIGH',
        'title': 'Hardcoded IP Address',
        'pattern': r'\b\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}\b',
        'why': 'Hardcoded IPs break when infrastructure changes',
        'bad': '$server = "192.168.1.100";',
        'good': '$server = getenv("DB_HOST");'
    }
}
```

### Batch Processing

Process multiple projects in parallel:

```python
from concurrent.futures import ThreadPoolExecutor
from agent.learn import learn_from_folder

projects = [
    "/var/www/client1",
    "/var/www/client2",
    "/var/www/client3",
]

def audit_project(path):
    result = learn_from_folder(path, min_occurrences=2, categories=['security'])
    return (path, result)

with ThreadPoolExecutor(max_workers=4) as executor:
    results = list(executor.map(audit_project, projects))

for path, result in results:
    print(f"\n{path}: {len(result['suggestions'])} issues")
    for sug in result['suggestions']:
        print(f"  - {sug['title']}: {sug['occurrences']} occurrences")
```

---

## Related Tools

- [kiwi_mine_patterns](PATTERN-MINING-GUIDE.md) — Learn from scan history (requires prior scans)
- [kiwi_detect_anomalies](../learning/anomaly.py) — Find novel patterns not in lessons
- [kiwi_scan](../scanner/cli.py) — Scan with existing lessons

---

## References

- Implementation: [agent/learn.py](../agent/learn.py)
- Tests: [tests/test_learning_learn.py](../tests/test_learning_learn.py)
- MCP tool: [mcp_server.py](../mcp_server.py) (line 2049-2061)
- Detector patterns: [agent/learn.py](../agent/learn.py) (line 29-79 PHP, line 83-130 JS/TS)
