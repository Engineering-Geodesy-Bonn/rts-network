"""Job implementations. Each task gets a JobContext and returns normally on success.

Measuring tasks write every measurement through ctx.sink: it gets a sequence number, is
appended to the local CSV log and stored in the outbox, from where it is uploaded.
A task ends when ctx.stop is set (the user stopped the job) or on an error (raise).
"""

import logging
import math
import os
import threading
import time
from dataclasses import dataclass

from rtsworker import config
from rtsworker.client import ApiClient
from rtsworker.dtos import Job, JobType, RTSConfig, TargetPosition
from rtsworker.instrument import open_instrument
from rtsworker.outbox import Outbox
from rtsworker.pygeocom import TMCInclinationMode, TMCMeasurementMode
from rtsworker.state import STATE

logger = logging.getLogger(__name__)

ALARM_THRESHOLD = 10  # consecutive attempts without distance until the instrument beeps
ALARM_EVERY_N_SECONDS = 6

# Same columns as the API's CSV download, plus the request time and the sequence number
LOG_HEADER = "ref_time,ts_time,h_angle,v_angle,distance,num_chars,geocom_return_code,rpc_return_code,request_time,seq\n"


class MeasurementSink:
    def __init__(self, job_id: str, outbox: Outbox):
        self.job_id = job_id
        self.outbox = outbox
        self.seq = 0
        os.makedirs(config.MEASUREMENT_LOG_DIR, exist_ok=True)
        self.log_path = os.path.join(config.MEASUREMENT_LOG_DIR, f"{job_id}.csv")
        self._log = open(self.log_path, "a", buffering=1)  # line buffered: survives crashes
        if self._log.tell() == 0:
            self._log.write(LOG_HEADER)

    def put(self, response, request_time: float | None = None) -> None:
        row = [
            self.seq, response.resp_time, response.time, request_time, response.resp_len,
            response.geocom_return_code, response.rpc_return_code,
            response.distance, response.h_angle, response.v_angle,
        ]
        self.outbox.put(self.job_id, self.seq, row)  # first: a logged row is always in the outbox
        if self._log is not None:
            try:
                self._log.write(
                    f"{response.resp_time},{response.time},{response.h_angle},{response.v_angle},{response.distance},"
                    f"{response.resp_len},{response.geocom_return_code},{response.rpc_return_code},{request_time or ''},{self.seq}\n"
                )
            except OSError as e:
                # e.g. disk full: the outbox keeps the measurements, the CSV copy is given up
                logger.error("CSV log %s cannot be written (%r), continuing without it", self.log_path, e)
                STATE.error(f"CSV log: {e!r}")
                self._close_log()
        self.seq += 1
        STATE.measurement_logged()

    def _close_log(self) -> None:
        log, self._log = self._log, None
        if log is not None:
            try:
                log.close()
            except OSError:
                pass

    def close(self) -> None:
        self._close_log()


@dataclass
class JobContext:
    job: Job
    rts: RTSConfig
    client: ApiClient
    outbox: Outbox
    stop: threading.Event

    _sink: MeasurementSink | None = None

    @property
    def sink(self) -> MeasurementSink:
        if self._sink is None:
            self._sink = MeasurementSink(self.job.id, self.outbox)
            STATE.streaming = True
        return self._sink

    def close(self) -> None:
        if self._sink is not None:
            self._sink.close()
        STATE.streaming = False


# ── instrument checks ───────────────────────────────────────────────────


def collect_instrument_report(instrument, latency_samples: int = 10) -> dict:
    """Identification, power and temperature of the instrument and the GeoCOM latency.
    Every query is optional, so that instruments not supporting a request still yield a report."""
    report = {"ok": True, "source": "health_check", "errors": [], "collected_at": time.time()}

    def query(key: str, request):
        try:
            report[key] = request()
        except Exception as e:
            report["errors"].append(f"{key}: {e!r}")

    query("instrument_name", instrument.get_instrument_name)
    query("serial_number", instrument.get_instrument_number)
    query("software_version", lambda: ".".join(str(v) for v in instrument.get_software_version()))
    try:
        capacity, active_power, _ = instrument.check_power()
        report["battery_capacity"] = capacity
        report["power_source"] = active_power.name.lower()
    except Exception as e:
        report["errors"].append(f"battery: {e!r}")
    query("internal_temperature", instrument.get_internal_temperature)
    query("face", instrument.get_face)

    latencies = []
    for _ in range(latency_samples):
        try:
            started = time.time()
            instrument.get_instrument_number()
            latencies.append(time.time() - started)
        except Exception as e:
            report["errors"].append(f"latency: {e!r}")
            break
    if latencies:
        report["latency_mean"] = sum(latencies) / len(latencies)
        report["latency_max"] = max(latencies)
        report["latency_samples"] = len(latencies)
    if "serial_number" not in report and not latencies:
        report["ok"] = False
    return report


