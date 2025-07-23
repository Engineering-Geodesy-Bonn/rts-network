from datetime import datetime

from fastapi import Depends
from fastapi.responses import PlainTextResponse
import numpy as np

from rtsapi.database.measurement_repository import MeasurementRepository
from rtsapi.database.rts_job_repository import RTSJobRepository
from rtsapi.database.rts_repository import RTSRepository
from rtsapi.dtos import AddMeasurementRequest, AlignmentResponse, MeasurementResponse, RTSResponse
from rtsapi.exceptions import RTSNotFoundException
from rtsapi.fitting.rts_observations import RTSObservations, RTSStation, RTSVarianceConfig
from rtsapi.fitting.sphere_fit import SphereFit
from rtsapi.mappers import MeasurementMapper
import trajectopy as tpy


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

    def add_static_measurement(self, add_measurement_request: AddMeasurementRequest) -> MeasurementResponse:
        add_measurement_job = self.rts_job_repository.get_rts_job(add_measurement_request.rts_job_id)
        job = self.rts_job_repository.get_static_rts_job(add_measurement_job.rts_id)
        add_measurement_request.rts_job_id = job.id
        db_measurement = MeasurementMapper.to_db(job.rts_id, add_measurement_request)
        added_measurement = self.measurement_repository.add_measurement(db_measurement)
        return MeasurementMapper.to_dto(added_measurement)

    def add_measurement(self, add_measurement_request: AddMeasurementRequest) -> MeasurementResponse:
        job = self.rts_job_repository.get_rts_job(add_measurement_request.rts_job_id)
        db_measurement = MeasurementMapper.to_db(job.rts_id, add_measurement_request)
        added_measurement = self.measurement_repository.add_measurement(db_measurement)
        return MeasurementMapper.to_dto(added_measurement)

    def get_raw_measurements(self, job_id: int = None) -> list[MeasurementResponse]:
        rts_obs = self.get_rts_observations(job_id)
        return rts_obs.to_measurement_response()

    def get_corrected_measurements(self, job_id: int) -> list[MeasurementResponse]:
        corrected_rts_obs = self.get_corrected_rts_observations(job_id)
        return corrected_rts_obs.to_measurement_response()

    def get_rts_observations(self, job_id: int) -> RTSObservations:
        job = self.rts_job_repository.get_rts_job(job_id)

        try:
            rts = self.rts_repository.get_rts(job.rts_id)
        except RTSNotFoundException:
            rts = RTSResponse(id=0, device_id=0)

        rts_variance_config = RTSVarianceConfig(
            distance=rts.distance_std_dev**2, ppm=rts.distance_ppm, angle=rts.angle_std_dev**2
        )
        rts_station = RTSStation(
            x=rts.station_x, y=rts.station_y, z=rts.station_z, epsg=rts.station_epsg, orientation=rts.orientation
        )
        measurements = [
            MeasurementMapper.to_dto(measurement)
            for measurement in self.measurement_repository.get_measurements(job_id)
        ]
        return RTSObservations(measurements=measurements, variances=rts_variance_config, station=rts_station)

    def get_corrected_rts_observations(self, job_id: int) -> RTSObservations:
        job = self.rts_job_repository.get_rts_job(job_id)
        rts = self.rts_repository.get_rts(job.rts_id)

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

    def get_internal_delay(self, job_id: int) -> float:
        rts_observations = self.get_rts_observations(job_id)
        job = self.rts_job_repository.get_rts_job(job_id)
        sphere_fit = SphereFit(rts_observations)
        print(f"Time Shift: {sphere_fit.estimated_parameters.time_shift * 1000:.3f} ms")
        self.rts_repository.update_internal_delay(job.rts_id, sphere_fit.estimated_parameters.time_shift)
        return sphere_fit.estimated_parameters.time_shift

    def get_alignment(self, reference_job_id: int, job_id: int) -> AlignmentResponse:
        """
        Compute alignment in local coordinate system and then shift back to reference coordinate system
        """
        reference_job = self.rts_job_repository.get_rts_job(reference_job_id)
        reference_station = self.rts_repository.get_station(reference_job.rts_id)
        self.rts_repository.set_station(
            rts_id=reference_job.rts_id, station_x=0, station_y=0, station_z=0, orientation=0
        )

        eval_job = self.rts_job_repository.get_rts_job(job_id)
        self.rts_repository.set_station(rts_id=eval_job.rts_id, station_x=0, station_y=0, station_z=0, orientation=0)

        alignment_settings = tpy.AlignmentSettings(
            estimation_settings=tpy.AlignmentEstimationSettings(rot_x=False, rot_y=False, time_shift=True),
            stochastics=tpy.AlignmentStochastics(variance_estimation=True),
        )

        # reference job is the corrected one
        traj_ref = self.get_corrected_rts_observations(reference_job_id).export_to_trajectory()

        # eval job is the corrected one except for the time shift
        eval_obs = self.get_rts_observations(job_id)
        eval_job_rts = self.rts_repository.get_rts(eval_job.rts_id)
        eval_obs.sync_sensor_time(baudrate=eval_job_rts.baudrate, external_delay=0.0)
        eval_obs.apply_intrinsic_delay(eval_job_rts.internal_delay)
        traj_eval = eval_obs.export_to_trajectory()

        alignment_result = tpy.estimate_alignment(
            traj_from=traj_eval, traj_to=traj_ref, alignment_settings=alignment_settings
        )

        alignment_response = AlignmentResponse(
            reference_job_id=reference_job_id,
            job_id=job_id,
            station_x=alignment_result.position_parameters.sim_trans_x.value,
            station_y=alignment_result.position_parameters.sim_trans_y.value,
            station_z=alignment_result.position_parameters.sim_trans_z.value,
            orientation=alignment_result.position_parameters.sim_rot_z.value,
            time_shift=alignment_result.position_parameters.time_shift.value,
            station_x_std=np.sqrt(alignment_result.position_parameters.sim_trans_x.variance),
            station_y_std=np.sqrt(alignment_result.position_parameters.sim_trans_y.variance),
            station_z_std=np.sqrt(alignment_result.position_parameters.sim_trans_z.variance),
            orientation_std=np.sqrt(alignment_result.position_parameters.sim_rot_z.variance),
            time_shift_std=np.sqrt(alignment_result.position_parameters.time_shift.variance),
        )

        self.rts_repository.add_to_external_delay(eval_job.rts_id, alignment_response.time_shift)
        self.rts_repository.move_station(
            eval_job.rts_id,
            reference_station.get("station_x", 0.0) + alignment_response.station_x,
            reference_station.get("station_y", 0.0) + alignment_response.station_y,
            reference_station.get("station_z", 0.0) + alignment_response.station_z,
            reference_station.get("orientation", 0.0) + alignment_response.orientation,
        )

        self.rts_repository.set_station(
            reference_job.rts_id,
            reference_station.get("station_x", 0.0),
            reference_station.get("station_y", 0.0),
            reference_station.get("station_z", 0.0),
            reference_station.get("station_epsg", 0),
            reference_station.get("orientation", 0.0),
        )

        return alignment_response
