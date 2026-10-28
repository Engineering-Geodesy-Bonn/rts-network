import queue
import threading
import time
import math
import requests
from rtsworker.api import (
    APIConfig,
    get_job_status,
    get_latest_target_position,
    get_rts,
    get_tracking_settings,
    post_measurement,
    post_static_measurement,
    update_job_status,
    websocket_sender,
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

SLEEP_TIME = 0.001
ALARM_THRESHOLD = 10
ALARM_EVERY_N_SECONDS = 6
JOB_CHECK_INTERVAL = 1.0
SENDER_DRAIN_TIMEOUT = 30.0


def angles_from_position(station: Station, target: TargetPosition) -> tuple[float, float]:
    dx = target.x - station.e0
    dy = target.y - station.n0
    dz = target.z - station.h0

    distance = math.sqrt(dx**2 + dy**2)

    h_angle = math.atan2(dx, dy)
    v_angle = math.pi / 2 - math.atan2(dz, distance)
    return h_angle, v_angle


def poll_job_status(job_id: str, current_status: RTSJobStatus, api_config: APIConfig) -> RTSJobStatus:
    # A short network outage must not end a running measurement, so keep the last known status.
    try:
        return get_job_status(job_id, api_config)
    except (requests.ConnectionError, requests.Timeout) as e:
        print(f"Could not fetch job status ({e}). Keeping status {current_status.value}.")
        return current_status


def start_sender(job: RTSJobResponse, api_config: APIConfig) -> tuple[queue.Queue, threading.Event, threading.Thread]:
    measurement_queue = queue.Queue()
    shutdown_event = threading.Event()

    sender_thread = threading.Thread(
        target=websocket_sender,
        args=(job.job_id, measurement_queue, shutdown_event, api_config),
        daemon=True,
    )
    sender_thread.start()
    return measurement_queue, shutdown_event, sender_thread


def stop_sender(measurement_queue: queue.Queue, shutdown_event: threading.Event, sender_thread: threading.Thread) -> None:
    # The sender stops consuming once shutdown_event is set, so wait for it to drain first.
    # unfinished_tasks also counts a measurement that was taken from the queue but not yet sent.
    if measurement_queue.unfinished_tasks:
        print(f"Waiting for measurement queue to drain ({measurement_queue.unfinished_tasks} items left)...")

    deadline = time.time() + SENDER_DRAIN_TIMEOUT
    while measurement_queue.unfinished_tasks and time.time() < deadline:
        time.sleep(0.1)

    if measurement_queue.unfinished_tasks:
        print(f"Warning: {measurement_queue.unfinished_tasks} measurements could not be sent.")

    print("Signaling sender thread to shut down...")
    shutdown_event.set()

    sender_thread.join(timeout=10.0)  # Wait for thread to exit
    if sender_thread.is_alive():
        print("Warning: Sender thread did not shut down cleanly.")
    else:
        print("Sender thread shut down. Exiting.")


def turn_to_target(job: RTSJobResponse, api_config: APIConfig) -> None:
    rts = get_rts(job.rts_id, api_config)
    target_position = get_latest_target_position(api_config)

    if target_position is None:
        raise ValueError("No target position available")

    with RTSSerialConnection(rts) as rts_serial:
        print("Setting station")
        station = rts_serial.get_station()
        h_angle, v_angle = angles_from_position(station, target_position)
        rts_serial.position(horizontal=h_angle, vertical=v_angle)

    update_job_status(job.job_id, RTSJobStatus.FINISHED, api_config)


def test_rts(job: RTSJobResponse, api_config: APIConfig) -> None:
    rts = get_rts(job.rts_id, api_config)
    with RTSSerialConnection(rts) as rts_serial:
        rts_serial.beep_alarm_normal()
        time.sleep(1)

    update_job_status(job.job_id, RTSJobStatus.FINISHED, api_config)


def change_face(job: RTSJobResponse, api_config: APIConfig) -> None:
    rts = get_rts(job.rts_id, api_config)
    with RTSSerialConnection(rts) as rts_serial:
        print("Changing face")
        rts_serial.change_face()
    update_job_status(job.job_id, RTSJobStatus.FINISHED, api_config)


def dummy_tracking(job: RTSJobResponse, api_config: APIConfig):
    print("Starting measurement")
    job_status = get_job_status(job.job_id, api_config)
    last_job_status_time = time.time()

    measurement_queue, shutdown_event, sender_thread = start_sender(job, api_config)

    try:
        while job_status == RTSJobStatus.RUNNING:
            if time.time() - last_job_status_time > JOB_CHECK_INTERVAL:
                job_status = poll_job_status(job.job_id, job_status, api_config)
                last_job_status_time = time.time()
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
            measurement_queue.put(add_measurement.model_dump())
            time.sleep(0.01)
        print("Stopped logging")
    finally:
        stop_sender(measurement_queue, shutdown_event, sender_thread)


def track_prism(job: RTSJobResponse, api_config: APIConfig) -> None:
    rts = get_rts(job.rts_id, api_config)
    tracking_settings_response = get_tracking_settings(job.rts_id, api_config)
    tracking_settings = TrackingSettings.from_response(tracking_settings_response)

    measurement_queue, shutdown_event, sender_thread = start_sender(job, api_config)

    try:
        with RTSSerialConnection(rts) as rts_serial:
            rts_serial.stop_tracking()
            rts_serial.start_tracking(tracking_settings)
            print("Starting measurement loop...")
            cnt = 1
            no_distance_count = 0
            last_alarm = 0

            last_job_status_time = time.time()
            job_status = get_job_status(job.job_id, api_config)

            while job_status == RTSJobStatus.RUNNING:
                if time.time() - last_job_status_time > JOB_CHECK_INTERVAL:
                    job_status = poll_job_status(job.job_id, job_status, api_config)
                    last_job_status_time = time.time()
                response = rts_serial.get_full_measurement(TMCInclinationMode.AUTOMATIC, 1000)

                if response.distance == 0:
                    no_distance_count += 1
                    print(f"No distance measurement available ({no_distance_count})")
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

                    measurement_queue.put(new_measurement.model_dump())
                    no_distance_count = 0
                    cnt += 1

                time.sleep(SLEEP_TIME)

            rts_serial.stop_tracking()
            print("Tracking loop finished.")

    except Exception as e:
        print(f"CRITICAL ERROR in measurement loop: {e}")
        raise e
    finally:
        stop_sender(measurement_queue, shutdown_event, sender_thread)


def add_single_measurement(job: RTSJobResponse, api_config: APIConfig) -> None:
    rts = get_rts(job.rts_id, api_config)
    tracking_settings_response = get_tracking_settings(job.rts_id, api_config)
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
        post_static_measurement(new_measurement, api_config)
        rts_serial.stop_tracking()

    update_job_status(job.job_id, RTSJobStatus.FINISHED, api_config)


def add_single_measurement_dummy(job: RTSJobResponse, api_config: APIConfig) -> None:
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
    post_static_measurement(add_measurement, api_config)
    update_job_status(job.job_id, RTSJobStatus.FINISHED, api_config)
