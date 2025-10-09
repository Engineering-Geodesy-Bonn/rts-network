import time
import math
from rtsworker.api import (
    get_job_status,
    get_latest_target_position,
    get_rts,
    get_tracking_settings,
    post_measurement,
    post_static_measurement,
    update_job_status,
)
from rtsworker.dtos import (
    AddMeasurementRequest,
    RTSJobResponse,
    RTSJobStatus,
    TargetPosition,
    TrackingSettings,
)
from rtsworker.pygeocom import Station, TMCInclinationMode, TMCMeasurementMode
from rtsworker.rts import RTSSerialConnection

SLEEP_TIME = 0.0001
ALARM_THRESHOLD = 10
ALARM_EVERY_N_SECONDS = 6


def angles_from_position(station: Station, target: TargetPosition) -> tuple[float, float]:
    dx = target.x - station.e0
    dy = target.y - station.n0
    dz = target.z - station.h0

    distance = math.sqrt(dx**2 + dy**2)

    h_angle = math.atan2(dx, dy)
    v_angle = math.pi / 2 - math.atan2(dz, distance)
    return h_angle, v_angle


def turn_to_target(job: RTSJobResponse) -> None:
    rts = get_rts(job.rts_id)
    target_position = get_latest_target_position()

    if target_position is None:
        raise ValueError("No target position available")

    with RTSSerialConnection(rts) as rts_serial:
        print("Setting station")
        station = rts_serial.get_station()
        h_angle, v_angle = angles_from_position(station, target_position)
        rts_serial.position(horizontal=h_angle, vertical=v_angle)

    update_job_status(job.job_id, RTSJobStatus.FINISHED)


def test_rts(job: RTSJobResponse) -> None:
    rts = get_rts(job.rts_id)
    with RTSSerialConnection(rts) as rts_serial:
        rts_serial.beep_alarm_normal()
        time.sleep(1)

    update_job_status(job.job_id, RTSJobStatus.FINISHED)


def change_face(job: RTSJobResponse) -> None:
    rts = get_rts(job.rts_id)
    with RTSSerialConnection(rts) as rts_serial:
        print("Changing face")
        rts_serial.change_face()
    update_job_status(job.job_id, RTSJobStatus.FINISHED)


def dummy_tracking(job: RTSJobResponse):
    print("Starting measurement")
    while get_job_status(job.job_id) == RTSJobStatus.RUNNING:
        timestamp = time.time()
        distance = math.cos(timestamp) * 100
        horizontal_angle = math.sin(timestamp)
        vertical_angle = math.sin(timestamp) * math.cos(timestamp)
        add_measurement = AddMeasurementRequest(
            rts_job_id=job.job_id,
            controller_timestamp=timestamp,
            sensor_timestamp=timestamp * 1000,
            distance=distance,
            horizontal_angle=horizontal_angle,
            vertical_angle=vertical_angle,
            response_length=10,
            geocom_return_code=0,
            rpc_return_code=0,
        )
        post_measurement(add_measurement)
        time.sleep(0.1)
    print("Stopped logging")


def track_prism(job: RTSJobResponse) -> None:
    rts = get_rts(job.rts_id)
    tracking_settings_response = get_tracking_settings(job.rts_id)
    tracking_settings = TrackingSettings.from_response(tracking_settings_response)
    with RTSSerialConnection(rts) as rts_serial:
        rts_serial.stop_tracking()
        rts_serial.start_tracking(tracking_settings)
        print("Starting measurement")
        cnt = 1
        no_distance_count = 0
        last_alarm = 0

        while get_job_status(job.job_id) == RTSJobStatus.RUNNING:
            response = rts_serial.get_full_measurement(TMCInclinationMode.AUTOMATIC, 1000)

            if response.distance == 0:
                no_distance_count += 1
                print("No distance measurement available (%i)", no_distance_count)
                if no_distance_count > ALARM_THRESHOLD and (time.time() - last_alarm) > ALARM_EVERY_N_SECONDS:
                    rts_serial.beep_alarm_normal()
                    last_alarm = time.time()
                    print("Triggering alarm")
                    rts_serial.do_measure(
                        TMCMeasurementMode(tracking_settings.tmc_measurement_mode),
                        TMCInclinationMode(tracking_settings.tmc_inclination_mode),
                    )
            else:
                new_measurement = AddMeasurementRequest(
                    rts_job_id=job.job_id,
                    controller_timestamp=response.resp_time + rts.external_delay,
                    sensor_timestamp=response.time,
                    horizontal_angle=response.h_angle,
                    vertical_angle=response.v_angle,
                    distance=response.distance,
                    response_length=response.resp_len,
                    geocom_return_code=response.geocom_return_code,
                    rpc_return_code=response.rpc_return_code,
                )
                post_measurement(new_measurement)

                no_distance_count = 0
                cnt += 1

            time.sleep(SLEEP_TIME)

        rts_serial.stop_tracking()


def add_single_measurement(job: RTSJobResponse) -> None:
    rts = get_rts(job.rts_id)
    tracking_settings_response = get_tracking_settings(job.rts_id)
    tracking_settings = TrackingSettings.from_response(tracking_settings_response)
    with RTSSerialConnection(rts) as rts_serial:
        rts_serial.stop_tracking()
        rts_serial.prepare_static_measurement(tracking_settings)
        response = rts_serial.get_full_measurement(TMCInclinationMode.AUTOMATIC, 300)
        new_measurement = AddMeasurementRequest(
            rts_job_id=job.job_id,
            controller_timestamp=response.resp_time + rts.external_delay,
            sensor_timestamp=response.time,
            horizontal_angle=response.h_angle,
            vertical_angle=response.v_angle,
            distance=response.distance,
            response_length=response.resp_len,
            geocom_return_code=response.geocom_return_code,
            rpc_return_code=response.rpc_return_code,
        )
        post_static_measurement(new_measurement)
        rts_serial.stop_tracking()

    update_job_status(job.job_id, RTSJobStatus.FINISHED)


def add_single_measurement_dummy(job: RTSJobResponse) -> None:
    timestamp = time.time()
    distance = math.cos(timestamp) * 100
    horizontal_angle = math.sin(timestamp)
    vertical_angle = math.sin(timestamp) * math.cos(timestamp)
    add_measurement = AddMeasurementRequest(
        rts_job_id=job.job_id,
        controller_timestamp=timestamp,
        sensor_timestamp=timestamp,
        distance=distance,
        horizontal_angle=horizontal_angle,
        vertical_angle=vertical_angle,
        response_length=10,
        geocom_return_code=0,
        rpc_return_code=0,
    )
    post_static_measurement(add_measurement)
    update_job_status(job.job_id, RTSJobStatus.FINISHED)
