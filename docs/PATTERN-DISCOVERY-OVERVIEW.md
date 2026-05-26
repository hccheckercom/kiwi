# Pattern Discovery Overview — Kiwi v2.1

**Last updated:** 2026-05-24  
**Status:** Production-ready

## Introduction

Kiwi provides 3 complementary tools for discovering and learning bug patterns. Each tool serves a different use case and works with different input sources. This guide helps you choose the right tool for your needs.

---

## Tool Comparison

| Tool | Input | Algorithm | Use Case | Speed | Lessons |
|------|-------|-----------|----------|-------|---------|
| **kiwi_mine_patterns** | Scan history DB | Levenshtein clustering | Find recurring bugs across scans | Fast (0.07s/1k) | Auto-suggest |
| **kiwi_learn_from_folder** | Any folder | 15 built-in detectors | Bootstrap KB, audit external code | Very fast (70 files/s) | Auto-suggest |
| **kiwi_detect_anomalies** | Scan history DB | Fingerprint matching | Find novel patterns | Fast | Auto-suggest |

---

## Decision Tree: Which Tool Should I Use?

```
START: What do you want to do?
│
├─ Learn from code I haven't scanned yet
│  └─ Use: kiwi_learn_from_folder
│     Examples:
│     - Audit downloaded plugin before installing
│     - Learn from competitor's open-source code
│     - Bootstrap KB for new project
│     - Security assessment of legacy code
│
├─ Find patterns in code I've already scanned
│  │
│  ├─ Find recurring bugs (same issue, multiple places)
│  │  └─ Use: kiwi_mine_patterns
│  │     Examples:
│  │     - "I keep seeing SQL injection in different files"
│  │     - "Hardcoded colors appear in 15 themes"
│  │     - Monthly pattern review
│  │
│  └─ Find novel bugs (never seen before)
│     └─ Use: kiwi_detect_anomalies
│        Examples:
│        - "This violation doesn't match any existing lesson"
│        - "Find zero-day patterns"
│        - Anomaly detection after major refactor
│
└─ I don't know / want recommendations
   └─ Start with: kiwi_learn_from_folder (fastest, no prerequisites)
      Then: kiwi_mine_patterns (after you have scan history)
```

---

## Detailed Tool Guides

### 1. kiwi_mine_patterns

**Full guide:** [PATTERN-MINING-GUIDE.md](PATTERN-MINING-GUIDE.md)

**What it does:**
- Analyzes violations from past scans stored in database
- Clusters similar violations using Levenshtein distance
- Extracts common regex patterns
- Suggests lessons when pattern appears ≥N times

**Prerequisites:**
- Must have scan history (run `kiwi_scan` first)
- Violations stored in `memory/violations` table

**Quick start:**
```javascript
// Step 1: Scan projects to build history
kiwi_scan({path: "themes/theme1", severity: "ALL"})
kiwi_scan({path: "themes/theme2", severity: "ALL"})
kiwi_scan({path: "themes/theme3", severity: "ALL"})

// Step 2: Mine patterns
kiwi_mine_patterns({
  lookback_days: 30,
  min_occurrences: 5,
  similarity_threshold: 0.8
})

// Step 3: Review and approve
kiwi_review_suggestions({status: "pending"})
kiwi_approve_suggestion({suggestion_id: 1})
```

**Best for:**
- Finding bugs that appear across multiple projects
- Monthly/quarterly pattern reviews
- Learning from your own codebase over time

**Performance:**
- 1000 violations: 0.07s
- 10k violations: 3.8s
- Memory: ~30 bytes per violation

---

### 2. kiwi_learn_from_folder

**Full guide:** [LEARN-FROM-FOLDER-GUIDE.md](LEARN-FROM-FOLDER-GUIDE.md)

