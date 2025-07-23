import logging
from fastapi import Depends

from rtsapi.database.measurement_repository import MeasurementRepository
from rtsapi.database.rts_job_repository import RTSJobRepository
from rtsapi.database.rts_repository import RTSRepository
from rtsapi import dtos
from rtsapi.mappers import RTSJobMapper

logger = logging.getLogger("root")


class RTSJobService:
    def __init__(
        self,
        rts_repository: RTSRepository = Depends(RTSRepository),
        rts_job_repository: RTSJobRepository = Depends(RTSJobRepository),
        measurement_repository: MeasurementRepository = Depends(MeasurementRepository),
    ) -> None:
        self.rts_repository = rts_repository
        self.rts_job_repository = rts_job_repository
        self.measurement_repository = measurement_repository

    def create_rts_job(self, create_rts_job_request: dtos.CreateRTSJobRequest) -> dtos.RTSJobResponse:
        self.rts_repository.get_rts(create_rts_job_request.rts_id)
        db_rts_job = RTSJobMapper.to_db(create_rts_job_request)
        created_rts_job = self.rts_job_repository.create_rts_job(db_rts_job)
        return RTSJobMapper.to_dto(created_rts_job)

    def get_rts_job(self, job_id: int) -> dtos.RTSJobResponse:
        db_rts_job = self.rts_job_repository.get_rts_job(job_id)
        return RTSJobMapper.to_dto(db_rts_job)

    def fetch_rts_job(self, client_ip: str, job_types: list[dtos.RTSJobType]) -> dtos.RTSJobResponse:
        db_rts_job = self.rts_job_repository.fetch_rts_job(client_ip, job_types)

        if db_rts_job is None:
            return None

        return RTSJobMapper.to_dto(db_rts_job)

    def get_rts_job_status(self, job_id: int) -> dtos.RTSJobStatusResponse:
        db_rts_job = self.rts_job_repository.get_rts_job(job_id)
        return dtos.RTSJobStatusResponse(job_status=dtos.RTSJobStatus(db_rts_job.status))

    def get_all_rts_jobs(self) -> list[dtos.RTSJobResponse]:
        db_rts_jobs = self.rts_job_repository.get_all_rts_jobs()
        return [RTSJobMapper.to_dto(rts_job) for rts_job in db_rts_jobs]

    def get_running_rts_jobs(self) -> list[dtos.RTSJobResponse]:
        db_rts_jobs = self.rts_job_repository.get_running_rts_jobs()
        return [RTSJobMapper.to_dto(rts_job) for rts_job in db_rts_jobs]

    def update_rts_job_status(self, job_id: int, status: dtos.RTSJobStatus) -> dtos.RTSJobResponse:
        db_rts_job = self.rts_job_repository.update_rts_job_status(job_id, status)
        return RTSJobMapper.to_dto(db_rts_job)

    def delete_rts_job(self, job_id: int) -> None:
        self.rts_job_repository.delete_rts_job(job_id)
