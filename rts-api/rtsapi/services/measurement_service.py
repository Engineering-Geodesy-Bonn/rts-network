import logging
from datetime import datetime

from fastapi import Depends
from fastapi.responses import PlainTextResponse

from rtsapi.database.measurement_repository import MeasurementRepository
from rtsapi.database.rts_job_repository import RTSJobRepository
from rtsapi.database.rts_repository import RTSRepository
from rtsapi.dtos import AddMeasurementRequest, MeasurementResponse, RTSResponse
from rtsapi.exceptions import (NoMeasurementsAvailableException,
                               RTSNotFoundException)
from rtsapi.mappers import MeasurementMapper
from rtsapi.rts_observations import (RTSObservations, RTSStation,
                                     RTSVarianceConfig)

logger = logging.getLogger("root")


class MeasurementService:
    def __init__(
        self,
        measurement_repository: MeasurementRepository = Depends(MeasurementRepository),
        rts_job_repository: RTSJobRepository = Depends(RTSJobRepository),
        rts_repository: RTSRepository = Depends(RTSRepository),
    ) -> None:
        self.measurement_repository = measurement_repository
        self.rts_job_repository = rts_job_repository
        self.rts_repository = rts_repository

    def add_measurement(self, add_measurement_request: AddMeasurementRequest) -> MeasurementResponse:
        job = self.rts_job_repository.get_rts_job(add_measurement_request.rts_job_id)
        db_measurement = MeasurementMapper.to_db(job.rts_id, add_measurement_request)
        added_measurement = self.measurement_repository.add_measurement(db_measurement)
        return MeasurementMapper.to_dto(added_measurement)

    def add_measurement_from_ws(self, measurement_dict: dict) -> None:
        measurement = AddMeasurementRequest(**measurement_dict)
        self.add_measurement(measurement)

    def get_raw_measurements(self, job_id: int = None) -> list[MeasurementResponse]:
        rts_obs = self.get_rts_observations(job_id)
        return rts_obs.to_measurement_response()
    
    def get_latest_measurements(self) -> list[MeasurementResponse]:
        latest_measurements = self.measurement_repository.get_latest_measurements()
        return [MeasurementMapper.to_dto(m) for m in latest_measurements]
        
    def get_corrected_measurements(self, job_id: int) -> list[MeasurementResponse]:
        corrected_rts_obs = self.get_corrected_rts_observations(job_id)
        return corrected_rts_obs.to_measurement_response()

    def get_rts_observations(self, job_id: int) -> RTSObservations:
        job = self.rts_job_repository.get_rts_job(job_id)

        try:
            rts = self.rts_repository.get_rts(job.rts_id, deleted_ok=True)
        except RTSNotFoundException:
            rts = RTSResponse(id=0, device_id=0)

        rts_variance_config = RTSVarianceConfig(
            distance=rts.distance_std_dev**2, ppm=rts.distance_ppm, angle=rts.angle_std_dev**2
        )
        rts_station = RTSStation(
            x=rts.station_x, y=rts.station_y, z=rts.station_z, orientation=rts.orientation
        )
        measurements = [
            MeasurementMapper.to_dto(measurement)
            for measurement in self.measurement_repository.get_measurements(job_id)
        ]
        if not measurements:
            raise NoMeasurementsAvailableException(f"No measurements found for job ID {job_id}")

        return RTSObservations(measurements=measurements, variances=rts_variance_config, station=rts_station)

    def get_corrected_rts_observations(self, job_id: int) -> RTSObservations:
        job = self.rts_job_repository.get_rts_job(job_id)
        try:
            rts = self.rts_repository.get_rts(job.rts_id, deleted_ok=True)
        except RTSNotFoundException:
            rts = RTSResponse(id=0, device_id=0)

        rts_observations = self.get_rts_observations(job_id)
        rts_observations.sync_sensor_time(baudrate=rts.baudrate, external_delay=rts.external_delay)
        rts_observations.apply_intrinsic_delay(rts.internal_delay)
        return rts_observations

    def download_measurements(self, job_id: int, filename: str = None, raw: bool = False) -> PlainTextResponse:
        if not filename:
            job = self.rts_job_repository.get_rts_job(job_id)
            filename = (
                f"{job.rts_id}_{job_id}_{datetime.fromtimestamp(job.created_at).strftime('%Y_%m_%d_%H_%M_%S')}.csv"
            )

        measurements = self.get_raw_measurements(job_id=job_id) if raw else self.get_corrected_measurements(job_id)
        measurements_str = (
            "ref_time, ts_time, h_angle, v_angle, distance, num_chars, geocom_return_code, rpc_return_code\n"
        )
        measurements_str += "\n".join(
            [
                f"{m.controller_timestamp},{m.sensor_timestamp},{m.horizontal_angle},{m.vertical_angle},{m.distance},{m.response_length},{m.geocom_return_code},{m.rpc_return_code}"
                for m in measurements
            ]
        )
        return PlainTextResponse(
            content=measurements_str, headers={"Content-Disposition": f"attachment; filename={filename}"}
        )

    def download_trajectory(self, job_id: int) -> PlainTextResponse:
        job = self.rts_job_repository.get_rts_job(job_id)
        trajectory = self.get_corrected_rts_observations(job_id).export_to_trajectory()
        trajectory_name = (
            f"rts_{job.rts_id}_{job_id}_{datetime.fromtimestamp(job.created_at).strftime('%Y_%m_%d_%H_%M_%S')}"
        )
        trajectory.name = trajectory_name
        filename = f"{trajectory_name}.traj"

        return PlainTextResponse(
            content=trajectory.to_string(), headers={"Content-Disposition": f"attachment; filename={filename}"}
        )


