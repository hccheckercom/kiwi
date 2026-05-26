# Phase 1: MCP Server — Kiwi Tools

## Mục tiêu

Biến Kiwi thành MCP server để Claude Code (và bất kỳ MCP client nào) gọi trực tiếp, không cần subprocess hay skill wrapper.

## File & Registration

**Server:** `.claude/kiwi/mcp_server.py` (~250 lines)
**Protocol:** JSON-RPC 2.0 via stdio (giống `rag_server.py`)
**Register:** Thêm vào `.mcp.json`:

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

## 7 MCP Tools

### 1. `kiwi_scan`

Scan project cho violations.

```json
{
  "name": "kiwi_scan",
  "description": "Scan project/theme cho bug patterns. Trả về violations grouped by severity.",
  "inputSchema": {
    "type": "object",
    "properties": {
      "path": {
        "type": "string",
        "description": "Path tới project/theme cần scan. Hoặc tên project trong _meta.json (wezone-plugins, webstore-vn)"
      },
      "severity": {
        "type": "string",
        "enum": ["CRITICAL", "HIGH", "SUGGEST", "ALL"],
        "default": "ALL",
        "description": "Lọc theo severity"
      },
      "platform": {
        "type": "string",
        "enum": ["wp", "nextjs"],
        "description": "Lọc theo platform"
      },
      "scope": {
        "type": "string",
        "enum": ["theme", "plugin"],
        "description": "Lọc theo scope type"
      },
      "diff_only": {
        "type": "boolean",
        "default": false,
        "description": "Chỉ scan files changed trong git"
      },
      "max_per_lesson": {
        "type": "integer",
        "default": 5,
        "description": "Max violations per lesson (giảm noise)"
      },
      "group": {
        "type": "boolean",
        "default": true,
        "description": "Group violations by lesson_id"
      }
    },
    "required": ["path"]
  }
}
```

**Reuses:** `scanner.cli.scan_theme()` + `scanner.cli.run_cli()` logic
**Returns:** Summary (critical/high/suggest counts) + top violations

### 2. `kiwi_query`

Search lessons by keyword, category, hoặc ID.

```json
{
  "name": "kiwi_query",
  "description": "Search Kiwi knowledge base. Tìm lessons theo keyword, category, severity, hoặc ID.",
  "inputSchema": {
    "type": "object",
    "properties": {
      "keyword": {
        "type": "string",
        "description": "Keyword tìm trong title, pattern, content (ví dụ: 'IDOR', 'XSS', 'mobile-first')"
      },
      "category": {
        "type": "string",
        "description": "Filter by category (php-security, wezone-api, css-tokens, ...)"
      },
      "severity": {
        "type": "string",
        "enum": ["CRITICAL", "HIGH", "SUGGEST", "INFO"]
      },
      "platform": {
        "type": "string",
        "enum": ["wp", "nextjs"]
      },
      "limit": {
        "type": "integer",
        "default": 10,
        "description": "Max results"
      }
    }
  }
}
```

**Reuses:** `scanner.loader.load_patterns()` + full-text grep on lesson files
**Returns:** List of matching lessons: id, severity, category, title, pattern

### 3. `kiwi_lesson`

Get full lesson content.

```json
{
  "name": "kiwi_lesson",
  "description": "Đọc full lesson: Bad code, Good code, Why, Grep hint. Dùng khi cần hiểu chi tiết một pattern.",
  "inputSchema": {
    "type": "object",
    "properties": {
      "id": {
        "type": "string",
        "description": "Lesson ID (ví dụ: LES-016, FEA-025)"
      }
    },
    "required": ["id"]
  }
}
```

**Reuses:** `scanner.loader._parse_frontmatter()` + file read
**Returns:** Full lesson: frontmatter (id, severity, category, scan config) + Bad/Good/Why/Grep sections

### 4. `kiwi_add`

Add new lesson.

