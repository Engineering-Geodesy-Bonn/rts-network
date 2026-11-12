"""HTTP client of the API. Thread-safe (one requests session per thread)."""

import ipaddress
import logging
import socket
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed

import requests

from rtsworker import config
from rtsworker.dtos import Claim, JobStatus, JobType, Renewal, TargetPosition

logger = logging.getLogger(__name__)


class ApiError(Exception):
    pass


class JobGone(ApiError):
    """The job was deleted on the server."""


class ApiClient:
    def __init__(self, host: str = config.API_HOST, port: int = config.API_PORT, timeout: float = config.API_TIMEOUT):
        self.host = host
        self.port = port
        self.timeout = timeout
        self._local = threading.local()

    def set_target(self, host: str, port: int) -> None:
        """Switches to another API address (requests and the upload follow at once)."""
        self.host, self.port = host, port

    @property
    def base_url(self) -> str:
        return f"http://{self.host}:{self.port}"

    @property
    def stream_url(self) -> str:
        return f"ws://{self.host}:{self.port}/worker/stream"

    def _session(self) -> requests.Session:
        session = getattr(self._local, "session", None)
        if session is None:
            session = requests.Session()
            self._local.session = session
        return session

    def request(self, method: str, path: str, **kwargs) -> requests.Response:
        kwargs.setdefault("timeout", self.timeout)
        return self._session().request(method, f"{self.base_url}{path}", **kwargs)

    # ── discovery ──────────────────────────────────────────────────────

    def ping(self, host: str | None = None) -> bool:
        try:
            response = requests.get(f"http://{host or self.host}:{self.port}/ping", timeout=2.0)
            return response.status_code == 204
        except requests.RequestException:
            return False

    def resolve(self) -> bool:
        """Checks the configured host and falls back to scanning the local /24 subnet."""
        if self.ping():
            return True
        local_ip = local_ip_towards(self.host)
        if local_ip is None:
            logger.error("API not reachable at %s and no local network found", self.base_url)
            return False
        subnet = ipaddress.ip_network(f"{local_ip}/24", strict=False)
        logger.warning("API not reachable at %s, scanning %s ...", self.base_url, subnet)
        with ThreadPoolExecutor(max_workers=50) as pool:
            futures = {pool.submit(self.ping, str(ip)): str(ip) for ip in subnet.hosts()}
            for future in as_completed(futures):
                if future.result():
                    self.host = futures[future]
                    logger.info("Found the API at %s", self.base_url)
                    for f in futures:
                        f.cancel()
                    return True
        logger.error("No API server found in %s", subnet)
        return False

    # ── jobs ───────────────────────────────────────────────────────────

    def claim(self, worker_id: str, hostname: str, job_types: list[JobType]) -> Claim | None:
        response = self.request(
            "POST", "/worker/claim",
            json={"worker_id": worker_id, "hostname": hostname, "job_types": [t.value for t in job_types]},
        )
        if response.status_code == 204:
            return None
        response.raise_for_status()
        return Claim.model_validate(response.json())

    def renew(self, job_id: str, worker_id: str) -> Renewal:
        response = self.request("POST", f"/worker/jobs/{job_id}/renew", params={"worker_id": worker_id})
        if response.status_code == 404:
            raise JobGone(job_id)
        response.raise_for_status()
        return Renewal.model_validate(response.json())

    def complete(self, job_id: str, worker_id: str, status: JobStatus, error: str | None = None) -> None:
        response = self.request(
            "POST", f"/worker/jobs/{job_id}/complete",
            params={"worker_id": worker_id}, json={"status": status.value, "error": error},
        )
        if response.status_code == 404:
            raise JobGone(job_id)
        response.raise_for_status()

    def instrument_report(self, rts_id: str, report: dict) -> None:
        response = self.request("POST", f"/worker/rts/{rts_id}/instrument-report", json=report)
        response.raise_for_status()

    def target(self) -> TargetPosition | None:
        response = self.request("GET", "/target")
        if response.status_code == 404:
            return None
        response.raise_for_status()
        return TargetPosition.model_validate(response.json())

    def heartbeat(self, body: str) -> dict:
        response = self.request(
            "POST", "/worker/heartbeat", data=body, headers={"Content-Type": "application/json"}
        )
        response.raise_for_status()
        return response.json()


def local_ip_towards(host: str) -> str | None:
    """IP of the interface that routes to host (a UDP connect sends no packets)."""
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
        try:
            s.connect((host, 80))
            return s.getsockname()[0]
        except OSError:
            return None
