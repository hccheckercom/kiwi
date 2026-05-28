"""Route aggregation for Kiwi API."""

from fastapi import APIRouter

from .scan import router as scan_router
from .knowledge import router as knowledge_router
from .fix import router as fix_router
from .dashboard import router as dashboard_router
from .tier import router as tier_router
from .health import router as health_router

api_router = APIRouter()
api_router.include_router(scan_router)
api_router.include_router(knowledge_router)
api_router.include_router(fix_router)
api_router.include_router(dashboard_router)
api_router.include_router(tier_router)
api_router.include_router(health_router)