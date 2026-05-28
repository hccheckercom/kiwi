# A7 — HTTP Server + WebSocket (2 days)

## Mục tiêu
VS Code extension và Web dashboard cần giao tiếp với Kiwi engine. MCP (stdio) chỉ phục vụ Claude Code. HTTP server mở ra cho mọi client: VS Code extension, browser dashboard, CI/CD webhooks, remote editors.

**One-liner:** `kiwi serve` → local HTTP + WebSocket server, expose toàn bộ Kiwi tools qua REST API.

---

## Dependencies
- A1 (core/plugin separation — handler logic)
- A4 (usage tracking — dashboard data)
- A5 (freemium gating — tier checks)
- A6 (CLI packaging — `kiwi serve` command)

## Scope — IN vs OUT

| IN (A7) | OUT (defer) |
|---------|-------------|
| FastAPI HTTP server | VS Code extension UI (→ B-series) |
| REST endpoints (1:1 with MCP tools) | Cloud sync / team server |
| WebSocket real-time events | Remote/public deployment |
| `kiwi serve` CLI command | OAuth / multi-user auth |
| Local-only binding (127.0.0.1) | Rate limiting (local = unlimited) |
| Auto-generated OpenAPI docs | |
| File watcher → auto-check events | |

---

## Technical Decisions

| Decision | Choice | Why |
|----------|--------|-----|
| Framework | **FastAPI** | Async native, WebSocket built-in, OpenAPI auto-docs, lightweight |
| Transport | HTTP + WebSocket | REST for request/response, WS for streaming events |
| Auth | Bearer token (optional) | Local-only default (127.0.0.1), token for remote/CI use |
| Port | 7891 (default) | Avoid conflicts with common dev ports (3000, 5000, 8000, 8080) |
| Process model | Single process, async | Kiwi is I/O-bound (file reads), no need for workers |
| Serialization | JSON | Standard, matches MCP protocol |

---

## Tasks

### Day 1: Core server + REST endpoints

| # | Task |
|---|------|
| 7.1 | Create `server/` module: `__init__.py`, `app.py`, `routes/`, `ws.py` |
| 7.2 | `app.py`: FastAPI app factory, CORS, error handling, lifespan |
| 7.3 | `routes/scan.py`: POST /api/scan, POST /api/check — reuse `_handle_scan`, `_handle_check` |
| 7.4 | `routes/knowledge.py`: GET /api/lessons, GET /api/lessons/{id}, POST /api/context, GET /api/stats |
| 7.5 | `routes/fix.py`: POST /api/fix, POST /api/dismiss, GET /api/trends |
| 7.6 | `routes/dashboard.py`: GET /api/dashboard, GET /api/status |
| 7.7 | `routes/tier.py`: GET /api/tier, POST /api/upgrade |
| 7.8 | Auth middleware: optional Bearer token from `.kiwi/config.json` |
| 7.9 | CLI command: `kiwi serve [--port] [--host] [--daemon]` |

### Day 2: WebSocket + file watcher + tests

| # | Task |
|---|------|
| 7.10 | `ws.py`: WebSocket endpoint `/ws` — connection manager, broadcast |
| 7.11 | Event types: `scan.start`, `scan.progress`, `scan.complete`, `violation.found`, `fix.applied` |
| 7.12 | File watcher: watchdog → on file save → auto-check → broadcast violations via WS |
| 7.13 | `routes/health.py`: GET /health, GET /api/openapi.json |
| 7.14 | Integration: scan progress streams via WS while HTTP returns final result |
| 7.15 | Test suite: `tests/test_a7_server.py` — 40+ checks |
| 7.16 | Cross-platform test: Windows + Unix (uvicorn) |

---

## Architecture

```
┌─────────────────────────────────────────────────────────┐
│  CLIENTS                                                 │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌────────┐ │
│  │ VS Code  │  │ Browser  │  │   CI/CD  │  │ Remote │ │
│  │Extension │  │Dashboard │  │ Webhook  │  │ Editor │ │
│  └────┬─────┘  └────┬─────┘  └────┬─────┘  └───┬────┘ │
│       │              │              │             │      │
├───────┼──────────────┼──────────────┼─────────────┼──────┤
│       ▼              ▼              ▼             ▼      │
│  ┌──────────────────────────────────────────────────┐   │
│  │  FastAPI Server (127.0.0.1:7891)                  │   │
│  │  ├── REST API (/api/*)                           │   │
│  │  ├── WebSocket (/ws)                             │   │
│  │  ├── OpenAPI docs (/docs)                        │   │
│  │  └── Health check (/health)                      │   │
│  ├──────────────────────────────────────────────────┤   │
│  │  Middleware                                       │   │
│  │  ├── Auth (optional Bearer token)                │   │
│  │  ├── CORS (localhost origins)                    │   │
│  │  ├── Tier gating (reuse core.gating)            │   │
│  │  └── Usage tracking (reuse tracking.usage_tracker)│  │
│  ├──────────────────────────────────────────────────┤   │
│  │  Handlers (reuse from mcp_server.py)              │   │
│  │  ├── _handle_scan()                              │   │
│  │  ├── _handle_check()                             │   │
│  │  ├── _handle_fix()                               │   │
│  │  ├── _handle_context()                           │   │
│  │  └── ... (all 19 MCP handlers)                   │   │
│  ├──────────────────────────────────────────────────┤   │
│  │  File Watcher (watchdog)                          │   │
│  │  └── on_modified → auto_check → WS broadcast     │   │
│  └──────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────┘
```

