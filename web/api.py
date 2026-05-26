"""FastAPI backend for Kiwi web dashboard."""

import json
import os
import sys
from datetime import timedelta
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException, Depends, status
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

KIWI_DIR = Path(__file__).parent.parent
PROJECT_ROOT = KIWI_DIR.parent.parent
sys.path.insert(0, str(KIWI_DIR))
sys.path.insert(0, str(KIWI_DIR / "web"))

# Import auth after sys.path setup
AUTH_ENABLED = True  # Enable auth for production
try:
    import auth
    LoginRequest = auth.LoginRequest
    TokenResponse = auth.TokenResponse
    User = auth.User
    authenticate_user = auth.authenticate_user
    create_access_token = auth.create_access_token
    get_current_user = auth.get_current_user
    ACCESS_TOKEN_EXPIRE_HOURS = auth.ACCESS_TOKEN_EXPIRE_HOURS
except ImportError as e:
    # Fallback if auth module not available
    print(f"WARNING: Auth module not available: {e}", file=sys.stderr)
    AUTH_ENABLED = False


def resolve_project_path(path: str) -> str:
    """Resolve relative path to absolute path from project root."""
    p = Path(path)
    if p.is_absolute():
        return str(p)

    # Try _meta.json mapping first
    meta_path = KIWI_DIR / "_meta.json"
    if meta_path.exists():
        try:
            import json
            meta = json.loads(meta_path.read_text(encoding="utf-8"))
            resolved = meta.get("projects", {}).get(path)
            if resolved and Path(resolved).exists():
                return resolved
        except Exception as e:
            import sys
            print(f"[kiwi] resolve_project_path meta error: {e}", file=sys.stderr)

    # Try relative to project root first
    project_path = PROJECT_ROOT / path
    if project_path.exists():
        return str(project_path)

    # Try as-is (might be relative to CWD)
    if p.exists():
        return str(p.resolve())

    # Return project root relative path even if doesn't exist yet
    return str(project_path)


def validate_scan_path(path: str) -> str:
    """Validate and resolve scan path, raise 422 if invalid."""
    resolved = resolve_project_path(path)
    resolved_path = Path(resolved)

    # Only validate if path looks like absolute path (not project name)
    if os.path.isabs(path):
        if not resolved_path.exists():
            raise HTTPException(
                status_code=422,
                detail=f"Path does not exist: {path}"
            )

        if not resolved_path.is_dir():
            raise HTTPException(
                status_code=422,
                detail=f"Path is not a directory: {path}"
            )

    return resolved

from scanner.cli import scan_theme

# Import persistence after path setup
try:
    from persistence import save_scan_history, save_approval, get_scan_trends, get_approval
except ImportError:
    # Fallback if persistence not available
    def save_scan_history(*args, **kwargs): pass
    def save_approval(*args, **kwargs): pass
    def get_scan_trends(*args, **kwargs): return []
    def get_approval(*args, **kwargs): return None

# Import checkpoint manager
try:
    from checkpoint import CheckpointManager, Checkpoint
    checkpoint_manager = CheckpointManager()
except ImportError:
    checkpoint_manager = None

app = FastAPI(title="Kiwi Dashboard API", version="1.0.0")

KIWI_CORS_ORIGINS = os.environ.get(
    "KIWI_CORS_ORIGINS",
    "http://localhost:3000,http://localhost:5173,http://localhost:5175"
).split(",")

