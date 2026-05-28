"""Health check endpoint."""

from fastapi import APIRouter

from ..ws import manager

router = APIRouter(tags=["health"])


@router.get("/health")
async def health():
    return {
        "status": "ok",
        "version": "1.0.0",
        "websocket_connections": manager.active_count,
    }