---

## REST API Endpoints

| Method | Path | Maps to | Tier |
|--------|------|---------|------|
| POST | `/api/scan` | `_handle_scan` | Free (3/day) |
| POST | `/api/check` | `_handle_check` | Free (unlimited) |
| POST | `/api/context` | `_handle_context` | Free |
| POST | `/api/fix` | `_handle_fix` | Pro |
| POST | `/api/dismiss` | `_handle_dismiss` | Pro |
| GET | `/api/lessons` | `_handle_query` | Free (10 results) |
| GET | `/api/lessons/{id}` | `_handle_lesson` | Pro |
| GET | `/api/stats` | `_handle_stats` | Free |
| GET | `/api/dashboard` | `_handle_dashboard` | Free |
| GET | `/api/trends` | `_handle_trends` | Pro |
| GET | `/api/status` | tier + health + project info | Free |
| GET | `/api/tier` | `_handle_tier` | Free |
| POST | `/api/upgrade` | `_handle_upgrade` | Free |
| GET | `/health` | server health | — |
| GET | `/docs` | OpenAPI Swagger UI | — |

### Request/Response format

```json
// POST /api/scan
{
  "path": ".",
  "severity": "CRITICAL",
  "platform": "wp",
  "diff_only": false
}

// Response 200
{
  "status": "ok",
  "data": {
    "violations": [...],
    "summary": { "critical": 2, "high": 5, "suggest": 12 },
    "files_scanned": 47,
    "patterns_checked": 379
  }
}

// Error response
{
  "status": "error",
  "error": { "code": "TIER_LIMIT", "message": "Free tier: 3 scans/day. Upgrade for unlimited." }
}
```

---

## WebSocket Protocol

### Connection
```
ws://127.0.0.1:7891/ws
Headers: Authorization: Bearer <token> (optional)
```

### Event format (server → client)
```json
{
  "event": "scan.progress",
  "data": {
    "file": "src/utils.ts",
    "violations_found": 2,
    "files_remaining": 15
  },
  "timestamp": "2026-05-28T10:30:00Z"
}
```

### Event types

| Event | When | Data |
|-------|------|------|
| `scan.start` | Scan begins | `{ path, total_files }` |
| `scan.progress` | Each file scanned | `{ file, violations_found, files_remaining }` |
| `scan.complete` | Scan done | `{ summary, duration_ms }` |
| `violation.found` | Real-time violation | `{ file, line, lesson_id, severity, message }` |
| `fix.applied` | Auto-fix applied | `{ file, lesson_id, diff_preview }` |
| `file.changed` | File watcher detected change | `{ file, action }` |
| `check.result` | Auto-check after file save | `{ file, violations }` |

### Commands (client → server)
```json
{ "command": "subscribe", "channels": ["scan", "violation", "file"] }
{ "command": "unsubscribe", "channels": ["file"] }
{ "command": "scan", "params": { "path": ".", "severity": "ALL" } }
```

---

## File Watcher Integration

```python
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

class KiwiFileHandler(FileSystemEventHandler):
    def on_modified(self, event):
        if not event.is_directory and self._is_scannable(event.src_path):
            # Debounce 500ms, then auto-check
            violations = quick_check(event.src_path)
            ws_manager.broadcast("check.result", {
                "file": event.src_path,
                "violations": violations
            })
```

**Watched extensions:** `.php`, `.js`, `.ts`, `.tsx`, `.jsx`, `.css`, `.py`, `.go`, `.rs`
**Debounce:** 500ms (avoid rapid-fire on save-all)
**Scope:** Project root from `.kiwi/config.json`

---

## CLI Command: `kiwi serve`

```
Usage: kiwi serve [OPTIONS]

  Start Kiwi HTTP + WebSocket server.

Options:
  --port INTEGER    Port to bind (default: 7891)
  --host TEXT       Host to bind (default: 127.0.0.1)
  --daemon          Run as background daemon
  --no-watch        Disable file watcher
  --token TEXT      Set auth token (or use KIWI_TOKEN env)
  --open            Open browser to /docs after start
```

### Daemon mode
```powershell
kiwi serve --daemon          # Start background, write PID to .kiwi/server.pid
kiwi serve --daemon --stop   # Stop background server
kiwi serve --daemon --status # Check if running
```

---

## Module Structure

