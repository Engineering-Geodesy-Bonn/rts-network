from uuid import UUID

from fastapi import Depends
from sqlalchemy import func
from sqlalchemy.orm import Session

from rtsapi.database.models import Measurement
from rtsapi.database.rts_job_repository import RTSJobRepository
from rtsapi.dependencies import get_db


class MeasurementRepository:

    def __init__(
        self,
        db: Session = Depends(get_db),
        rts_job_repository: RTSJobRepository = Depends(RTSJobRepository),
    ):
        self.db = db
        self.rts_job_repository = rts_job_repository

    def add_measurement(self, measurement: Measurement) -> Measurement:
        self.db.add(measurement)
        self.db.commit()
        self.db.refresh(measurement)
        return measurement

    def get_latest_measurements(self) -> list[Measurement]:
        """Get the latest measurements for all running jobs"""
        running_jobs = self.rts_job_repository.get_running_rts_jobs()
        running_job_ids = [job.id for job in running_jobs]

        subquery = (
            self.db.query(
                Measurement.rts_job_id,
                func.max(Measurement.controller_timestamp).label("max_timestamp"),
            )
            .filter(Measurement.rts_job_id.in_(running_job_ids))
            .group_by(Measurement.rts_job_id)
            .subquery()
        )

        latest_measurements = (
            self.db.query(Measurement)
            .join(
                subquery,
                (Measurement.rts_job_id == subquery.c.rts_job_id)
                & (Measurement.controller_timestamp == subquery.c.max_timestamp),
            )
            .all()
        )

        return latest_measurements

    def get_measurements(
        self, job_id: UUID = None, since_timestamp: float = None
    ) -> list[Measurement]:
        query = self.db.query(Measurement)
        if job_id is not None:
            query = query.filter(Measurement.rts_job_id == job_id)
        if since_timestamp is not None:
            query = query.filter(Measurement.controller_timestamp > since_timestamp)

        query = query.order_by(Measurement.controller_timestamp.asc())
        return query.all()

    def delete_measurements(self, job_id: UUID) -> None:
        self.db.query(Measurement).filter(Measurement.rts_job_id == job_id).delete()
        self.db.commit()

    def get_latest_measurement(self) -> Measurement:
        return (
            self.db.query(Measurement)
            .order_by(Measurement.controller_timestamp.desc())
            .first()
        )

    def get_last_measurement_of_rts(self, rts_id: UUID) -> Measurement:
        return (
            self.db.query(Measurement)
            .filter(Measurement.rts_id == rts_id)
            .order_by(Measurement.controller_timestamp.desc())
            .first()
        )

    def get_number_of_measurements_for_job(self, job_id: UUID) -> int:
        return (
            self.db.query(Measurement).filter(Measurement.rts_job_id == job_id).count()
        )

    def get_datarate_for_job(self, job_id: UUID) -> float:
        measurements = (
            self.db.query(Measurement)
            .filter(Measurement.rts_job_id == job_id)
            .order_by(Measurement.controller_timestamp.asc())
            .limit(100)
            .all()
        )
        if len(measurements) < 2:
            return 0.0

        time_span = (
            measurements[-1].controller_timestamp - measurements[0].controller_timestamp
        )
        if time_span <= 0:
            return 0.0

        return len(measurements) / time_span
