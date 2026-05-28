"""Tier and upgrade endpoints."""

import asyncio

from fastapi import APIRouter

from ..models import UpgradeRequest, KiwiResponse

router = APIRouter(prefix="/api", tags=["tier"])


def _get_mcp():
    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).parent.parent.parent))
    import mcp_server
    return mcp_server


@router.get("/tier", response_model=KiwiResponse)
async def tier_endpoint():
    from core.tier_manager import get_tier_manager
    tm = get_tier_manager()
    return KiwiResponse(data=tm.get_status())


@router.post("/upgrade", response_model=KiwiResponse)
async def upgrade_endpoint(req: UpgradeRequest):
    from core.tier_manager import get_tier_manager
    tm = get_tier_manager()

    if req.license_key:
        success = tm.activate_license(req.license_key)
        if success:
            return KiwiResponse(data={"message": f"Upgraded to {req.tier}", "status": tm.get_status()})
        return KiwiResponse(status="error", data={"message": "Invalid license key"})

    return KiwiResponse(data={"message": "License key required for upgrade", "upgrade_url": "https://kiwi-ai.dev/pricing"})