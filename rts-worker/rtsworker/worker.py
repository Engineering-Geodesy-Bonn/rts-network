"""Job loop: claim a job, hold its lease while the task runs, report the result."""

import logging
import threading
import time
from typing import Callable

import requests

from rtsworker import config
from rtsworker.client import ApiClient, JobGone
from rtsworker.dtos import Claim, JobStatus, JobType
from rtsworker.health import HeartbeatSender
from rtsworker.outbox import Outbox
from rtsworker.state import STATE
from rtsworker.tasks import TASKS, JobContext
from rtsworker.uploader import Uploader

logger = logging.getLogger(__name__)

RESOLVE_INTERVAL = 30.0  # s between subnet scans while the API is unreachable
COMPLETE_RETRY_FOR = 1800.0  # s a job result is retried while the API is unreachable


class Lease:
    """Renews the lease of a job every second in a background thread.

    Network problems never stop the job (measurements are kept in the outbox); only an
    explicit stop from the API or a deleted job does.
    """

    def __init__(self, client: ApiClient, job_id: str, stop: threading.Event):
        self.client = client
        self.job_id = job_id
        self.stop = stop
        self._ended = threading.Event()
        self._thread = threading.Thread(target=self._run, name="lease", daemon=True)
        self._failing_since: float | None = None

    def __enter__(self):
        self._thread.start()
        return self

    def __exit__(self, *exc):
        self._ended.set()
        self._thread.join(timeout=10)

    def _run(self) -> None:
        while not self._ended.wait(config.RENEW_INTERVAL):
            try:
                renewal = self.client.renew(self.job_id, STATE.worker_id)
                if self._failing_since is not None:
                    logger.info("API reachable again after %.0f s", time.time() - self._failing_since)
                    self._failing_since = None
                if renewal.stop and not self.stop.is_set():
                    logger.info("Job %s: stop requested (%s)", self.job_id, renewal.status.value)
                    self.stop.set()
            except JobGone:
                logger.warning("Job %s was deleted on the server, stopping", self.job_id)
                self.stop.set()
            except Exception as e:
                if self._failing_since is None:
                    self._failing_since = time.time()
                    logger.warning("Cannot renew the lease of job %s (%r), measuring on", self.job_id, e)
                    STATE.error(f"API not reachable: {e!r}")


class Worker:
    def __init__(self, tasks: dict[JobType, Callable[[JobContext], None]] | None = None):
        self.tasks = tasks or TASKS
        self.client = ApiClient()
        self.outbox = Outbox(config.OUTBOX_PATH, STATE.worker_id)
        self.uploader = Uploader(self.client, self.outbox)
        self.heartbeat = HeartbeatSender(self.client, config.MEASUREMENT_LOG_DIR)
        self._last_resolve = 0.0

    def start(self) -> None:
        logger.info("Worker %s (%s) starting, API %s", STATE.worker_id, STATE.hostname, self.client.base_url)
        backlog, _ = self.outbox.backlog()
        if backlog:
            logger.info("%d measurements from a previous run are waiting in the outbox", backlog)
        self.client.resolve()
        self.uploader.start()
        self.heartbeat.start()

    def run(self) -> None:
        self.start()
        while True:
            STATE.touch()
            try:
                claim = self.client.claim(STATE.worker_id, STATE.hostname, list(self.tasks))
            except requests.ConnectionError as e:
                STATE.error(f"API not reachable: {e!r}")
                if time.time() - self._last_resolve > RESOLVE_INTERVAL:
                    self._last_resolve = time.time()
                    self.client.resolve()
                time.sleep(config.CLAIM_INTERVAL)
                continue
            except Exception as e:
                logger.error("Claiming a job failed: %r", e)
                STATE.error(f"Claiming a job failed: {e!r}")
                time.sleep(config.CLAIM_INTERVAL)
                continue
            if claim is None:
                time.sleep(config.CLAIM_INTERVAL)
                continue
            self.run_job(claim)

    def run_job(self, claim: Claim) -> None:
        job = claim.job
        logger.info("Running job %s (%s) on %s", job.id, job.type.value, claim.rts.name)
        STATE.job_started(job.id, job.type.value, job.rts_id)
        stop = threading.Event()
        ctx = JobContext(job=job, rts=claim.rts, client=self.client, outbox=self.outbox, stop=stop)
        status, error = JobStatus.FINISHED, None
        with Lease(self.client, job.id, stop):
            try:
                task = self.tasks.get(job.type)
                if task is None:
                    raise RuntimeError(f"This worker cannot run {job.type.value} jobs")
                task(ctx)
            except Exception as e:
                logger.exception("Job %s failed", job.id)
                status, error = JobStatus.FAILED, f"{type(e).__name__}: {e}"
                STATE.error(f"Job {job.type.value} failed: {e}")
            finally:
                ctx.close()
                self.outbox.flush()
            self._complete(job.id, status, error)
        STATE.job_ended(status == JobStatus.FAILED)

    def _complete(self, job_id: str, status: JobStatus, error: str | None) -> None:
        deadline = time.time() + COMPLETE_RETRY_FOR
        while True:
            try:
                self.client.complete(job_id, STATE.worker_id, status, error)
                logger.info("Job %s %s", job_id, status.value)
                return
            except JobGone:
                logger.warning("Job %s was deleted on the server", job_id)
                return
            except Exception as e:
                if time.time() > deadline:
                    logger.error("Giving up to report the result of job %s: %r", job_id, e)
                    return
                logger.warning("Cannot report the result of job %s (%r), retrying", job_id, e)
                time.sleep(2.0)
