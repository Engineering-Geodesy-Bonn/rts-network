import logging
import time
import math
from rtsworker.api import (
    APIConfig,
    get_latest_target_position,
    get_rts,
    get_tracking_settings,
    post_instrument_report,
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
from rtsworker.pygeocom import PyGeoCom, Station, TMCInclinationMode, TMCMeasurementMode
from rtsworker.rts import RTSSerialConnection
from rtsworker.stream import JobStatusWatcher, MeasurementStream

logger = logging.getLogger("root")

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


def collect_instrument_report(rts_serial: PyGeoCom, latency_samples: int = 10) -> dict:
    """Reads identification, power and temperature of the total station and measures the GeoCOM latency.

    Every query is optional, so that instruments not supporting a request still yield a report.
    """
    report = {"ok": True, "source": "health_check", "errors": [], "collected_at": time.time()}

    def query(key: str, request):
        try:
            report[key] = request()
        except Exception as e:
            report["errors"].append(f"{key}: {e!r}")

    query("instrument_name", rts_serial.get_instrument_name)
    query("serial_number", rts_serial.get_instrument_number)
    query("software_version", lambda: ".".join(str(v) for v in rts_serial.get_software_version()))
    try:
        capacity, active_power, _ = rts_serial.check_power()
        report["battery_capacity"] = capacity
        report["power_source"] = active_power.name.lower()
    except Exception as e:
        report["errors"].append(f"battery: {e!r}")
    query("internal_temperature", rts_serial.get_internal_temperature)
    query("face", rts_serial.get_face)

    latencies = []
    for _ in range(latency_samples):
        try:
            started = time.time()
            rts_serial.get_instrument_number()
            latencies.append(time.time() - started)
        except Exception as e:
            report["errors"].append(f"latency: {e!r}")
            break
    if latencies:
        report["latency_mean"] = sum(latencies) / len(latencies)
        report["latency_max"] = max(latencies)
        report["latency_samples"] = len(latencies)

    # The instrument did not answer anything meaningful
    if "serial_number" not in report and not latencies:
        report["ok"] = False
    return report


def health_check(job: RTSJobResponse, api_config: APIConfig) -> None:
    rts = get_rts(job.rts_id, api_config)
    try:
        with RTSSerialConnection(rts) as rts_serial:
            report = collect_instrument_report(rts_serial)
    except Exception as e:
        report = {"ok": False, "source": "health_check", "errors": [f"Serial connection failed: {e!r}"], "collected_at": time.time()}
    post_instrument_report(job.rts_id, report, api_config)

    if not report["ok"]:
        raise RuntimeError(f"Instrument check failed: {'; '.join(report['errors'])}")
    update_job_status(job.job_id, RTSJobStatus.FINISHED, api_config)


def report_instrument_state(rts_serial: PyGeoCom, rts_id: str, api_config: APIConfig) -> None:
    """Best-effort instrument report before tracking starts, never interrupts the job."""
    try:
        report = collect_instrument_report(rts_serial, latency_samples=3)
        report["source"] = "tracking_start"
        post_instrument_report(rts_id, report, api_config)
    except Exception as e:
        logger.warning(f"Could not report instrument state: {e}")


def turn_to_target(job: RTSJobResponse, api_config: APIConfig) -> None:
    rts = get_rts(job.rts_id, api_config)
    target_position = get_latest_target_position(api_config)

    if target_position is None:
        raise ValueError("No target position available")

    with RTSSerialConnection(rts) as rts_serial:
        logger.info("Setting station")
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
        logger.info("Changing face")
        rts_serial.change_face()
    update_job_status(job.job_id, RTSJobStatus.FINISHED, api_config)


def dummy_tracking(job: RTSJobResponse, api_config: APIConfig):
    logger.info("Starting measurement")
    with MeasurementStream(job.job_id, api_config) as stream, JobStatusWatcher(job.job_id, api_config) as job_status:
        while job_status.running:
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
            stream.put(add_measurement)
            time.sleep(0.01)
    logger.info("Stopped logging")


def track_prism(job: RTSJobResponse, api_config: APIConfig) -> None:
    rts = get_rts(job.rts_id, api_config)
    tracking_settings_response = get_tracking_settings(job.rts_id, api_config)
    tracking_settings = TrackingSettings.from_response(tracking_settings_response)

    with MeasurementStream(job.job_id, api_config) as stream, RTSSerialConnection(rts) as rts_serial:
        report_instrument_state(rts_serial, job.rts_id, api_config)
        rts_serial.stop_tracking()
        rts_serial.start_tracking(tracking_settings)
        logger.info("Starting measurement loop...")
        no_distance_count = 0
        last_alarm = 0

        with JobStatusWatcher(job.job_id, api_config) as job_status:
            while job_status.running:
                response = rts_serial.get_full_measurement(TMCInclinationMode.AUTOMATIC, 1000)

                # Without a distance the instrument also reports sensor time 0.
                # Such a sample is no measurement and must not be stored: it would
                # be a point at the station position and corrupt the time sync.
                if response.distance == 0 or response.time == 0:
                    no_distance_count += 1
                    logger.info(f"No distance measurement available ({no_distance_count})")
                    if no_distance_count > ALARM_THRESHOLD and (time.time() - last_alarm) > ALARM_EVERY_N_SECONDS:
                        rts_serial.beep_alarm_normal()
                        last_alarm = time.time()
                        logger.warning("Triggering alarm")
                        rts_serial.do_measure(
                            TMCMeasurementMode(tracking_settings.tmc_measurement_mode),
                            TMCInclinationMode(tracking_settings.tmc_inclination_mode),
                        )
                    continue

                new_measurement = AddMeasurementRequest(
                    rts_job_id=job.job_id,
                    controller_timestamp=response.resp_time,
                    sensor_timestamp=response.time,
                    horizontal_angle=response.h_angle,
                    vertical_angle=response.v_angle,
                    distance=response.distance,
                    response_length=response.resp_len,
                    geocom_return_code=response.geocom_return_code,
                    rpc_return_code=response.rpc_return_code,
                )
                stream.put(new_measurement, request_time=rts_serial.last_request_time)
                no_distance_count = 0

        rts_serial.stop_tracking()
        logger.info("Tracking loop finished.")


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
            controller_timestamp=response.resp_time,
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
