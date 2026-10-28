import logging
import os
import queue
import threading

import requests

from rtsworker.api import APIConfig, get_job_status, websocket_sender
from rtsworker.dtos import AddMeasurementRequest, RTSJobStatus

logger = logging.getLogger("root")

MEASUREMENT_LOG_DIR = os.getenv("MEASUREMENT_LOG_DIR", "measurements")
JOB_CHECK_INTERVAL = 1.0
SENDER_SHUTDOWN_TIMEOUT = 30.0

# Same column order as the API's CSV download (readable by scripts/import_measurement.py),
# plus the time the request was written to the serial port.
LOG_HEADER = "ref_time,ts_time,h_angle,v_angle,distance,num_chars,geocom_return_code,rpc_return_code,request_time\n"


class JobStatusWatcher:
    """Polls the job status in a background thread so the measurement loop never blocks on HTTP."""

    def __init__(self, job_id: str, api_config: APIConfig):
        self.job_id = job_id
        self.api_config = api_config
        self._stopped = threading.Event()
        self._thread = threading.Thread(target=self._run, daemon=True)

    def __enter__(self):
        self._thread.start()
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        self._stopped.set()
        self._thread.join()

    @property
    def running(self) -> bool:
        return not self._stopped.is_set()

    def _run(self):
        while not self._stopped.wait(JOB_CHECK_INTERVAL):
            try:
                if get_job_status(self.job_id, self.api_config) != RTSJobStatus.RUNNING:
                    self._stopped.set()
            except requests.RequestException as e:
                logger.warning(f"Could not fetch status of job {self.job_id}: {e}")


class MeasurementStream:
    """Writes measurements to a local CSV file and streams them to the API via websocket."""

    def __init__(self, job_id: str, api_config: APIConfig):
        self.job_id = job_id
        self.log_path = os.path.join(MEASUREMENT_LOG_DIR, f"{job_id}.csv")
        self._queue = queue.Queue()
        self._shutdown = threading.Event()
        self._sender = threading.Thread(
            target=websocket_sender,
            args=(job_id, self._queue, self._shutdown, api_config),
            daemon=True,
        )

    def __enter__(self):
        os.makedirs(MEASUREMENT_LOG_DIR, exist_ok=True)
        self._log_file = open(self.log_path, "a", buffering=1)  # line buffered, survives crashes
        if self._log_file.tell() == 0:
            self._log_file.write(LOG_HEADER)
        logger.info(f"Logging measurements of job {self.job_id} to {self.log_path}")
        self._sender.start()
        return self

    def put(self, m: AddMeasurementRequest, request_time: float = 0.0) -> None:
        self._log_file.write(
            f"{m.controller_timestamp},{m.sensor_timestamp},{m.horizontal_angle},{m.vertical_angle},"
            f"{m.distance},{m.response_length},{m.geocom_return_code},{m.rpc_return_code},{request_time}\n"
        )
        self._queue.put(m)

    def __exit__(self, exc_type, exc_value, traceback):
        logger.info("Waiting for sender thread to drain the measurement queue...")
        self._shutdown.set()
        self._sender.join(timeout=SENDER_SHUTDOWN_TIMEOUT)
        if self._sender.is_alive():
            logger.warning(
                f"Sender thread still busy, {self._queue.qsize()} measurements not yet sent. "
                f"All measurements are in {self.log_path}"
            )
        self._log_file.close()
