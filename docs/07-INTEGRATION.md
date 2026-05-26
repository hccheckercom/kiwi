# Integration — Claude Code, Skills, Hooks, CI

## MCP Registration

### `.mcp.json` (project root)

```json
{
  "mcpServers": {
    "wezone-rag": {
      "command": "python",
      "args": ["d:\\projects\\wezone\\rag\\rag_server.py"]
    },
    "kiwi": {
      "command": "python",
      "args": ["d:\\projects\\wezone\\.claude\\kiwi\\mcp_server.py"]
    }
  }
}
```

Claude Code tự phát hiện và load MCP servers khi khởi động. Sau khi register, user thấy tools ngay trong conversation.

## Backward Compatibility

### Cái gì KHÔNG thay đổi:

| Component | Status | Lý do |
|-----------|--------|-------|
| `scanner/cli.py` | Giữ nguyên | MCP server import từ CLI, không sửa CLI |
| `scanner/checkers/*` | Giữ nguyên | Không đổi logic check |
| `scanner/loader.py` | Giữ nguyên | MCP server dùng load_patterns() y nguyên |
| `scanner/resolver.py` | Giữ nguyên | Không đổi scope resolution |
| `scanner/reporters/*` | Giữ nguyên | MCP server format riêng, reporters cho CLI |
| `hooks/post_edit.py` | Giữ nguyên | Hook vẫn gọi CLI trực tiếp |
| `tools/add.py` | Giữ nguyên | MCP server import logic, không sửa tool |
| `tools/stats.py` | Giữ nguyên | MCP server import logic |
| `tools/rebuild_index.py` | Giữ nguyên | Gọi trực tiếp khi cần |
| `_meta.json` | Giữ nguyên format | MCP server đọc, kiwi_add cập nhật qua add.py |
| `lessons/**/*.md` | Thêm `fix` field | Backward compatible — scanner bỏ qua field không biết |

### Cái gì THÊM MỚI:

| Component | Phase | Mục đích |
|-----------|-------|----------|
| `mcp_server.py` | 1 | MCP server entry point |
| `scanner/fixer.py` | 2 | Auto-fix engine |
| `agent/` | 3 | Agent loop + tools + prompts |
| `memory/` | 4 | SQLite learning system |
| `kiwi.db` | 4 | SQLite database file |
| `docs/` | - | Tài liệu (this directory) |

## Skills Evolution

### Hiện tại: Skills gọi CLI subprocess
```markdown
<!-- .claude/commands/kiwi-scan.md -->
Scan theme: python -m scanner.cli --theme $PATH --severity CRITICAL
```

### Tương lai: Skills có thể gọi MCP tools trực tiếp
```markdown
<!-- .claude/commands/kiwi-scan.md -->
Use kiwi_scan tool with path=$PATH, severity=CRITICAL
```

**Migration không cần ngay** — skills gọi CLI vẫn hoạt động. Khi MCP ổn định, từ từ chuyển skills sang gọi MCP tools.

### Skill mới (Phase 3):
```markdown
<!-- .claude/commands/kiwi-agent.md -->
# /kiwi-agent — Run Kiwi Agent Loop

Chạy Kiwi Agent tự động scan và fix bugs.

## Usage
/kiwi-agent [path] [--mode review|interactive|auto] [--severity CRITICAL|HIGH|ALL]

## Examples
/kiwi-agent wezone-plugins --mode review
/kiwi-agent themes/trunganh-v2 --mode auto --severity CRITICAL
```

## Hooks Integration

### Post-edit hook (hiện tại — giữ nguyên)

```json
// .claude/settings.json
{
  "hooks": {
    "PostToolUse": [
      {
        "matcher": "Edit|Write",
        "hooks": [
          {
            "type": "command",
            "command": "python d:/projects/wezone/.claude/kiwi/hooks/post_edit.py"
          }
        ]
      }
    ]
  }
}
```

Hook chạy scanner trực tiếp (không qua MCP) — giữ nguyên vì:
- Hook cần response nhanh (<2s)
- MCP server startup có latency
- Hook chỉ scan CRITICAL — nhẹ

