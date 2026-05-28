"""FastAPI app factory for Kiwi server."""

import sys
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware

from .auth import TokenAuthMiddleware
from .routes import api_router
from .ws import manager


@asynccontextmanager
async def lifespan(app: FastAPI):
    sys.path.insert(0, str(Path(__file__).parent.parent))
    yield


def create_app(enable_watcher: bool = True, project_path: str = ".") -> FastAPI:
    app = FastAPI(
        title="Kiwi AI",
        description="Code quality scanner API",
        version="1.0.0",
        lifespan=lifespan,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:*", "http://127.0.0.1:*"],
        allow_origin_regex=r"http://(localhost|127\.0\.0\.1)(:\d+)?",
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.add_middleware(TokenAuthMiddleware)

    app.include_router(api_router)

    @app.websocket("/ws")
    async def websocket_endpoint(ws: WebSocket):
        await manager.connect(ws)
        try:
            while True:
                data = await ws.receive_json()
                cmd = data.get("command")
                if cmd == "subscribe":
                    manager.subscribe(ws, data.get("channels", []))
                elif cmd == "unsubscribe":
                    manager.unsubscribe(ws, data.get("channels", []))
        except WebSocketDisconnect:
            manager.disconnect(ws)

    if enable_watcher:
        app.state.project_path = project_path

    return app