def health_check(ctx: JobContext) -> None:
    try:
        with open_instrument(ctx.rts) as instrument:
            report = collect_instrument_report(instrument)
    except Exception as e:
        report = {"ok": False, "source": "health_check", "errors": [f"Connection to the instrument failed: {e}"], "collected_at": time.time()}
    ctx.client.instrument_report(ctx.rts.id, report)
    if not report["ok"]:
        raise RuntimeError(f"Instrument check failed: {'; '.join(report['errors'])}")


def report_instrument_state(instrument, ctx: JobContext) -> None:
    """Best effort report before tracking starts, never interrupts the job."""
    try:
        report = collect_instrument_report(instrument, latency_samples=3)
        report["source"] = "tracking_start"
        ctx.client.instrument_report(ctx.rts.id, report)
    except Exception as e:
        logger.warning("Could not report the instrument state: %r", e)


# ── simple commands ─────────────────────────────────────────────────────


def test_connection(ctx: JobContext) -> None:
    with open_instrument(ctx.rts) as instrument:
        instrument.beep_alarm_normal()
        time.sleep(1)


def change_face(ctx: JobContext) -> None:
    with open_instrument(ctx.rts) as instrument:
        instrument.change_face()


def angles_from_position(rts: RTSConfig, target: TargetPosition) -> tuple[float, float]:
    """Instrument angles towards a target in the coordinate frame of the API (station and
    orientation of the RTS, as used to compute positions from the measurements)."""
    dx, dy, dz = target.x - rts.station_x, target.y - rts.station_y, target.z - rts.station_z
    horizontal = math.sqrt(dx**2 + dy**2)
    return (math.atan2(dx, dy) - rts.orientation) % (2 * math.pi), math.pi / 2 - math.atan2(dz, horizontal)


def turn_to_target(ctx: JobContext) -> None:
    target = ctx.client.target()
    if target is None:
        raise ValueError("No target position known yet: no station has measured the prism")
    h_angle, v_angle = angles_from_position(ctx.rts, target)
    logger.info("Turning to the target position measured %.0f s ago", time.time() - target.timestamp)
    with open_instrument(ctx.rts) as instrument:
        instrument.position(horizontal=h_angle, vertical=v_angle)


# ── measuring ───────────────────────────────────────────────────────────


def track(ctx: JobContext, simulate: bool) -> None:
    rts = ctx.rts
    if simulate and not rts.port.startswith("sim://"):
        rts = rts.model_copy(update={"port": f"sim://{rts.name}"})
    settings = rts.tracking
    with open_instrument(rts) as instrument:
        report_instrument_state(instrument, ctx)
        instrument.stop_tracking()
        instrument.start_tracking(settings)
        logger.info("Tracking with %s on %s", rts.name, rts.port)
        no_distance = 0
        last_alarm = 0.0
        try:
            while not ctx.stop.is_set():
                response = instrument.get_full_measurement(TMCInclinationMode.AUTOMATIC, 1000)
                request_time = instrument.last_request_time
                # Without a distance the instrument also reports sensor time 0. Such a sample is
                # no measurement: it would be a point at the station and corrupt the time sync.
                if response.distance == 0 or response.time == 0:
                    no_distance += 1
                    STATE.no_distance()
                    if no_distance > ALARM_THRESHOLD and time.time() - last_alarm > ALARM_EVERY_N_SECONDS:
                        logger.warning("Prism lost (%d attempts without distance)", no_distance)
                        instrument.beep_alarm_normal()
                        last_alarm = time.time()
                        instrument.do_measure(
                            TMCMeasurementMode(settings.tmc_measurement_mode),
                            TMCInclinationMode(settings.tmc_inclination_mode),
                        )
                    continue
                no_distance = 0
                ctx.sink.put(response, request_time)
        finally:
            try:
                instrument.stop_tracking()
            except Exception as e:
                logger.warning("Could not stop tracking on the instrument: %r", e)
    logger.info("Tracking stopped after %d measurements", ctx.sink.seq)


def track_prism(ctx: JobContext) -> None:
    track(ctx, simulate=False)


def dummy_tracking(ctx: JobContext) -> None:
    track(ctx, simulate=True)


def add_static_measurement(ctx: JobContext) -> None:
    with open_instrument(ctx.rts) as instrument:
        instrument.stop_tracking()
        instrument.prepare_static_measurement(ctx.rts.tracking)
        response = instrument.get_full_measurement(TMCInclinationMode.AUTOMATIC, 300)
        instrument.stop_tracking()
    if response.distance == 0 or response.time == 0:
        raise RuntimeError("No distance measured (prism not found?)")
    ctx.sink.put(response, None)


TASKS = {
    JobType.TEST_CONNECTION: test_connection,
    JobType.TRACK_PRISM: track_prism,
    JobType.CHANGE_FACE: change_face,
    JobType.DUMMY_TRACKING: dummy_tracking,
    JobType.TURN_TO_TARGET: turn_to_target,
    JobType.ADD_STATIC_MEASUREMENT: add_static_measurement,
    JobType.HEALTH_CHECK: health_check,
}
