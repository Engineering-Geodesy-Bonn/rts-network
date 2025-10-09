from fastapi import Depends
from sqlalchemy.orm import Session

from rtsapi.database.models import Measurement
from rtsapi.dependencies import get_db


class MeasurementRepository:

    def __init__(self, db: Session = Depends(get_db)):
        self.db = db

    def add_measurement(self, measurement: Measurement) -> Measurement:
        self.db.add(measurement)
        self.db.commit()
        self.db.refresh(measurement)
        return measurement

    def get_measurements(self, job_id: int = None) -> list[Measurement]:
        query = self.db.query(Measurement)
        if job_id:
            query = query.filter(Measurement.rts_job_id == job_id)

        query = query.order_by(Measurement.controller_timestamp.asc())
        return query.all()

    def delete_measurements(self, job_id: int) -> None:
        self.db.query(Measurement).filter(Measurement.rts_job_id == job_id).delete()
        self.db.commit()

    def get_latest_measurement(self) -> Measurement:
        return self.db.query(Measurement).order_by(Measurement.controller_timestamp.desc()).first()

    def get_last_measurement_of_rts(self, rts_id: int) -> Measurement:
        return (
            self.db.query(Measurement)
            .filter(Measurement.rts_id == rts_id)
            .order_by(Measurement.controller_timestamp.desc())
            .first()
        )
