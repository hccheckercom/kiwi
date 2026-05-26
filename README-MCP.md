# Kiwi MCP — Claude Code Integration Guide

Kiwi tích hợp với Claude Code qua MCP (Model Context Protocol), cung cấp 19 tools để Claude có thể gọi trực tiếp.

## MCP Tools Available

Kiwi expose 19 MCP tools qua JSON-RPC stdio protocol:

### Core Tools

1. **`kiwi_context`** — Inject rules trước khi code (BẮT BUỘC)
2. **`kiwi_check`** — Quick file check sau Write/Edit
3. **`kiwi_scan`** — Scan project for violations
4. **`kiwi_fix`** — Auto-fix hoặc preview fix
5. **`kiwi_agent`** — Autonomous agent loop

### Knowledge Base Tools

6. **`kiwi_query`** — Search lessons by keyword
7. **`kiwi_lesson`** — Read full lesson content
8. **`kiwi_stats`** — Knowledge base statistics
9. **`kiwi_template`** — Query template library

### Management Tools

10. **`kiwi_add`** — Add new lesson
11. **`kiwi_dismiss`** — Mark false positive
12. **`kiwi_reenable`** — Re-enable disabled lesson
13. **`kiwi_confidence`** — View confidence scores
14. **`kiwi_trends`** — Violation trends over time

### Deployment Tools

15. **`kiwi_deploy`** — Token-optimized deployment
16. **`kiwi_deploy_history`** — Deployment history
17. **`kiwi_impact`** — Impact analysis for regression defense

### Learning Tools

18. **`kiwi_learn_from_folder`** — Auto-detect patterns from folder
19. **`kiwi_scan_learn`** — Scan file + suggest lessons

## Hooks Integration

Kiwi tích hợp với Claude Code qua hooks trong `.claude/settings.json`:

### PostToolUse Hooks

**1. Post-edit guardrail** — Auto-scan CRITICAL sau Write/Edit

```json
{
  "hooks": {
    "PostToolUse": [
      {
        "matcher": "Edit|Write",
        "hooks": [
          {
            "type": "command",
            "command": "python",
            "args": ["d:/projects/wezone/.claude/kiwi/hooks/post_edit.py"],
            "timeout": 30
          }
        ]
      }
    ]
  }
}
```

**Behavior:**
- Chạy sau mỗi Write/Edit trên `.php`, `.css`, `.js`, `.jsx`, `.tsx`, `.ts`
- Scan CRITICAL violations
- Nếu phát hiện → BLOCK turn, buộc phải fix

**2. Track kiwi_context calls**

```json
{
  "matcher": "mcp__kiwi__kiwi_context",
  "hooks": [
    {
      "type": "command",
      "command": "python",
      "args": ["d:/projects/wezone/.claude/kiwi/hooks/track_kiwi_context.py"],
      "timeout": 3000
    }
  ]
}
```

### PreToolUse Hooks

**Enforce kiwi_context before code**

```json
{
  "hooks": {
    "PreToolUse": [
      {
        "matcher": "Edit|Write",
        "hooks": [
          {
            "type": "command",
            "command": "python",
            "args": ["d:/projects/wezone/.claude/kiwi/hooks/pre_edit.py", "${file_path}", "${tool_name}"],
            "timeout": 5000,
            "description": "Block Edit/Write on code files if kiwi_context not called"
          }
        ]
      }
    ]
  }
}
```

**Behavior:**
- Block Write/Edit nếu chưa gọi `kiwi_context` trong session
- Chỉ áp dụng cho code files (`.php`, `.css`, `.js`, etc.)
- Không áp dụng cho infrastructure code (`.claude/kiwi/`, `rag/`, etc.)

## Smart Detection (Auto kiwi_context)

Claude tự động phát hiện task code và gọi `kiwi_context` TRƯỚC khi Write/Edit:

**Trigger keywords:**
- Verbs: "tạo", "sửa", "fix", "thêm", "update", "refactor", "implement"
- + File extensions: `.php`, `.css`, `.js`, `.ts`, `.tsx`, `.jsx`
- + Code terms: "class", "function", "component", "API", "bug", "feature"

**Exclusions (KHÔNG gọi kiwi_context):**
- Infrastructure code: `.claude/kiwi/`, `.claude/kiwipw/`, `rag/`
- Internal tools: Kiwi scanner, agent, MCP server, hooks
- Research/debug: "research bug", "debug", "investigate" (không có file path)
- Git operations: commit, push, merge, rebase
- Documentation: README, HANDOFF, markdown files

