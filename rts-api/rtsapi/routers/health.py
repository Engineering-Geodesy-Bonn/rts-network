from fastapi import APIRouter, Depends

from rtsapi import models as m
from rtsapi.core import Core
from rtsapi.routers import get_core

router = APIRouter(tags=["Health"])


@router.get("/health", response_model=m.Health, summary="Problems of a session (also pushed every 2 s over /events).")
async def get_health(session_id: str | None = None, core: Core = Depends(get_core)) -> m.Health:
    return await core.health(session_id)
