from fastapi import APIRouter

from app.api.v1.endpoints import events, institutions

router = APIRouter()
router.include_router(events.router)
router.include_router(institutions.router)