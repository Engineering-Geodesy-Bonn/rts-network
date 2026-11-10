import math

import numpy as np
from fastapi import APIRouter, Depends, Query
from fastapi.responses import PlainTextResponse

from rtsapi import models as m
from rtsapi import repo
from rtsapi.core import Core
from rtsapi.exports import job_csv, job_trajectory
from rtsapi.routers import get_core

router = APIRouter(tags=["Jobs"])

MAX_POINTS_LIMIT = 200_000


@router.get("/jobs", response_model=m.JobPage, summary="List jobs, newest first (paginated).")
def list_jobs(
    session_id: str | None = None,
    rts_id: str | None = None,
    status: list[m.JobStatus] = Query(default=[]),
    type: list[m.JobType] = Query(default=[]),
    with_measurements: bool = False,
    before: float | None = Query(default=None, description="created_at of the last job of the previous page"),
    limit: int = Query(default=50, ge=1, le=500),
    core: Core = Depends(get_core),
) -> m.JobPage:
    return repo.list_jobs(core.db, session_id, rts_id, status, type, with_measurements, before, limit)


@router.post("/jobs", response_model=m.Job, summary="Queue a job for an RTS.")
def create_job(data: m.JobCreate, core: Core = Depends(get_core)) -> m.Job:
    return core.jobs.create(data)


@router.get("/jobs/{job_id}", response_model=m.Job)
def get_job(job_id: str, core: Core = Depends(get_core)) -> m.Job:
    return repo.get_job(core.db, job_id)


@router.patch("/jobs/{job_id}", response_model=m.Job, summary="Annotate a job.")
def update_job(job_id: str, data: m.JobUpdate, core: Core = Depends(get_core)) -> m.Job:
    job = repo.update_job(core.db, job_id, data)
    core.hub.publish_threadsafe({"type": "job", "job": job})
    return job


@router.post("/jobs/{job_id}/stop", response_model=m.Job, summary="Stop a running job or cancel a pending one.")
def stop_job(job_id: str, core: Core = Depends(get_core)) -> m.Job:
    return core.jobs.stop(job_id)


@router.delete("/jobs/{job_id}", status_code=204, summary="Delete a finished job and its measurements.")
def delete_job(job_id: str, core: Core = Depends(get_core)) -> None:
    core.delete_job(job_id)


@router.get(
    "/jobs/{job_id}/measurements",
    response_model=m.MeasurementSeries,
    summary="Measurements of a job, thinned out to at most max_points.",
)
def get_measurements(
    job_id: str,
    from_seq: int | None = None,
    to_seq: int | None = None,
    max_points: int = Query(default=20_000, ge=10, le=MAX_POINTS_LIMIT),
    core: Core = Depends(get_core),
) -> m.MeasurementSeries:
    row = repo.get_job_row(core.db, job_id)
    rts = repo.get_rts(core.db, row["rts_id"])
    total, _, last_seq = repo.count_measurements(core.db, row["no"], from_seq, to_seq)
    stride = max(1, math.ceil(total / max_points))
    data = repo.read_measurements(core.db, row["no"], from_seq, to_seq, stride)
    if stride > 1 and last_seq is not None and (len(data) == 0 or data.seq[-1] != last_seq):
        tail = repo.read_measurements(core.db, row["no"], last_seq, last_seq)
        data = repo.MeasurementArrays(**{k: np.concatenate([getattr(data, k), getattr(tail, k)]) for k in data.__dataclass_fields__})

    sin_v = np.sin(data.v)
    x = rts.station_x + data.d * sin_v * np.sin(data.hz + rts.orientation)
    y = rts.station_y + data.d * sin_v * np.cos(data.hz + rts.orientation)
    z = rts.station_z + data.d * np.cos(data.v)
    return m.MeasurementSeries(
        job_id=job_id,
        rts_id=rts.id,
        total=total,
        stride=stride,
        seq=data.seq.tolist(),
        t=data.t.tolist(),
        ts=data.ts.tolist(),
        d=data.d.tolist(),
        hz=data.hz.tolist(),
        v=data.v.tolist(),
        x=x.tolist(),
        y=y.tolist(),
        z=z.tolist(),
        ok=((data.grc == 0) & (data.rrc == 0)).tolist(),
    )


def _download(filename: str, content: str, media_type: str = "text/csv") -> PlainTextResponse:
    return PlainTextResponse(
        content=content,
        media_type=media_type,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/jobs/{job_id}/csv", response_class=PlainTextResponse, summary="Measurements as CSV (v1 column layout).")
def download_csv(job_id: str, corrected: bool = True, core: Core = Depends(get_core)) -> PlainTextResponse:
    job = repo.get_job(core.db, job_id)
    filename, content = job_csv(core.db, job, repo.get_rts(core.db, job.rts_id), corrected)
    return _download(filename, content)


@router.get("/jobs/{job_id}/trajectory", response_class=PlainTextResponse, summary="Corrected trajectory (trajectopy format).")
def download_trajectory(job_id: str, core: Core = Depends(get_core)) -> PlainTextResponse:
    job = repo.get_job(core.db, job_id)
    filename, content = job_trajectory(core.db, job, repo.get_rts(core.db, job.rts_id))
    return _download(filename, content, "text/plain")