**Example:**
```
✅ "Tạo Logger.php" → auto gọi kiwi_context
✅ "Fix SQL injection trong search.php" → auto gọi kiwi_context
❌ "Giải thích code này" → KHÔNG gọi (không phải task code)
❌ "Fix crash trong .claude/kiwi/" → KHÔNG gọi (Kiwi internal)
```

## Token Optimization

Kiwi được thiết kế để tiết kiệm token:

### 1. kiwi_context với compact mode

```javascript
// Full mode (feature mới, cần full context)
kiwi_context({
  task: "loyalty plugin",
  scope_type: "plugin",
  compact: false
})

// Compact mode (fix nhỏ, edit < 10 dòng)
kiwi_context({
  task: "fix SQL injection",
  scope_type: "plugin",
  compact: true  // Saves ~70% tokens
})
```

### 2. kiwi_check thay vì kiwi_scan

```javascript
// Sau Write/Edit → dùng kiwi_check (0 token, instant)
kiwi_check({
  file: "src/Plugin.php",
  severity: "CRITICAL"
})

// Thay vì kiwi_scan toàn project (tốn nhiều token)
```

### 3. kiwi_deploy với cache

```javascript
// First deploy: ~3500 tokens (full scan)
kiwi_deploy({
  path: "themes/sfvn",
  type: "wp_theme",
  mode: "execute"
})

// Subsequent deploys (code unchanged): ~500 tokens (skip scan)
kiwi_deploy({
  path: "themes/sfvn",
  type: "wp_theme",
  mode: "execute",
  skip_scan: true  // Use cached scan result
})
```

**Token savings:**
- First deploy: 3,400 tokens (vs 7,700 baseline) — **56% reduction**
- Unchanged code: 500 tokens (vs 7,700) — **94% reduction**
- Incremental: 1,000 tokens (vs 7,700) — **87% reduction**

## Workflow Examples

### Workflow 1: Code với Kiwi Context

```
1. User: "Tạo Logger.php"
2. Claude: Auto gọi kiwi_context(task="Logger class", compact=false)
3. Claude: Đọc rules, anti-patterns, snippets
4. Claude: Write Logger.php
5. Hook: post_edit.py auto-scan CRITICAL
6. Nếu PASS → done
   Nếu BLOCK → Claude phải fix ngay
```

### Workflow 2: Fix Bug với Impact Analysis

```
1. Claude: Fix bug trong src/Cart.php
2. Claude: Gọi kiwi_impact(file="src/Cart.php")
3. Kiwi: Tìm affected files (callers, importers)
4. Claude: Scan affected files để phòng regression
5. Nếu phát hiện issue → fix luôn
```

### Workflow 3: Deploy với Pre-checks

```
1. Claude: Gọi kiwi_deploy(mode="verify")
2. Kiwi: Pre-checks (git clean, scan CRITICAL, build plan)
3. Nếu PASS → Claude gọi kiwi_deploy(mode="execute")
4. Kiwi: Execute + health checks + auto-rollback on fail
```

## Configuration

Kiwi MCP server được gọi qua hooks, không cần config thêm trong settings.json.

**Current setup:**
- MCP server: `python d:/projects/wezone/.claude/kiwi/mcp_server.py`
- Hooks: Đã config trong `.claude/settings.json`
- Tools: 19 tools available qua JSON-RPC stdio

## Troubleshooting

**Hook không chạy:**

```bash
# Check hook config
cat .claude/settings.json | grep -A 10 "hooks"

# Test hook manually
python .claude/kiwi/hooks/post_edit.py
```

**MCP tool không available:**

```bash
# Check MCP server
python .claude/kiwi/mcp_server.py

# Test tool call
echo '{"jsonrpc":"2.0","id":1,"method":"tools/list"}' | python .claude/kiwi/mcp_server.py
```

**kiwi_context bị skip:**

Check xem file có thuộc exclusion list không:
- `.claude/kiwi/` → excluded
- `rag/` → excluded
- `*.md` → excluded

## Performance Metrics

**Hook overhead:**
- post_edit.py: ~200ms (scan 1 file)
- pre_edit.py: ~50ms (check session state)
- track_kiwi_context.py: ~30ms (write to file)

**MCP tool latency:**
- kiwi_check: ~200ms (instant scan)
- kiwi_context: ~500ms (load rules)
- kiwi_scan: ~5-30s (depends on project size)
- kiwi_deploy: ~10-60s (depends on deploy type)

## See Also

- [README-CLI.md](README-CLI.md) — Standalone CLI usage
- [README.md](README.md) — Main documentation
- [CLAUDE.md](../../CLAUDE.md) — Project rules
