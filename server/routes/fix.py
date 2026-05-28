"""Fix and dismiss endpoints."""

import asyncio

from fastapi import APIRouter

from ..models import FixRequest, DismissRequest, TrendsRequest, KiwiResponse
from ..ws import manager

router = APIRouter(prefix="/api", tags=["fix"])


def _get_mcp():
    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).parent.parent.parent))
    import mcp_server
    return mcp_server


@router.post("/fix", response_model=KiwiResponse)
async def fix_endpoint(req: FixRequest):
    mcp = _get_mcp()
    result = await asyncio.to_thread(
        mcp._handle_fix, req.model_dump(exclude_none=True)
    )

    if req.apply and req.file:
        await manager.broadcast("fix.applied", {
            "file": req.file,
            "lesson_id": req.lesson_id,
        })

    return KiwiResponse(data=result)


@router.post("/dismiss", response_model=KiwiResponse)
async def dismiss_endpoint(req: DismissRequest):
    mcp = _get_mcp()
    result = await asyncio.to_thread(
        mcp._handle_dismiss, req.model_dump()
    )
    return KiwiResponse(data=result)


@router.post("/trends", response_model=KiwiResponse)
async def trends_endpoint(req: TrendsRequest):
    mcp = _get_mcp()
    result = await asyncio.to_thread(
        mcp._handle_trends, req.model_dump()
    )
    return KiwiResponse(data=result)