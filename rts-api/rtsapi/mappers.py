import time

from rtsapi.database.models import RTS, Device, Measurement, RTSJob, TrackingSettings
from rtsapi import dtos


class MeasurementMapper:
    @staticmethod
    def to_db(rts_id: int, measurement: dtos.AddMeasurementRequest) -> Measurement:
        return Measurement(
            rts_id=rts_id,
            rts_job_id=measurement.rts_job_id,
            controller_timestamp=measurement.controller_timestamp,
            sensor_timestamp=measurement.sensor_timestamp,
            response_length=measurement.response_length,
            geocom_return_code=measurement.geocom_return_code,
            rpc_return_code=measurement.rpc_return_code,
            distance=measurement.distance,
            horizontal_angle=measurement.horizontal_angle,
            vertical_angle=measurement.vertical_angle,
        )

    @staticmethod
    def to_dto(measurement: Measurement) -> dtos.MeasurementResponse:
        return dtos.MeasurementResponse(
            id=measurement.id,
            rts_id=measurement.rts_id,
            rts_job_id=measurement.rts_job_id,
            controller_timestamp=measurement.controller_timestamp,
            sensor_timestamp=measurement.sensor_timestamp,
            response_length=measurement.response_length,
            geocom_return_code=measurement.geocom_return_code,
            rpc_return_code=measurement.rpc_return_code,
            distance=measurement.distance,
            horizontal_angle=measurement.horizontal_angle,
            vertical_angle=measurement.vertical_angle,
        )

    @staticmethod
    def to_measurement_dtos(measurements: list[Measurement]) -> list[dtos.MeasurementResponse]:
        return [MeasurementMapper.to_dto(measurement) for measurement in measurements]


class RTSMapper:
    @staticmethod
    def to_dto(rts: RTS) -> dtos.RTSResponse:
        return dtos.RTSResponse(
            id=rts.id,
            device_id=rts.device_id,
            name=rts.name,
            baudrate=rts.baudrate,
            port=rts.port,
            timeout=rts.timeout,
            parity=rts.parity,
            stopbits=rts.stopbits,
            bytesize=rts.bytesize,
            external_delay=rts.external_delay,
            internal_delay=rts.internal_delay,
            station_x=rts.station_x,
            station_y=rts.station_y,
            station_z=rts.station_z,
            orientation=rts.orientation,
            distance_std_dev=rts.distance_std_dev,
            angle_std_dev=rts.angle_std_dev,
            distance_ppm=rts.distance_ppm,
        )

    @staticmethod
    def to_db(rts: dtos.CreateRTSRequest) -> RTS:
        return RTS(
            device_id=rts.device_id,
            name=rts.name,
            baudrate=rts.baudrate,
            port=rts.port,
            timeout=rts.timeout,
            parity=rts.parity,
            stopbits=rts.stopbits,
            bytesize=rts.bytesize,
            external_delay=rts.external_delay,
            internal_delay=rts.internal_delay,
            station_x=rts.station_x,
            station_y=rts.station_y,
            station_z=rts.station_z,
            orientation=rts.orientation,
            distance_std_dev=rts.distance_std_dev,
            angle_std_dev=rts.angle_std_dev,
            distance_ppm=rts.distance_ppm,
            deleted=False,
        )


class RTSJobMapper:
    @staticmethod
    def to_dto(rts_job: RTSJob) -> dtos.RTSJobResponse:
        return dtos.RTSJobResponse(
            job_id=rts_job.id,
            rts_id=rts_job.rts_id,
            job_type=dtos.RTSJobType(rts_job.job_type),
            job_status=dtos.RTSJobStatus(rts_job.status),
            created_at=rts_job.created_at,
            payload=rts_job.payload,
        )

    @staticmethod
    def to_db(rts_job: dtos.CreateRTSJobRequest) -> RTSJob:
        return RTSJob(
            rts_id=rts_job.rts_id,
            job_type=rts_job.job_type.value,
            status=dtos.RTSJobStatus.PENDING.value,
            created_at=time.time(),
            payload=rts_job.payload,
        )


