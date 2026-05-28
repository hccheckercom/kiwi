"""Knowledge base endpoints: lessons, context, stats, query."""

import asyncio

from fastapi import APIRouter

from ..models import ContextRequest, QueryRequest, KiwiResponse

router = APIRouter(prefix="/api", tags=["knowledge"])


def _get_mcp():
    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).parent.parent.parent))
    import mcp_server
    return mcp_server


@router.post("/context", response_model=KiwiResponse)
async def context_endpoint(req: ContextRequest):
    mcp = _get_mcp()
    result = await asyncio.to_thread(
        mcp._handle_context, req.model_dump(exclude_none=True)
    )
    return KiwiResponse(data=result)


@router.get("/lessons", response_model=KiwiResponse)
async def query_lessons(
    keyword: str = "",
    category: str = None,
    severity: str = None,
    platform: str = None,
    limit: int = 10,
):
    mcp = _get_mcp()
    args = {"keyword": keyword, "limit": limit}
    if category:
        args["category"] = category
    if severity:
        args["severity"] = severity
    if platform:
        args["platform"] = platform

    result = await asyncio.to_thread(mcp._handle_query, args)
    return KiwiResponse(data=result)


@router.get("/lessons/{lesson_id}", response_model=KiwiResponse)
async def get_lesson(lesson_id: str):
    mcp = _get_mcp()
    result = await asyncio.to_thread(mcp._handle_lesson, {"id": lesson_id})
    return KiwiResponse(data=result)


@router.get("/stats", response_model=KiwiResponse)
async def stats_endpoint():
    mcp = _get_mcp()
    result = await asyncio.to_thread(mcp._handle_stats, {})
    return KiwiResponse(data=result)