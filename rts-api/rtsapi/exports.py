import json
import logging
import re
from datetime import datetime

from rtsapi import models as m
from rtsapi import repo
from rtsapi.db import Database
from rtsapi.errors import NotFound
from rtsapi.processing import observations

logger = logging.getLogger(__name__)


def base_name(job: m.Job, rts: m.RTS) -> str:
    stamp = datetime.fromtimestamp(job.started_at or job.created_at).strftime("%Y-%m-%d_%H-%M-%S")
    name = re.sub(r"[^A-Za-z0-9_.-]+", "_", rts.name).strip("_") or "rts"
    return f"{name}_{stamp}_{job.id[:8]}"


def job_csv(db: Database, job: m.Job, rts: m.RTS, corrected: bool) -> tuple[str, str]:
    data = repo.read_measurements(db, repo.get_job_row(db, job.id)["no"])
    obs = observations(data, rts, corrected=corrected, job_id=job.id)
    suffix = "corrected" if corrected else "raw"
    return f"{base_name(job, rts)}_{suffix}.csv", obs.to_csv()


def job_trajectory(db: Database, job: m.Job, rts: m.RTS) -> tuple[str, str]:
    data = repo.read_measurements(db, repo.get_job_row(db, job.id)["no"])
    obs = observations(data, rts, corrected=True, job_id=job.id)
    name = base_name(job, rts)
    return f"{name}.traj", obs.to_trajectory(name).to_string()


def job_settings(job: m.Job, rts: m.RTS) -> tuple[str, str]:
    """The job and the settings it was run with. Coordinates in the CSV files are computed with
    the current station settings (so that a corrected station position applies)."""
    info = {
        "job": job.model_dump(mode="json", exclude={"settings", "payload"}),
        "station": rts.name,
        "settings_used": job.settings.model_dump(mode="json") if job.settings else None,
        "settings_note": None if job.settings else "Not recorded: the job ran before the API recorded job settings",
        "current_station_settings": rts.model_dump(mode="json", include=set(m.JobSettings.model_fields)),
    }
    return f"{base_name(job, rts)}_settings.json", json.dumps(info, indent=2)


def job_exports(db: Database, job: m.Job, rts: m.RTS) -> list[tuple[str, str]]:
    files = [job_settings(job, rts)]
    for corrected in (False, True):
        try:
            files.append(job_csv(db, job, rts, corrected))
        except NotFound:
            return files
        except Exception as e:
            logger.exception("Export of job %s failed", job.id)
            files.append((f"{base_name(job, rts)}_ERROR.txt", f"Export failed: {e!r}"))
            return files
    try:
        files.append(job_trajectory(db, job, rts))
    except Exception as e:
        logger.exception("Trajectory export of job %s failed", job.id)
        files.append((f"{base_name(job, rts)}_trajectory_ERROR.txt", f"Export failed: {e!r}"))
    return files
