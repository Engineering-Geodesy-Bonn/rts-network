import time
from fastapi import Depends
from sqlalchemy.orm import Query, Session

from rtsapi.database.models import RTS, Device, RTSJob
from rtsapi.dependencies import get_db
from rtsapi.dtos import RTSJobStatus, RTSJobType
from rtsapi.exceptions import RTSJobNotFoundException, RTSJobStatusChangeException


class RTSJobRepository:

    def __init__(self, db: Session = Depends(get_db)):
        self.db = db

    def create_rts_job(self, rts_job: RTSJob) -> RTSJob:
        self.db.add(rts_job)
        self.db.commit()
        self.db.refresh(rts_job)
        return rts_job

    def get_static_rts_job(self, rts_id: int) -> RTSJob:
        rts_job = (
            self.db.query(RTSJob)
            .filter(RTSJob.rts_id == rts_id, RTSJob.job_type == RTSJobType.STATIC_MEASUREMENT.value)
            .first()
        )

        if rts_job is None:
            new_job = RTSJob(
                rts_id=rts_id,
                job_type=RTSJobType.STATIC_MEASUREMENT.value,
                status=RTSJobStatus.FINISHED.value,
                created_at=time.time(),
                payload={},
            )
            rts_job = self.create_rts_job(new_job)

        return rts_job

    def get_rts_job(self, job_id: int) -> RTSJob:
        rts_job = self.db.query(RTSJob).filter(RTSJob.id == job_id).first()

        if rts_job is None:
            raise RTSJobNotFoundException(job_id)

        return rts_job

    def fetch_rts_job(self, client_ip: str, job_types: list[RTSJobType]) -> RTSJob:
        job_types = job_types or []
        query = self.filter_by_device_ip_query(client_ip)

        if job_types:
            query = query.filter(RTSJob.job_type.in_([job_type.value for job_type in job_types]))

        query = query.filter(RTSJob.status == RTSJobStatus.PENDING.value)
        query = query.order_by(RTSJob.created_at.asc())

        return query.first()

    def get_all_rts_jobs(self) -> list[RTSJob]:
        return self.db.query(RTSJob).order_by(RTSJob.created_at.desc()).all()

    def update_rts_job_status(self, job_id: int, status: RTSJobStatus) -> RTSJob:
        job = self.db.query(RTSJob).filter(RTSJob.id == job_id).first()

        if job is None:
            raise RTSJobNotFoundException(job_id)

        if not self.verify_status_change(RTSJobStatus(job.status), status):
            raise RTSJobStatusChangeException(job_id, RTSJobStatus(job.status), status)

        job.status = status.value
        self.db.commit()
        self.db.refresh(job)
        return job

    def delete_rts_job(self, job_id: int) -> None:
        job = self.db.query(RTSJob).get(job_id)

        if job:
            self.db.delete(job)
            self.db.commit()
        else:
            print(f"No RTSJob found with id {job_id}")

    def get_running_rts_job(self, rts_id: int) -> RTSJob:
        return (
            self.db.query(RTSJob)
            .filter(RTSJob.rts_id == rts_id)
            .filter(RTSJob.status == RTSJobStatus.RUNNING.value)
            .first()
        )

    def get_running_rts_jobs(self) -> list[RTSJob]:
        return self.db.query(RTSJob).filter(RTSJob.status == RTSJobStatus.RUNNING.value).all()

    def verify_status_change(self, old_status: RTSJobStatus, new_status: RTSJobStatus) -> bool:
        order = [RTSJobStatus.PENDING, RTSJobStatus.RUNNING, RTSJobStatus.FINISHED, RTSJobStatus.FAILED]
        return order.index(old_status) < order.index(new_status)

    def filter_by_device_ip_query(self, device_ip: str) -> Query[RTSJob]:
        return (
            self.db.query(RTSJob)
            .join(RTS, RTSJob.rts_id == RTS.id)
            .join(Device, RTS.device_id == Device.id)
            .filter(Device.ip == device_ip)
        )
