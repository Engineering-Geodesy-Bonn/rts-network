from fastapi import APIRouter, Depends

from rtsapi import models as m
from rtsapi import repo
from rtsapi.core import Core
from rtsapi.errors import Conflict
from rtsapi.routers import get_core

router = APIRouter(tags=["RTS"])


@router.get("/rts", response_model=list[m.RTS], summary="List the RTS of a session.")
def list_rts(session_id: str | None = None, include_deleted: bool = False, core: Core = Depends(get_core)) -> list[m.RTS]:
    return repo.list_rts(core.db, session_id, include_deleted)


@router.post("/rts", response_model=m.RTS, summary="Add an RTS to a session.")
def create_rts(data: m.RTSCreate, core: Core = Depends(get_core)) -> m.RTS:
    rts = repo.create_rts(core.db, data)
    core.rts_changed(rts.id, rts.session_id)
    return rts


@router.get("/rts/{rts_id}", response_model=m.RTS)
def get_rts(rts_id: str, core: Core = Depends(get_core)) -> m.RTS:
    return repo.get_rts(core.db, rts_id)


@router.patch("/rts/{rts_id}", response_model=m.RTS, summary="Change the configuration of an RTS.")
def update_rts(rts_id: str, data: m.RTSUpdate, core: Core = Depends(get_core)) -> m.RTS:
    rts = repo.update_rts(core.db, rts_id, data)
    core.rts_changed(rts_id, rts.session_id)
    return rts


@router.delete("/rts/{rts_id}", status_code=204, summary="Remove an RTS (its measurements are kept).")
def delete_rts(rts_id: str, core: Core = Depends(get_core)) -> None:
    rts = repo.get_rts(core.db, rts_id, deleted_ok=False)
    if any(j.rts_id == rts_id for j in repo.active_jobs(core.db)):
        raise Conflict("The RTS has active jobs, stop them first")
    repo.delete_rts(core.db, rts_id)
    core.rts_changed(rts_id, rts.session_id)