```
kiwi/
├── server/
│   ├── __init__.py          # version, create_app()
│   ├── app.py               # FastAPI app factory, lifespan, middleware
│   ├── auth.py              # Bearer token validation
│   ├── ws.py                # WebSocket manager, broadcast, subscriptions
│   ├── watcher.py           # File watcher (watchdog integration)
│   ├── routes/
│   │   ├── __init__.py      # router aggregation
│   │   ├── scan.py          # /api/scan, /api/check
│   │   ├── knowledge.py     # /api/lessons, /api/context, /api/stats
│   │   ├── fix.py           # /api/fix, /api/dismiss, /api/trends
│   │   ├── dashboard.py     # /api/dashboard, /api/status
│   │   ├── tier.py          # /api/tier, /api/upgrade
│   │   └── health.py        # /health
│   └── models.py            # Pydantic request/response schemas
├── cli/
│   └── commands/
│       └── serve.py         # kiwi serve command (NEW)
└── tests/
    └── test_a7_server.py    # 40+ checks
```

---

## Handler Reuse Strategy (zero duplication)

MCP server handlers (`mcp_server.py`) accept `dict` args and return `str`. HTTP routes:

```python
# routes/scan.py
from fastapi import APIRouter
from ..models import ScanRequest, ScanResponse

router = APIRouter()

@router.post("/api/scan", response_model=ScanResponse)
async def scan_endpoint(req: ScanRequest):
    # Reuse existing handler
    from mcp_server import _handle_scan
    result_str = _handle_scan(req.dict())
    return parse_scan_result(result_str)
```

**Refactor needed:** Extract handler logic from `mcp_server.py` into `core/handlers.py` so both MCP and HTTP import from same source. MCP server becomes thin wrapper (JSON-RPC → handlers). HTTP routes become thin wrapper (REST → handlers).

```
Before:  mcp_server.py (handlers + JSON-RPC protocol)
After:   core/handlers.py (pure logic)
         mcp_server.py (JSON-RPC wrapper → core/handlers)
         server/routes/* (HTTP wrapper → core/handlers)
```

---

## Dependencies (Python packages)

```toml
[project.optional-dependencies]
server = [
    "fastapi>=0.100",
    "uvicorn[standard]>=0.20",
    "watchdog>=3.0",
    "websockets>=11.0",
]
```

**Install:** `pip install kiwi-ai[server]` — server deps are optional extra.
**Without server:** `pip install kiwi-ai` — CLI + MCP only, no FastAPI.

---

## Security

| Concern | Mitigation |
|---------|-----------|
| Remote access | Default bind 127.0.0.1 (local only) |
| Unauthorized access | Optional Bearer token |
| Path traversal | Validate all paths within project root |
| Command injection | No shell execution from HTTP params |
| DoS | Local-only = trusted environment |
| CORS | Allow only localhost origins by default |

---

## VS Code Extension Communication (protocol spec)

VS Code extension connects to `ws://127.0.0.1:7891/ws` on activation:

```
1. Extension activates → check if kiwi server running (GET /health)
2. If not running → spawn `kiwi serve --daemon`
3. Connect WebSocket → subscribe to ["violation", "check", "fix"]
4. On file save → server auto-checks → WS pushes diagnostics
5. Extension renders diagnostics as VS Code Problems
6. User clicks "Quick Fix" → extension calls POST /api/fix
7. Extension applies returned diff
```

**Diagnostic mapping:**
| Kiwi severity | VS Code DiagnosticSeverity |
|---------------|---------------------------|
| CRITICAL | Error |
| HIGH | Warning |
| SUGGEST | Information |

---

## Performance Targets

| Metric | Target |
|--------|--------|
| Server startup | < 500ms |
| Single file check (HTTP) | < 200ms |
| Full scan (50 files) | < 3s |
| WebSocket latency | < 50ms |
| Memory (idle) | < 50MB |
| Memory (scanning) | < 150MB |

---

## Done khi
- [ ] `pip install kiwi-ai[server]` installs FastAPI + uvicorn + watchdog
- [ ] `kiwi serve` starts server, prints "Kiwi server running at http://127.0.0.1:7891"
- [ ] `GET /health` returns `{"status": "ok", "version": "1.0.0"}`
- [ ] `GET /docs` shows Swagger UI with all endpoints
- [ ] `POST /api/scan` returns same violations as `kiwi scan` CLI
- [ ] `POST /api/check` returns same result as `kiwi check` CLI
- [ ] WebSocket connects, receives events during scan
- [ ] File watcher detects save → auto-check → WS broadcast
- [ ] `kiwi serve --daemon` runs in background, `--stop` kills it
- [ ] Auth token blocks unauthorized requests when configured
- [ ] All paths validated (no traversal outside project root)
- [ ] `tests/test_a7_server.py` — 40+ checks, all PASS
- [ ] A6 backward compat maintained (77/77 still pass)
- [ ] Handler logic extracted to `core/handlers.py` (shared by MCP + HTTP)