```json
{
  "name": "kiwi_add",
  "description": "Thêm lesson mới vào Kiwi knowledge base. Tự tạo file, update _meta.json, rebuild README.",
  "inputSchema": {
    "type": "object",
    "properties": {
      "category": {
        "type": "string",
        "description": "Category (php-security, wezone-api, css-tokens, ...)"
      },
      "severity": {
        "type": "string",
        "enum": ["CRITICAL", "HIGH", "SUGGEST", "INFO"]
      },
      "title": {
        "type": "string",
        "description": "Mô tả ngắn về bug pattern"
      },
      "scan_type": {
        "type": "string",
        "enum": ["presence", "absence", "cross-check", "bom-check"],
        "default": "presence"
      },
      "pattern": {
        "type": "string",
        "description": "Regex pattern cho scanner"
      },
      "scope": {
        "type": "string",
        "default": "**/*.php",
        "description": "File glob pattern"
      },
      "tags": {
        "type": "array",
        "items": {"type": "string"},
        "default": ["theme"]
      },
      "bad_code": {"type": "string", "description": "Ví dụ code sai"},
      "good_code": {"type": "string", "description": "Ví dụ code đúng"},
      "why": {"type": "string", "description": "Giải thích tại sao đây là bug"},
      "platform": {
        "type": "string",
        "enum": ["wp", "nextjs", "both"],
        "default": "wp"
      }
    },
    "required": ["category", "severity", "title", "pattern"]
  }
}
```

**Reuses:** `tools/add.py` core logic (create file, update _meta.json, rebuild index)
**Returns:** Created lesson ID + file path

### 5. `kiwi_stats`

Statistics breakdown.

```json
{
  "name": "kiwi_stats",
  "description": "Thống kê Kiwi knowledge base: severity, category, check type distribution.",
  "inputSchema": {
    "type": "object",
    "properties": {}
  }
}
```

**Reuses:** `tools/stats.py` logic
**Returns:** Severity counts, category breakdown, check type distribution

### 6. `kiwi_fix`

Get fix suggestion (Phase 1: read-only; Phase 2: can apply).

```json
{
  "name": "kiwi_fix",
  "description": "Lấy fix suggestion cho violation. Phase 1: trả Good code example. Phase 2: có thể apply fix tự động.",
  "inputSchema": {
    "type": "object",
    "properties": {
      "lesson_id": {
        "type": "string",
        "description": "Lesson ID (ví dụ: LES-016)"
      },
      "file": {
        "type": "string",
        "description": "File chứa violation (optional — để context)"
      },
      "line": {
        "type": "integer",
        "description": "Line number (optional)"
      },
      "apply": {
        "type": "boolean",
        "default": false,
        "description": "Phase 2: true = apply fix, false = chỉ show suggestion"
      }
    },
    "required": ["lesson_id"]
  }
}
```

**Reuses:** `scanner.cli.get_fix_for_lesson()`
**Returns:** Good code example + Why section. Phase 2: diff preview, then apply if requested.

### 7. `kiwi_template`

Query template library.

```json
{
  "name": "kiwi_template",
  "description": "Tìm template sections đã kiểm chứng (hero, header, footer, product-card, ...). Dùng khi code section mới.",
  "inputSchema": {
    "type": "object",
    "properties": {
      "section": {
        "type": "string",
        "description": "Section type (hero, header, footer, product-card, flash-sale, ...)"
      },
      "tag": {
        "type": "string",
        "description": "Filter by tag"
      },
      "keyword": {
        "type": "string",
        "description": "Full-text search"
      },
      "detail": {
        "type": "boolean",
        "default": false,
        "description": "true = full template code, false = list only"
      }
    }
  }
}
```

**Reuses:** `templates/tools/query.py` — `load_all_templates()`, `filter_templates()`
**Returns:** Template list or full template with code

## Implementation Pattern

Follow `rag_server.py` exactly:

