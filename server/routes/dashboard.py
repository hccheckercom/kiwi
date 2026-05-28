"""Dashboard and status endpoints."""

import asyncio

from fastapi import APIRouter

from ..models import KiwiResponse

router = APIRouter(prefix="/api", tags=["dashboard"])


def _get_mcp():
    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).parent.parent.parent))
    import mcp_server
    return mcp_server


@router.get("/dashboard", response_model=KiwiResponse)
async def dashboard_endpoint(mode: str = "compact"):
    mcp = _get_mcp()
    result = await asyncio.to_thread(
        mcp._handle_dashboard, {"mode": mode}
    )
    return KiwiResponse(data=result)


@router.get("/status", response_model=KiwiResponse)
async def status_endpoint():
    from core.tier_manager import get_tier_manager
    from core.plugin_registry import discover_plugins

    tm = get_tier_manager()
    tier_info = tm.get_status()
    plugins = discover_plugins()

    return KiwiResponse(data={
        "version": "1.0.0",
        "tier": tier_info,
        "plugins_loaded": len(plugins),
        "plugins": [getattr(p, "name", str(p)) for p in plugins],
    })