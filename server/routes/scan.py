"""Scan and check endpoints."""

import asyncio

from fastapi import APIRouter

from ..models import ScanRequest, CheckRequest, KiwiResponse, KiwiError
from ..ws import manager

router = APIRouter(prefix="/api", tags=["scan"])


def _get_mcp():
    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).parent.parent.parent))
    import mcp_server
    return mcp_server


@router.post("/scan", response_model=KiwiResponse)
async def scan_endpoint(req: ScanRequest):
    mcp = _get_mcp()
    await manager.broadcast("scan.start", {"path": req.path})

    result = await asyncio.to_thread(
        mcp._handle_scan, req.model_dump(exclude_none=True)
    )

    await manager.broadcast("scan.complete", {"path": req.path, "result_length": len(result)})
    return KiwiResponse(data=result)


@router.post("/check", response_model=KiwiResponse)
async def check_endpoint(req: CheckRequest):
    mcp = _get_mcp()
    result = await asyncio.to_thread(
        mcp._handle_check, req.model_dump(exclude_none=True)
    )

    if req.file:
        await manager.broadcast("check.result", {"file": req.file, "result": result[:200]})

    return KiwiResponse(data=result)