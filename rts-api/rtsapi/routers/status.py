from fastapi import APIRouter, Depends

from rtsapi import models as m
from rtsapi.core import Core
from rtsapi.routers import get_core

router = APIRouter(tags=["Status"])


@router.get(
    "/status",
    response_model=m.StatusBoard,
    summary="Health of the network (also pushed every 2 s over /events).",
)
async def get_status(session_id: str | None = None, core: Core = Depends(get_core)) -> m.StatusBoard:
    return await core.status_board(session_id)
