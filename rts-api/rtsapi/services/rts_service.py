from fastapi import Depends

from rtsapi.database.device_repository import DeviceRepository
from rtsapi.database.measurement_repository import MeasurementRepository
from rtsapi.database.rts_job_repository import RTSJobRepository
from rtsapi.database.rts_repository import RTSRepository
from rtsapi.database.tracking_settings_repository import TrackingSettingsRepository
from rtsapi import dtos
from rtsapi.mappers import RTSMapper, TrackingSettingsMapper


class RTSService:
    def __init__(
        self,
        rts_repository: RTSRepository = Depends(RTSRepository),
        rts_job_repository: RTSJobRepository = Depends(RTSJobRepository),
        measurement_repository: MeasurementRepository = Depends(MeasurementRepository),
        tracking_settings_repository: TrackingSettingsRepository = Depends(TrackingSettingsRepository),
        device_repository: DeviceRepository = Depends(DeviceRepository),
    ) -> None:
        self.rts_repository = rts_repository
        self.rts_job_repository = rts_job_repository
        self.tracking_settings_repository = tracking_settings_repository
        self.measurement_repository = measurement_repository
        self.device_repository = device_repository

    def get_rts(self, rts_id: int) -> dtos.RTSResponse:
        db_rts = self.rts_repository.get_rts(rts_id)
        return RTSMapper.to_dto(db_rts)

    def get_all_rts(self) -> list[dtos.RTSResponse]:
        return [RTSMapper.to_dto(rts) for rts in self.rts_repository.get_all_rts()]

    def create_rts(self, create_rts_request: dtos.CreateRTSRequest) -> dtos.RTSResponse:
        self.device_repository.get_device(create_rts_request.device_id)
        db_rts = RTSMapper.to_db(create_rts_request)
        created_rts = self.rts_repository.create_rts(db_rts)
        tracking_settings = TrackingSettingsMapper.create_to_db(
            dtos.CreateTrackingSettingsRequest(rts_id=created_rts.id)
        )
        self.tracking_settings_repository.create_tracking_settings(tracking_settings)
        return dtos.RTSResponse.model_validate(created_rts)

    def update_rts(self, rts_id: int, update_rts_request: dtos.UpdateRTSRequest) -> dtos.RTSResponse:
        return self.rts_repository.update_rts(rts_id, update_rts_request)

    def delete_rts(self, rts_id: int) -> None:
        self.rts_repository.delete_rts(rts_id)

    def get_tracking_settings(self, rts_id: int) -> dtos.TrackingSettingsResponse:
        db_settings = self.tracking_settings_repository.get_tracking_settings(rts_id)
        return TrackingSettingsMapper.to_dto(db_settings)

    def get_tracking_settings(self, rts_id: int) -> dtos.TrackingSettingsResponse:
        db_settings = self.tracking_settings_repository.get_tracking_settings(rts_id)
        return TrackingSettingsMapper.to_dto(db_settings)

    def update_tracking_settings(
        self, rts_id: int, update_tracking_settings_request: dtos.UpdateTrackingSettingsRequest
    ) -> dtos.TrackingSettingsResponse:
        db_settings = TrackingSettingsMapper.update_to_db(update_tracking_settings_request)
        updated_settings = self.tracking_settings_repository.update_tracking_settings(rts_id, db_settings)
        return TrackingSettingsMapper.to_dto(updated_settings)

    def get_rts_status(self, rts_id: int) -> dtos.RTSStatus:
        self.get_rts(rts_id)
        rts_job = self.rts_job_repository.get_running_rts_job(rts_id)
        rts_job_id = rts_job.id if rts_job is not None else None
        rts_busy = rts_job is not None
        last_measurement = self.measurement_repository.get_last_measurement_of_rts(rts_id)
        last_measurement_response = (
            dtos.MeasurementResponse.model_validate(last_measurement) if last_measurement is not None else None
        )
        num_measurements = (
            self.measurement_repository.get_number_of_measurements_for_job(rts_job_id) if rts_job_id else 0
        )
        datarate = self.measurement_repository.get_datarate_for_job(rts_job_id) if rts_job_id else 0.0
        return dtos.RTSStatus(
            job_id=rts_job_id,
            busy=rts_busy,
            last_measurement=last_measurement_response,
            num_measurements=num_measurements,
            datarate=datarate,
        )
