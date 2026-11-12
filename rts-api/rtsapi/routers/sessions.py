import re
import zipfile
from datetime import datetime
from tempfile import SpooledTemporaryFile

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse

from rtsapi import models as m
from rtsapi import repo
from rtsapi.core import Core
from rtsapi.errors import Conflict
from rtsapi.exports import job_exports
from rtsapi.routers import get_core

router = APIRouter(tags=["Sessions"])


@router.get("/sessions", response_model=list[m.Session], summary="List sessions with statistics.")
def list_sessions(core: Core = Depends(get_core)) -> list[m.Session]:
    return repo.list_sessions(core.db)


@router.post("/sessions", response_model=m.Session, summary="Create a session.")
def create_session(data: m.SessionCreate, core: Core = Depends(get_core)) -> m.Session:
    session = repo.create_session(core.db, data)
    core.hub.changed("session", session.id)
    return session


@router.get("/sessions/{session_id}", response_model=m.Session)
def get_session(session_id: str, core: Core = Depends(get_core)) -> m.Session:
    return repo.get_session(core.db, session_id)


@router.patch("/sessions/{session_id}", response_model=m.Session, summary="Rename, annotate or archive a session.")
def update_session(session_id: str, data: m.SessionUpdate, core: Core = Depends(get_core)) -> m.Session:
    session = repo.update_session(core.db, session_id, data)
    core.hub.changed("session", session_id)
    return session


@router.delete("/sessions/{session_id}", status_code=204, summary="Delete a session with all its RTS, jobs and measurements.")
def delete_session(session_id: str, core: Core = Depends(get_core)) -> None:
    active = [j for j in repo.active_jobs(core.db) if j.rts_id in {r.id for r in repo.list_rts(core.db, session_id, True)}]
    if active:
        raise Conflict(f"{len(active)} job(s) of this session are still active, stop them first")
    repo.delete_session(core.db, session_id)
    core.hub.changed("session", session_id)


def safe_name(name: str) -> str:
    return re.sub(r"[^A-Za-z0-9_.-]+", "_", name).strip("_") or "export"


@router.get("/sessions/{session_id}/export", summary="Download all measurements of a session as ZIP.")
def export_session(session_id: str, core: Core = Depends(get_core)) -> StreamingResponse:
    session = repo.get_session(core.db, session_id)
    rts_by_id = {r.id: r for r in repo.list_rts(core.db, session_id, include_deleted=True)}
    buffer = SpooledTemporaryFile(max_size=64 * 1024 * 1024)
    with zipfile.ZipFile(buffer, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        before, before_no = None, None
        while True:
            page = repo.list_jobs(
                core.db, session_id=session_id, with_measurements=True, before=before, before_no=before_no, limit=200
            )
            for job in page.items:
                if job.type not in m.MEASURING_JOB_TYPES:
                    continue
                rts = rts_by_id[job.rts_id]
                folder = safe_name(rts.name)
                for filename, content in job_exports(core.db, job, rts):
                    archive.writestr(f"{folder}/{filename}", content)
            if page.next_before is None:
                break
            before, before_no = page.next_before, page.next_before_no
    size = buffer.tell()
    buffer.seek(0)
    stamp = datetime.fromtimestamp(session.created_at).strftime("%Y-%m-%d")
    filename = f"{safe_name(session.name)}_{stamp}.zip"

    def chunks():
        try:
            while chunk := buffer.read(1024 * 1024):
                yield chunk
        finally:
            buffer.close()

    return StreamingResponse(
        chunks(),
        media_type="application/zip",
        headers={"Content-Disposition": f'attachment; filename="{filename}"', "Content-Length": str(size)},
    )