**What it does:**
- Scans any folder (doesn't need to be in your project)
- Detects 15 common bug patterns (10 PHP + 5 JS/TS)
- Works on raw code files directly
- No scan history required

**15 Built-in Detectors:**

**PHP (10):**
1. Hardcoded credentials (CRITICAL)
2. SQL injection (CRITICAL)
3. XSS risk (HIGH)
4. Missing nonce (HIGH)
5. File inclusion (CRITICAL)
6. Hardcoded URLs (HIGH)
7. Missing error handling (HIGH)
8. Deprecated functions (HIGH)
9. Inefficient loops (SUGGEST)
10. Missing sanitization (HIGH)

**JavaScript/TypeScript (5):**
11. Hardcoded API keys (CRITICAL)
12. eval() usage (CRITICAL)
13. innerHTML XSS (HIGH)
14. Missing error handling (HIGH)
15. console.log (SUGGEST)

**Quick start:**
```javascript
// Scan any folder
kiwi_learn_from_folder({
  path: "/path/to/folder",
  min_occurrences: 3,
  auto_approve: false,
  categories: ["security"]  // optional filter
})

// Review and approve
kiwi_review_suggestions({status: "pending"})
kiwi_approve_suggestion({suggestion_id: 1})
```

**Best for:**
- Auditing external code before integration
- Bootstrap knowledge base for new projects
- Security assessment of downloaded plugins
- Learning from legacy codebases

**Performance:**
- 500 files: 7.2s (~70 files/s)
- 5000 files: 72s (~70 files/s)
- Memory: ~50MB for 5000 files

---

### 3. kiwi_detect_anomalies

**Implementation:** [learning/anomaly.py](../learning/anomaly.py)

**What it does:**
- Compares recent violations against existing lesson fingerprints
- Uses Jaccard similarity to find novel patterns
- Suggests new lessons for violations that don't match any existing pattern

**Quick start:**
```javascript
kiwi_detect_anomalies({
  lookback_days: 7
})
```

**Best for:**
- Finding zero-day patterns
- Detecting new bug types after major refactors
- Continuous learning from production scans

**Performance:**
- Fast (similar to mine_patterns)
- Low memory footprint

---

## Workflow Examples

### Workflow 1: Bootstrap New Project

**Goal:** Start a new WordPress theme with learned patterns from existing themes.

```javascript
// Step 1: Learn from 3 reference themes
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

// Step 2: Review all suggestions
kiwi_review_suggestions({status: "pending"})

// Step 3: Approve high-confidence patterns
kiwi_approve_suggestion({suggestion_id: 1})
kiwi_approve_suggestion({suggestion_id: 3})
kiwi_approve_suggestion({suggestion_id: 5})

// Step 4: Scan your new theme with learned patterns
kiwi_scan({path: "themes/my-new-theme", severity: "ALL"})
```

**Result:** New theme scanned with 15+ custom lessons learned from reference themes.

---

### Workflow 2: Monthly Pattern Review

**Goal:** Discover recurring bugs across all projects scanned in the last month.

```javascript
// Step 1: Mine patterns from last 30 days
kiwi_mine_patterns({
  lookback_days: 30,
  min_occurrences: 5,
  similarity_threshold: 0.8
})

// Step 2: Check for anomalies
kiwi_detect_anomalies({
  lookback_days: 30
})

// Step 3: Review all suggestions
kiwi_review_suggestions({status: "pending"})

// Step 4: Approve patterns
// (Manually review each suggestion)
kiwi_approve_suggestion({suggestion_id: 1})
kiwi_approve_suggestion({suggestion_id: 2})

// Step 5: Reject false positives
kiwi_reject_suggestion({
  suggestion_id: 3,
  reason: "Too generic, would cause false positives"
})
```

**Result:** Knowledge base updated with patterns discovered in last month.

---

### Workflow 3: Audit External Code

**Goal:** Security assessment of downloaded plugin before installing.

```javascript
// Step 1: Learn security patterns
kiwi_learn_from_folder({
  path: "D:/downloads/suspicious-plugin",
  min_occurrences: 1,  // Low threshold for security
  categories: ["security"]
})

// Output shows:
// - 3 SQL injection patterns (12 occurrences)
// - 2 XSS risks (8 occurrences)
// - 1 hardcoded credential (1 occurrence)

// Decision: DO NOT install this plugin
```

**Result:** Security issues identified before installation.

---

## Integration Patterns

### Pattern A: Continuous Learning Loop

```
1. Scan projects daily (CI/CD)
   ↓
2. Mine patterns weekly (cron job)
   ↓
3. Review suggestions (manual)
   ↓
4. Approve high-confidence patterns
   ↓
5. Re-scan with new lessons
   ↓
6. Repeat
```

**Implementation:**
```yaml
# .github/workflows/pattern-learning.yml
name: Pattern Learning

on:
  schedule:
    - cron: '0 0 * * 0'  # Weekly on Sunday

jobs:
  mine:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - name: Mine patterns
        run: |
          cd .claude/kiwi
          python -c "
          from learning.miner import mine_patterns
          patterns = mine_patterns(min_occurrences=5, lookback_days=7)
          print(f'Found {len(patterns)} patterns')
          "
```

---

### Pattern B: Pre-commit Learning

```bash
#!/bin/bash
# .git/hooks/pre-commit

# Learn from staged files
STAGED_PHP=$(git diff --cached --name-only --diff-filter=ACM | grep '\.php$')

if [ -n "$STAGED_PHP" ]; then
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
    print(f'⚠ Found {len(result[\"suggestions\"])} security patterns')
    exit(1)
"
    
    rm -rf "$TEMP_DIR"
fi
```

---

## Performance Comparison

| Operation | Tool | Dataset | Duration | Throughput |
|-----------|------|---------|----------|------------|
| Mine 1000 violations | mine_patterns | Scan history | 0.07s | 14k violations/s |
| Scan 500 PHP files | learn_from_folder | Raw files | 7.2s | 70 files/s |
| Scan 500 JS files | learn_from_folder | Raw files | 7.2s | 70 files/s |
| Detect anomalies | detect_anomalies | Scan history | 0.5s | Fast |

**Key takeaways:**
- `learn_from_folder` is fastest for initial KB bootstrap
- `mine_patterns` is most efficient for large scan histories
- All tools scale linearly with input size

---

## Common Pitfalls

### Pitfall 1: Using mine_patterns without scan history

**Problem:**
```javascript
kiwi_mine_patterns({lookback_days: 30})
// → No patterns found
```

**Solution:**
```javascript
// First, build scan history
kiwi_scan({path: "project1", severity: "ALL"})
kiwi_scan({path: "project2", severity: "ALL"})

// Then mine patterns
kiwi_mine_patterns({lookback_days: 30})
```

---

### Pitfall 2: min_occurrences too high

**Problem:**
```javascript
kiwi_learn_from_folder({
  path: "/small-project",
  min_occurrences: 10  // Too high for small project
})
// → No patterns found
```

**Solution:**
```javascript
kiwi_learn_from_folder({
  path: "/small-project",
  min_occurrences: 2  // Lower threshold
})
```

---

### Pitfall 3: Auto-approving without review

**Problem:**
```javascript
kiwi_learn_from_folder({
  path: "/untrusted-code",
  auto_approve: true  // Dangerous!
})
// → Creates lessons with false positives
```

**Solution:**
```javascript
kiwi_learn_from_folder({
  path: "/untrusted-code",
  auto_approve: false  // Review first
})

// Manual review
kiwi_review_suggestions({status: "pending"})
kiwi_approve_suggestion({suggestion_id: 1})
```

---

## FAQ

### Q: Which tool should I use first?

**A:** Start with `kiwi_learn_from_folder` — it's fastest, requires no prerequisites, and gives immediate results. Once you have scan history, add `kiwi_mine_patterns` to your monthly workflow.

---

### Q: Can I use multiple tools together?

**A:** Yes! They're complementary:
1. Use `learn_from_folder` to bootstrap KB
2. Use `mine_patterns` monthly to find recurring bugs
3. Use `detect_anomalies` to catch novel patterns

---

### Q: How do I avoid false positives?

**A:**
- Increase `min_occurrences` threshold
- Use category filtering
- Always review suggestions before approving
- Reject false positives with `kiwi_reject_suggestion`

---

### Q: What's the difference between mine_patterns and learn_from_folder?

**A:**

| Aspect | mine_patterns | learn_from_folder |
|--------|---------------|-------------------|
| Input | Scan history DB | Raw code files |
| Algorithm | Clustering | Built-in detectors |
| Prerequisites | Must scan first | None |
| Flexibility | Learns any pattern | 15 fixed patterns |
| Speed | Very fast | Fast |

---

### Q: How often should I run pattern discovery?

**A:**
- `learn_from_folder`: Ad-hoc (when auditing external code)
- `mine_patterns`: Weekly or monthly
- `detect_anomalies`: After major refactors or releases

---

## Related Documentation

- [Pattern Mining Guide](PATTERN-MINING-GUIDE.md) — Deep dive into `kiwi_mine_patterns`
- [Learn from Folder Guide](LEARN-FROM-FOLDER-GUIDE.md) — Deep dive into `kiwi_learn_from_folder`
- [Quickstart Guide](QUICKSTART.md) — Getting started with Kiwi
- [Architecture](../ARCHITECTURE.md) — System design and components

---

## References

- Pattern mining: [learning/miner.py](../learning/miner.py)
- Learn from folder: [agent/learn.py](../agent/learn.py)
- Anomaly detection: [learning/anomaly.py](../learning/anomaly.py)
- MCP tools: [mcp_server.py](../mcp_server.py)