app.add_middleware(
    CORSMiddleware,
    allow_origins=KIWI_CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class ScanRequest(BaseModel):
    path: str
    severity: str = "CRITICAL"
    platform: Optional[str] = None


class PlanRequest(BaseModel):
    path: str
    severity: str = "CRITICAL"
    max_fixes: int = 10


class ApprovalRequest(BaseModel):
    task_id: str
    approved: bool
    comment: Optional[str] = None


class ConnectionManager:
    """Manage WebSocket connections."""

    def __init__(self):
        self.active_connections: list[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        self.active_connections.remove(websocket)

    async def broadcast(self, message: dict):
        for connection in self.active_connections:
            try:
                await connection.send_json(message)
            except Exception as e:
                import sys
                print(f"WARNING: WebSocket send failed: {e}", file=sys.stderr)


manager = ConnectionManager()


@app.get("/")
async def root():
    return {"message": "Kiwi Dashboard API", "version": "1.0.0"}


@app.get("/health")
async def health():
    return {"status": "healthy"}


if AUTH_ENABLED:
    @app.post("/auth/login", response_model=TokenResponse)
    async def login(request: LoginRequest):
        """Authenticate user and return JWT token."""
        user = authenticate_user(request.username, request.password)
        if not user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Incorrect username or password",
                headers={"WWW-Authenticate": "Bearer"},
            )

        access_token = create_access_token(
            data={"sub": user["username"], "role": user["role"]},
            expires_delta=timedelta(hours=ACCESS_TOKEN_EXPIRE_HOURS),
        )

        return TokenResponse(
            access_token=access_token,
            expires_in=ACCESS_TOKEN_EXPIRE_HOURS * 3600,
        )

    @app.get("/auth/me", response_model=User)
    async def get_me(current_user: User = Depends(get_current_user)):
        """Get current authenticated user."""
        return current_user


@app.post("/api/scan")
async def scan_project(request: ScanRequest, current_user: Optional[dict] = Depends(get_current_user) if AUTH_ENABLED else None):
    """Scan project for violations."""
    try:
        # Log request for debugging
        print(f"[DEBUG] /api/scan request: path={request.path}, severity={request.severity}", file=sys.stderr, flush=True)

        # Resolve path (handles both absolute paths and project names like 'wezone-plugins')
        resolved_path = resolve_project_path(request.path)
        print(f"[DEBUG] Resolved path: {resolved_path}", file=sys.stderr, flush=True)

        # Check if resolved path exists
        if not Path(resolved_path).exists():
            print(f"[ERROR] Path does not exist: {resolved_path}", file=sys.stderr, flush=True)
            raise HTTPException(
                status_code=422,
                detail=f"Path does not exist: {request.path} (resolved to: {resolved_path})"
            )

        # Progress callback for WebSocket streaming
        def progress_callback(checked: int, total: int, violations: int):
            import asyncio
            asyncio.create_task(manager.broadcast({
                "type": "scan_progress",
                "patterns_checked": checked,
                "total_patterns": total,
                "violations_found": violations
            }))

        report = scan_theme(
            resolved_path,
            severity_filter=request.severity,
            platform=request.platform,
            progress_callback=progress_callback
        )

        violations = [
            {
                "lesson_id": v.lesson_id,
                "file": v.file,
                "line": v.line,
                "severity": v.severity,
                "category": v.category,
                "description": v.description,
                "match_text": v.match_text[:100] if v.match_text else "",
            }
            for v in report.violations
        ]

        # Save scan to history for trends
        save_scan_history(resolved_path, report)

        await manager.broadcast({
            "type": "scan_complete",
            "data": {
                "violations_count": len(violations),
                "critical": report.critical_count,
                "high": report.high_count,
            }
        })

        return {
            "success": True,
            "violations": violations,
            "summary": {
                "total": len(violations),
                "critical": report.critical_count,
                "high": report.high_count,
                "suggest": report.suggest_count,
                "patterns_checked": report.patterns_checked,
                "files_scanned": report.files_scanned,
            }
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/plan")
async def create_plan(request: PlanRequest):
    """Create execution plan from violations."""
    try:
        print(f"[DEBUG] /api/plan request: path={request.path}, severity={request.severity}, max_fixes={request.max_fixes}", file=sys.stderr, flush=True)

        resolved_path = resolve_project_path(request.path)
        print(f"[DEBUG] Resolved path: {resolved_path}", file=sys.stderr, flush=True)

        if not Path(resolved_path).exists():
            print(f"[ERROR] Path does not exist: {resolved_path}", file=sys.stderr, flush=True)

            # Load valid project names from _meta.json
            meta_path = KIWI_DIR / "_meta.json"
            valid_projects = []
            if meta_path.exists():
                try:
                    meta = json.loads(meta_path.read_text(encoding="utf-8"))
                    valid_projects = list(meta.get("projects", {}).keys())
                except Exception as e:
                    print(f"[kiwi] create_plan meta error: {e}", file=sys.stderr)

            error_msg = f"Path does not exist: '{request.path}'"
            if valid_projects:
                error_msg += f"\n\nValid project names: {', '.join(valid_projects)}"
            error_msg += f"\n\nOr use absolute path to theme folder (e.g., D:/projects/wezone/themes/your-theme)"

            raise HTTPException(
                status_code=422,
                detail=error_msg
            )

        report = scan_theme(
            resolved_path,
            severity_filter=request.severity,
            platform=None
        )

        print(f"[DEBUG] Scan complete: {len(report.violations)} violations found", file=sys.stderr, flush=True)

        severity_priority = {"CRITICAL": 1, "HIGH": 2, "SUGGEST": 3}
        sorted_violations = sorted(
            report.violations,
            key=lambda v: (severity_priority.get(v.severity, 99), v.file, v.line)
        )[:request.max_fixes]

        tasks = []
        for idx, v in enumerate(sorted_violations):
            tasks.append({
                "id": f"task_{idx}",
                "lesson_id": v.lesson_id,
                "file": v.file,
                "line": v.line,
                "severity": v.severity,
                "category": v.category,
                "description": v.description,
                "effort": 5 if v.severity == "CRITICAL" else 3 if v.severity == "HIGH" else 2,
                "risk": 0.8 if v.severity == "CRITICAL" else 0.4 if v.severity == "HIGH" else 0.2,
                "priority": severity_priority.get(v.severity, 99)
            })

        nodes = [
            {
                "id": t["id"],
                "lesson_id": t["lesson_id"],
                "label": f"{t['lesson_id']}:{t['line']}",
                "severity": t["severity"],
                "file": t["file"],
                "line": t["line"],
                "category": t["category"],
                "description": t["description"],
                "effort": t["effort"],
                "risk": t["risk"],
                "priority": t["priority"]
            }
            for t in tasks
        ]

        critical_tasks = [t["id"] for t in tasks if t["severity"] == "CRITICAL"]
        high_tasks = [t["id"] for t in tasks if t["severity"] == "HIGH"]
        suggest_tasks = [t["id"] for t in tasks if t["severity"] == "SUGGEST"]

        stages = []
        if critical_tasks:
            stages.append({"id": "stage_0", "name": "Critical Fixes", "tasks": critical_tasks})
        if high_tasks:
            stages.append({"id": f"stage_{len(stages)}", "name": "High Priority", "tasks": high_tasks})
        if suggest_tasks:
            stages.append({"id": f"stage_{len(stages)}", "name": "Suggestions", "tasks": suggest_tasks})

        estimated_minutes = sum(t["effort"] for t in tasks)

        await manager.broadcast({
            "type": "plan_complete",
            "data": {
                "tasks_count": len(tasks),
                "estimated_minutes": estimated_minutes
            }
        })

        return {
            "success": True,
            "tasks": tasks,
            "stages": stages,
            "dependency_graph": {"nodes": nodes, "links": []},
            "critical_path": critical_tasks,
            "estimated_duration_minutes": estimated_minutes
        }
    except Exception as e:
        import traceback
        print(f"ERROR in /api/plan: {e}", file=sys.stderr)
        print(traceback.format_exc(), file=sys.stderr)
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/agent-runs")
async def get_agent_runs(path: Optional[str] = None):
    """Get active agent runs."""
    # TODO: Implement coordination module (Phase 5)
    return {"success": True, "runs": []}


@app.get("/api/agent-runs/{run_id}")
async def get_agent_run(run_id: int):
    """Get specific agent run."""
    # TODO: Implement coordination module (Phase 5)
    raise HTTPException(status_code=404, detail="Agent run not found")


@app.get("/api/consensus/{lesson_id}/{file}")
async def get_consensus(lesson_id: str, file: str, line: Optional[int] = None):
    """Get consensus for a violation."""
    # TODO: Implement coordination module (Phase 5)
    return {"success": True, "consensus": {"verdict": "unknown", "confidence": 0.0}}


@app.post("/api/approval")
async def submit_approval(request: ApprovalRequest):
    """Submit approval decision for a task."""
    await manager.broadcast({
        "type": "approval_submitted",
        "data": {
            "task_id": request.task_id,
            "approved": request.approved,
        }
    })
    return {"success": True, "message": "Approval recorded"}


@app.get("/api/trends/{project_name}")
async def get_trends(project_name: str, days: int = 30):
    """Get violation trends for a project."""
    try:
        resolved_path = resolve_project_path(project_name)
        trends = get_scan_trends(resolved_path, days)
        return {"success": True, "trends": trends}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/stats")
async def get_stats(path: Optional[str] = None):
    """Get coordination statistics."""
    # TODO: Implement coordination module (Phase 5)
    return {"success": True, "stats": {}}


@app.get("/api/checkpoints")
async def get_checkpoints(agent_run_id: Optional[int] = None, current_user: User = Depends(get_current_user) if AUTH_ENABLED else None):
    """Get pending checkpoints, optionally filtered by agent run."""
    if checkpoint_manager is None:
        raise HTTPException(status_code=501, detail="Checkpoint system not available")

    pending = checkpoint_manager.get_pending_checkpoints(agent_run_id)
    return {
        "success": True,
        "checkpoints": [checkpoint_manager.to_dict(cp) for cp in pending]
    }


@app.post("/api/checkpoint/{checkpoint_id}/resolve")
async def resolve_checkpoint_endpoint(
    checkpoint_id: str,
    decision: str,
    comment: Optional[str] = None,
    current_user: User = Depends(get_current_user) if AUTH_ENABLED else None
):
    """Resolve a checkpoint with human decision."""
    if checkpoint_manager is None:
        raise HTTPException(status_code=501, detail="Checkpoint system not available")

    success = checkpoint_manager.resolve_checkpoint(checkpoint_id, decision, comment)

    if not success:
        raise HTTPException(status_code=404, detail="Checkpoint not found")

    # Save approval to database
    username = current_user.username if current_user else "anonymous"
    save_approval(checkpoint_id, decision, comment or "", username)

    # Broadcast resolution to WebSocket clients
    await manager.broadcast({
        "type": "checkpoint_resolved",
        "data": {
            "checkpoint_id": checkpoint_id,
            "decision": decision,
            "user": username
        }
    })

    return {"success": True, "message": "Checkpoint resolved"}


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """WebSocket endpoint for real-time updates."""
    try:
        await manager.connect(websocket)
        await websocket.send_json({"type": "connected", "status": "ok"})

        while True:
            data = await websocket.receive_text()
            message = json.loads(data)

            if message.get("type") == "ping":
                await websocket.send_json({"type": "pong"})

    except WebSocketDisconnect:
        manager.disconnect(websocket)
    except Exception as e:
        print(f"WebSocket error: {e}", file=sys.stderr)
        try:
            await websocket.close(code=1011, reason=str(e))
        except Exception as e:
            print(f"[kiwi] websocket close error: {e}", file=sys.stderr)
        manager.disconnect(websocket)


if __name__ == "__main__":
    import uvicorn
    import socket

    port = 8000
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.bind(('0.0.0.0', port))
        sock.close()
    except OSError:
        print(f"Port {port} already in use. Kill existing process or use different port.")
        sys.exit(1)

    uvicorn.run(app, host="0.0.0.0", port=port)