class TrackingSettingsMapper:
    @staticmethod
    def to_dto(tracking_settings: TrackingSettings) -> dtos.TrackingSettingsResponse:
        return dtos.TrackingSettingsResponse(
            tmc_measurement_mode=tracking_settings.tmc_measurement_mode,
            tmc_inclination_mode=tracking_settings.tmc_inclination_mode,
            edm_measurement_mode=tracking_settings.edm_measurement_mode,
            prism_type=tracking_settings.prism_type,
            fine_adjust_position_mode=tracking_settings.fine_adjust_position_mode,
            fine_adjust_horizontal_search_range=tracking_settings.fine_adjust_horizontal_search_range,
            fine_adjust_vertical_search_range=tracking_settings.fine_adjust_vertical_search_range,
            power_search_area_dcenterhz=tracking_settings.power_search_area_dcenterhz,
            power_search_area_dcenterv=tracking_settings.power_search_area_dcenterv,
            power_search_area_drangehz=tracking_settings.power_search_area_drangehz,
            power_search_area_drangev=tracking_settings.power_search_area_drangev,
            power_search_area_enabled=tracking_settings.power_search_area_enabled,
            power_search_min_range=tracking_settings.power_search_min_range,
            power_search_max_range=tracking_settings.power_search_max_range,
            power_search=tracking_settings.power_search,
            rts_id=tracking_settings.rts_id,
            id=tracking_settings.id,
        )

    @staticmethod
    def create_to_db(tracking_settings: dtos.CreateTrackingSettingsRequest) -> TrackingSettings:
        return TrackingSettings(
            tmc_measurement_mode=tracking_settings.tmc_measurement_mode,
            tmc_inclination_mode=tracking_settings.tmc_inclination_mode,
            edm_measurement_mode=tracking_settings.edm_measurement_mode,
            prism_type=tracking_settings.prism_type,
            fine_adjust_position_mode=tracking_settings.fine_adjust_position_mode,
            fine_adjust_horizontal_search_range=tracking_settings.fine_adjust_horizontal_search_range,
            fine_adjust_vertical_search_range=tracking_settings.fine_adjust_vertical_search_range,
            power_search_area_dcenterhz=tracking_settings.power_search_area_dcenterhz,
            power_search_area_dcenterv=tracking_settings.power_search_area_dcenterv,
            power_search_area_drangehz=tracking_settings.power_search_area_drangehz,
            power_search_area_drangev=tracking_settings.power_search_area_drangev,
            power_search_area_enabled=tracking_settings.power_search_area_enabled,
            power_search_min_range=tracking_settings.power_search_min_range,
            power_search_max_range=tracking_settings.power_search_max_range,
            power_search=tracking_settings.power_search,
            rts_id=tracking_settings.rts_id,
        )

    @staticmethod
    def update_to_db(tracking_settings: dtos.UpdateTrackingSettingsRequest) -> TrackingSettings:
        return TrackingSettings(
            tmc_measurement_mode=tracking_settings.tmc_measurement_mode,
            tmc_inclination_mode=tracking_settings.tmc_inclination_mode,
            edm_measurement_mode=tracking_settings.edm_measurement_mode,
            prism_type=tracking_settings.prism_type,
            fine_adjust_position_mode=tracking_settings.fine_adjust_position_mode,
            fine_adjust_horizontal_search_range=tracking_settings.fine_adjust_horizontal_search_range,
            fine_adjust_vertical_search_range=tracking_settings.fine_adjust_vertical_search_range,
            power_search_area_dcenterhz=tracking_settings.power_search_area_dcenterhz,
            power_search_area_dcenterv=tracking_settings.power_search_area_dcenterv,
            power_search_area_drangehz=tracking_settings.power_search_area_drangehz,
            power_search_area_drangev=tracking_settings.power_search_area_drangev,
            power_search_area_enabled=tracking_settings.power_search_area_enabled,
            power_search_min_range=tracking_settings.power_search_min_range,
            power_search_max_range=tracking_settings.power_search_max_range,
            power_search=tracking_settings.power_search,
        )

    @staticmethod
    def to_dtos(tracking_settings: list[TrackingSettings]) -> list[dtos.TrackingSettingsResponse]:
        return [TrackingSettingsMapper.to_dto(tracking_setting) for tracking_setting in tracking_settings]


class DeviceMapper:
    @staticmethod
    def to_db(device: dtos.CreateDeviceRequest) -> Device:
        return Device(ip=device.ip, last_seen=device.last_seen)

    @staticmethod
    def to_dto(device: Device) -> dtos.DeviceResponse:
        return dtos.DeviceResponse(id=device.id, ip=device.ip, last_seen=device.last_seen)

    @staticmethod
    def to_dtos(devices: list[Device]) -> list[dtos.DeviceResponse]:
        return [DeviceMapper.to_dto(device) for device in devices]
