# Kiwi Production Deployment Guide

Complete guide for integrating Kiwi into production workflows, CI/CD pipelines, and team processes.

## Table of Contents
1. [Quick Start](#quick-start)
2. [CI/CD Integration](#cicd-integration)
3. [Git Hooks Setup](#git-hooks-setup)
4. [Team Workflow](#team-workflow)
5. [Performance Tuning](#performance-tuning)
6. [Monitoring & Alerts](#monitoring--alerts)

---

## Quick Start

### Prerequisites
- Python 3.11+
- Git repository
- 562 Kiwi lessons indexed

### Installation
```bash
# Clone or ensure Kiwi is in .claude/kiwi/
cd /path/to/project/.claude/kiwi

# Verify installation
python -m scanner.cli --help
python -m agent.cli --help
```

### First Scan
```bash
# Scan WordPress theme
python -m scanner.cli --theme /path/to/theme --platform wp --severity CRITICAL

# Scan Next.js app
python -m scanner.cli --theme /path/to/app --platform nextjs --severity ALL

# JSON output for CI/CD
python -m scanner.cli --theme /path/to/theme --json > scan_result.json
```

---

## CI/CD Integration

### GitHub Actions

Create `.github/workflows/kiwi-scan.yml`:

```yaml
name: Kiwi Security Scan

on:
  pull_request:
    branches: [main, master, develop]
  push:
    branches: [main, master]

jobs:
  kiwi-scan:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      
      - name: Set up Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.11'
      
      - name: Run Kiwi Scanner
        run: |
          cd .claude/kiwi
          python -m scanner.cli \
            --theme ${{ github.workspace }} \
            --platform wp \
            --severity CRITICAL \
            --json > scan_result.json
      
      - name: Check for CRITICAL violations
        run: |
          CRITICAL_COUNT=$(python -c "
          import json
          with open('.claude/kiwi/scan_result.json') as f:
              data = json.load(f)
              print(len([v for v in data.get('violations', []) if v['severity'] == 'CRITICAL']))
          ")
          
          if [ "$CRITICAL_COUNT" -gt 0 ]; then
            echo "❌ Found $CRITICAL_COUNT CRITICAL violations"
            exit 1
          else
            echo "✅ No CRITICAL violations found"
          fi
      
      - name: Upload scan results
        if: always()
        uses: actions/upload-artifact@v3
        with:
          name: kiwi-scan-results
          path: .claude/kiwi/scan_result.json
```

### GitLab CI

Create `.gitlab-ci.yml`:

```yaml
kiwi-scan:
  stage: test
  image: python:3.11
  script:
    - cd .claude/kiwi
    - python -m scanner.cli --theme $CI_PROJECT_DIR --platform wp --severity CRITICAL --json > scan_result.json
    - |
      CRITICAL_COUNT=$(python -c "
      import json
      with open('scan_result.json') as f:
          data = json.load(f)
          print(len([v for v in data.get('violations', []) if v['severity'] == 'CRITICAL']))
      ")
      if [ "$CRITICAL_COUNT" -gt 0 ]; then
        echo "❌ Found $CRITICAL_COUNT CRITICAL violations"
        exit 1
      fi
  artifacts:
    paths:
      - .claude/kiwi/scan_result.json
    when: always
  only:
    - merge_requests
    - main
```

### Jenkins Pipeline

```groovy
pipeline {
    agent any
    
    stages {
        stage('Kiwi Scan') {
            steps {
                sh '''
                    cd .claude/kiwi
                    python3 -m scanner.cli \
                        --theme ${WORKSPACE} \
                        --platform wp \
                        --severity CRITICAL \
                        --json > scan_result.json
                '''
                
                script {
                    def scanResult = readJSON file: '.claude/kiwi/scan_result.json'
                    def criticalCount = scanResult.violations.count { it.severity == 'CRITICAL' }
                    
                    if (criticalCount > 0) {
                        error("Found ${criticalCount} CRITICAL violations")
                    }
                }
            }
        }
    }
    
    post {
        always {
            archiveArtifacts artifacts: '.claude/kiwi/scan_result.json', allowEmptyArchive: true
        }
    }
}
```

---

## Git Hooks Setup

### Pre-commit Hook (Scan Changed Files Only)

Create `.git/hooks/pre-commit`:

```bash
#!/bin/bash

# Get list of staged PHP/JS/TS files
STAGED_FILES=$(git diff --cached --name-only --diff-filter=ACM | grep -E '\.(php|js|ts|tsx)$')

if [ -z "$STAGED_FILES" ]; then
    echo "No PHP/JS/TS files to scan"
    exit 0
fi

echo "🔍 Running Kiwi scan on staged files..."

cd .claude/kiwi

# Scan each staged file
VIOLATIONS=0
for FILE in $STAGED_FILES; do
    RESULT=$(python -m scanner.cli --theme "../../$FILE" --severity CRITICAL --json 2>/dev/null)
    FILE_VIOLATIONS=$(echo "$RESULT" | python -c "import sys, json; print(len(json.load(sys.stdin).get('violations', [])))" 2>/dev/null || echo "0")
    VIOLATIONS=$((VIOLATIONS + FILE_VIOLATIONS))
done

if [ "$VIOLATIONS" -gt 0 ]; then
    echo "❌ Found $VIOLATIONS CRITICAL violations in staged files"
    echo "Run 'python .claude/kiwi/scanner/cli.py --theme <file>' to see details"
    exit 1
fi

echo "✅ No CRITICAL violations found"
exit 0
```

Make executable:
```bash
chmod +x .git/hooks/pre-commit
```

### Pre-push Hook (Full Scan)

Create `.git/hooks/pre-push`:

```bash
#!/bin/bash

echo "🔍 Running full Kiwi scan before push..."

cd .claude/kiwi
python -m scanner.cli --theme ../.. --platform wp --severity CRITICAL --json > /tmp/kiwi_scan.json

CRITICAL_COUNT=$(python -c "
import json
with open('/tmp/kiwi_scan.json') as f:
    data = json.load(f)
    print(len([v for v in data.get('violations', []) if v['severity'] == 'CRITICAL']))
")

if [ "$CRITICAL_COUNT" -gt 0 ]; then
    echo "❌ Found $CRITICAL_COUNT CRITICAL violations"
    echo "Fix violations before pushing or use --no-verify to skip"
    exit 1
fi

echo "✅ No CRITICAL violations found"
exit 0
```

---

## Team Workflow

### 1. Developer Workflow

```bash
# Before starting work
cd .claude/kiwi
python -m scanner.cli --theme /path/to/feature --severity ALL

# During development (quick check)
python -m scanner.cli --theme /path/to/file.php --severity CRITICAL

# Before commit
git add .
git commit -m "feat: add feature X"  # Pre-commit hook runs automatically

# Before push
git push  # Pre-push hook runs full scan
```

### 2. Code Review Workflow

**Reviewer checklist**:
1. Check CI/CD scan results in PR
2. Review violations in scan artifact
3. Verify fixes don't introduce new violations
4. Approve only if 0 CRITICAL violations

**PR template addition**:
```markdown
## Kiwi Scan Results
- [ ] 0 CRITICAL violations
- [ ] 0 HIGH violations (or justified)
- [ ] Scan artifact reviewed
```

### 3. Deployment Workflow

```bash
# Pre-deployment scan
cd .claude/kiwi
python -m scanner.cli --theme /path/to/deploy --severity CRITICAL --json > pre_deploy_scan.json

# Check results
CRITICAL_COUNT=$(python -c "
import json
with open('pre_deploy_scan.json') as f:
    data = json.load(f)
    print(len([v for v in data.get('violations', []) if v['severity'] == 'CRITICAL']))
")

if [ "$CRITICAL_COUNT" -eq 0 ]; then
    echo "✅ Safe to deploy"
    # Proceed with deployment
else
    echo "❌ BLOCK: $CRITICAL_COUNT CRITICAL violations"
    exit 1
fi
```

---

## Performance Tuning

### 1. Scan Speed Optimization

**Exclude unnecessary paths**:
```bash
# Exclude vendor, node_modules, build artifacts
python -m scanner.cli \
    --theme /path/to/project \
    --exclude "vendor/**,node_modules/**,build/**,dist/**"
```

**Parallel scanning** (for large codebases):
```bash
# Split by directory
find src -type d -maxdepth 1 | xargs -P 4 -I {} \
    python -m scanner.cli --theme {} --json > {}.json
```

### 2. Memory Optimization

For large codebases (>10k files):
```bash
# Scan in batches
find . -name "*.php" | split -l 1000 - batch_
for batch in batch_*; do
    python -m scanner.cli --theme $(cat $batch) --json >> results.json
done
```

### 3. Severity Filtering

```bash
# CI/CD: Only CRITICAL (fastest)
python -m scanner.cli --severity CRITICAL

# Pre-commit: CRITICAL + HIGH
python -m scanner.cli --severity HIGH

# Full audit: ALL (slowest)
python -m scanner.cli --severity ALL
```

---

## Monitoring & Alerts

### 1. Metrics Collection

Track over time:
- Total violations by severity
- Violations per 1000 LOC
- Fix rate (violations fixed / violations found)
- False positive rate

**Example metrics script**:
```python
import json
from datetime import datetime

def collect_metrics(scan_result_path):
    with open(scan_result_path) as f:
        data = json.load(f)
    
    violations = data.get('violations', [])
    
    metrics = {
        'timestamp': datetime.now().isoformat(),
        'total_violations': len(violations),
        'critical': len([v for v in violations if v['severity'] == 'CRITICAL']),
        'high': len([v for v in violations if v['severity'] == 'HIGH']),
        'files_scanned': data.get('files_scanned', 0),
        'lessons_triggered': len(set(v['lesson_id'] for v in violations)),
    }
    
    # Append to metrics log
    with open('kiwi_metrics.jsonl', 'a') as f:
        f.write(json.dumps(metrics) + '\n')
    
    return metrics
```

### 2. Slack Notifications

```bash
# Send scan results to Slack
CRITICAL_COUNT=$(python -c "import json; print(len([v for v in json.load(open('scan_result.json')).get('violations', []) if v['severity'] == 'CRITICAL']))")

if [ "$CRITICAL_COUNT" -gt 0 ]; then
    curl -X POST $SLACK_WEBHOOK_URL \
        -H 'Content-Type: application/json' \
        -d "{
            \"text\": \"❌ Kiwi scan found $CRITICAL_COUNT CRITICAL violations in PR #$PR_NUMBER\",
            \"attachments\": [{
                \"color\": \"danger\",
                \"fields\": [{
                    \"title\": \"PR\",
                    \"value\": \"<$PR_URL|#$PR_NUMBER>\",
                    \"short\": true
                }]
            }]
        }"
fi
```

### 3. Dashboard Integration

**Grafana dashboard** (example query):
```sql
SELECT
    DATE(timestamp) as date,
    AVG(critical) as avg_critical,
    AVG(high) as avg_high
FROM kiwi_metrics
WHERE timestamp > NOW() - INTERVAL 30 DAY
GROUP BY date
ORDER BY date
```

---

## Troubleshooting

### Common Issues

**1. Scanner not found**
```bash
# Verify Python path
cd .claude/kiwi
python -m scanner.cli --help

# If fails, check PYTHONPATH
export PYTHONPATH="${PYTHONPATH}:/path/to/.claude/kiwi"
```

**2. High false positive rate**
```bash
# Dismiss false positives
python -c "
from memory.db import dismiss_violation
dismiss_violation('LES-XXX', '/path/to/file.php', 'reason', scope='project')
"

# Check confidence scores
python -c "
from memory.db import get_confidence_scores
print(get_confidence_scores())
"
```

**3. Slow scans**
```bash
# Profile scan
time python -m scanner.cli --theme /path/to/project --severity CRITICAL

# Check lesson count
python -c "
import json
with open('_meta.json') as f:
    print(f'Total lessons: {json.load(f)[\"stats\"][\"total\"]}')
"
```

---

## Best Practices

1. **Start with CRITICAL only** — Don't overwhelm team with HIGH/SUGGEST initially
2. **Gradual rollout** — Enable pre-commit hooks after team is comfortable with CI/CD scans
3. **Track metrics** — Monitor violation trends to measure improvement
4. **Regular lesson updates** — Review and refine noisy lessons quarterly
5. **Team training** — Ensure team understands why violations matter
6. **Dismiss wisely** — Only dismiss true false positives, document reason
7. **Automate fixes** — Use agent auto-fix mode for safe, repetitive fixes

---

## Support

- **Documentation**: `.claude/kiwi/README.md`
- **Lessons**: `.claude/kiwi/lessons/`
- **Issues**: Track in project issue tracker
- **Updates**: `git pull` to get latest lessons

---

**Version**: 1.0.0 (2026-05-27)  
**Score**: 93/100 (Tier 4)  
**Lessons**: 562  
**Test Coverage**: 26 files