```python
"""Kiwi MCP Server — Bug pattern scanner as MCP tools."""
import sys
import json
from pathlib import Path

KIWI_DIR = Path(__file__).parent

# Lazy imports
_patterns = None

def _ensure_imports():
    """Lazy import scanner modules."""
    global _patterns
    if _patterns is not None:
        return
    sys.path.insert(0, str(KIWI_DIR))
    from scanner.loader import load_patterns
    _patterns = load_patterns

def handle_request(req: dict) -> dict:
    method = req.get("method", "")
    req_id = req.get("id")

    if method == "initialize":
        return {"jsonrpc": "2.0", "id": req_id, "result": {
            "protocolVersion": "2024-11-05",
            "capabilities": {"tools": {}},
            "serverInfo": {"name": "kiwi", "version": "1.0.0"},
        }}

    if method == "notifications/initialized":
        return None  # no response needed

    if method == "tools/list":
        return {"jsonrpc": "2.0", "id": req_id, "result": {"tools": [
            # ... 7 tool definitions above
        ]}}

    if method == "tools/call":
        tool = req.get("params", {}).get("name", "")
        args = req.get("params", {}).get("arguments", {})
        _ensure_imports()

        if tool == "kiwi_scan":
            return _handle_scan(req_id, args)
        elif tool == "kiwi_query":
            return _handle_query(req_id, args)
        # ... etc

    return {"jsonrpc": "2.0", "id": req_id,
            "error": {"code": -32601, "message": f"Method not found: {method}"}}

def main():
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            req = json.loads(line)
            resp = handle_request(req)
        except Exception as e:
            resp = {"jsonrpc": "2.0", "id": None,
                    "error": {"code": -32700, "message": f"Parse error: {e}"}}
        if resp is not None:
            print(json.dumps(resp, ensure_ascii=False), flush=True)

if __name__ == "__main__":
    main()
```

## Output Format

### kiwi_scan output (grouped)
```
Kiwi Scan: D:\projects\wezone\wezone-plugins
Patterns: 312 | Files: 89 | Platform: wp

Summary: 5 CRITICAL | 12 HIGH | 3 SUGGEST

CRITICAL (5):
  LES-016 [php-security] Order page thiếu IDOR check (3 hits)
    → wezone-templates/account/orders.php:42
    → wezone-templates/account/order-detail.php:18
    → wezone-templates/account/order-tracking.php:25

  LES-362 [php-security] innerHTML with server data (2 hits)
    → assets/js/checkout.js:156
    → assets/js/cart.js:89

HIGH (12):
  LES-006 [css-tokens] Hardcoded color (5 hits)
    → src/checkout.css:34
    ...

Full lessons: .claude/kiwi/lessons/<category>/<ID>.md
```

### kiwi_query output
```
Kiwi Query: "IDOR" (3 results)

1. LES-016 [CRITICAL] [php-security]
   Order page thiếu IDOR check (user_id !== current user)
   Pattern: \$_GET\['order_id'\]|\$_POST\['order_id'\]
   Scope: wezone-templates/account/*.php

2. LES-017 [CRITICAL] [php-security]
   Profile edit thiếu ownership check
   Pattern: update_user_meta.*\$_POST
   Scope: wezone-templates/account/*.php

3. LES-429 [HIGH] [php-security]
   API endpoint thiếu nonce verification
   Pattern: wp_ajax_.*function
   Scope: **/*.php
```

## Verification Steps

1. **Unit test MCP protocol:**
   ```powershell
   echo '{"jsonrpc":"2.0","id":1,"method":"tools/list"}' | python .claude/kiwi/mcp_server.py
   # Expect: 7 tools listed
   ```

2. **Test kiwi_scan:**
   ```powershell
   echo '{"jsonrpc":"2.0","id":2,"method":"tools/call","params":{"name":"kiwi_scan","arguments":{"path":"wezone-plugins","severity":"CRITICAL"}}}' | python .claude/kiwi/mcp_server.py
   # Expect: violations report
   ```

3. **Test kiwi_query:**
   ```powershell
   echo '{"jsonrpc":"2.0","id":3,"method":"tools/call","params":{"name":"kiwi_query","arguments":{"keyword":"IDOR"}}}' | python .claude/kiwi/mcp_server.py
   # Expect: matching lessons
   ```

4. **Register & verify in Claude Code:**
   - Add to `.mcp.json`
   - Restart Claude Code
   - Verify `kiwi_scan`, `kiwi_query` etc. appear as available tools
   - Call `kiwi_scan` from conversation

5. **Backward compatibility:**
   - Verify CLI still works: `python -m scanner.cli --theme <path>`
   - Verify post_edit hook still fires
   - Verify skills `/kst`, `/kiwi-scan` still work