### Phase 4: Enhanced post-edit hook

```python
# hooks/post_edit.py — thêm memory integration
def post_edit_scan(file_path):
    report = scan_theme(theme_path, severity_filter="CRITICAL")
    
    # Phase 4: filter dismissed false positives
    if DB_AVAILABLE:
        from memory.db import is_dismissed
        report.violations = [
            v for v in report.violations 
            if not is_dismissed(v.lesson_id, v.file)
        ]
    
    return report
```

## CI/CD Integration (tương lai)

### GitHub Actions

```yaml
# .github/workflows/kiwi-scan.yml
name: Kiwi Scan
on: [pull_request]

jobs:
  scan:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: '3.11'
      - run: pip install pyyaml
      - name: Kiwi Scan
        run: |
          cd .claude/kiwi
          python -m scanner.cli --theme . --severity CRITICAL --json > report.json
          CRITICAL=$(python -c "import json; print(json.load(open('report.json'))['summary']['critical'])")
          if [ "$CRITICAL" -gt 0 ]; then
            echo "::error::$CRITICAL CRITICAL violations found"
            exit 1
          fi
```

### Pre-commit hook

```bash
#!/bin/bash
# .git/hooks/pre-commit
cd .claude/kiwi
RESULT=$(python -m scanner.cli --theme ../.. --diff-only --severity CRITICAL --json 2>/dev/null)
CRITICAL=$(echo $RESULT | python -c "import sys,json; print(json.load(sys.stdin).get('summary',{}).get('critical',0))")
if [ "$CRITICAL" -gt 0 ]; then
    echo "❌ Kiwi: $CRITICAL CRITICAL violations in staged files"
    echo "$RESULT" | python -c "import sys,json; [print(f'  {v[\"file\"]}:{v[\"line\"]} {v[\"description\"]}') for v in json.load(sys.stdin).get('violations',[])]"
    exit 1
fi
```

## Environment Requirements

### Python packages

```
# Required (already installed)
pyyaml                    # Kiwi scanner

# Phase 3 (new)
anthropic                 # Claude API for agent loop

# Phase 4 (built-in)
sqlite3                   # Python standard library — no install needed
```

### API Configuration

Agent (Phase 3) cần Anthropic API key. Options:

1. **Reuse orbit-provider** (from settings.local.json):
   ```python
   client = Anthropic(
       api_key=os.environ.get("ANTHROPIC_API_KEY", "<from-settings>"),
       base_url="https://api.orbit-provider.com/api/provider/agy"
   )
   ```

2. **Environment variable:**
   ```powershell
   $env:ANTHROPIC_API_KEY = "sk-ant-..."
   ```

3. **Config file:**
   ```python
   # .claude/kiwi/agent/config.json
   {"api_key": "...", "model": "claude-sonnet-4-6"}
   ```

Recommendation: Option 1 (reuse existing config) — no new secrets needed.

## Tool Summary — All Phases

### Phase 1: 7 MCP tools
| Tool | Type | Description |
|------|------|-------------|
| `kiwi_scan` | Read | Scan project for violations |
| `kiwi_query` | Read | Search knowledge base |
| `kiwi_lesson` | Read | Get full lesson content |
| `kiwi_add` | Write | Add new lesson |
| `kiwi_stats` | Read | Statistics breakdown |
| `kiwi_fix` | Read | Fix suggestion (Good section) |
| `kiwi_template` | Read | Query template library |

### Phase 2: Updated tool
| Tool | Type | Description |
|------|------|-------------|
| `kiwi_fix` | Read/Write | + apply option for auto-fix |

### Phase 3: 1 new MCP tool
| Tool | Type | Description |
|------|------|-------------|
| `kiwi_agent` | Execute | Run agent loop (review/interactive/auto) |

### Phase 4: 3 new MCP tools
| Tool | Type | Description |
|------|------|-------------|
| `kiwi_dismiss` | Write | Mark violation as false positive |
| `kiwi_trends` | Read | Violation trend over time |
| `kiwi_confidence` | Read | Lesson confidence scores |

**Total: 11 MCP tools when all phases complete.**