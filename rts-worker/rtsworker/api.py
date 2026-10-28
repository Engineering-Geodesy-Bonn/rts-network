import logging
import asyncio
from dataclasses import dataclass, field
import ipaddress
import os
import queue
import socket
import threading
from uuid import UUID
import aiohttp
import requests
import websockets
from rtsworker.dtos import (
    AddMeasurementRequest,
    DeviceResponse,
    MeasurementResponse,
    RTSJobResponse,
    RTSJobStatus,
    RTSResponse,
    TargetPosition,
    TrackingSettingsResponse,
)

logger = logging.getLogger("worker")

@dataclass
class APIConfig:
    host: str = field(default_factory=lambda: os.getenv("API_HOST", "131.220.172.1"))
    port: int = field(default_factory=lambda: int(os.getenv("API_PORT", 8000)))
    timeout: int = field(default_factory=lambda: int(os.getenv("API_TIMEOUT", 5)))
    ws_reconnect_delay: int = field(default_factory=lambda: int(os.getenv("WS_RECONNECT_DELAY", 5)))

    @property
    def websocket_url(self) -> str:
        return f"ws://{self.host}:{self.port}/ws/measurements/{{job_id}}"

    @property
    def api_url(self) -> str:
        return f"http://{self.host}:{self.port}"

    def ping(self) -> bool:
        try:
            response = requests.get(f"{self.api_url}/ping", timeout=self.timeout)
            return response.status_code == 204
        except requests.RequestException:
            return False

    def resolve(self) -> bool:
        """Checks the configured host and falls back to scanning the local /24 subnet."""
        if self.ping():
            return True

        local_ip = get_local_ip(self.host)
        if local_ip is None:
            logger.error(f"API not reachable at {self.api_url} and no local network found.")
            return False

        subnet = ipaddress.ip_network(f"{local_ip}/24", strict=False)
        logger.warning(f"API not reachable at {self.api_url}. Scanning {subnet}...")
        found_ip = asyncio.run(find_server(str(subnet), self.port, concurrency_limit=50))

        if found_ip is None:
            logger.error(f"No API server found in {subnet}.")
            return False

        logger.info(f"Found API server at {found_ip}. Updating host.")
        self.host = found_ip
        return True


def get_local_ip(target_host: str) -> str | None:
    """Returns the IP of the interface that routes to target_host (UDP connect sends no packets)."""
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
        try:
            s.connect((target_host, 80))
            return s.getsockname()[0]
        except OSError:
            return None


async def check_host(session: aiohttp.ClientSession, ip: str, port: int) -> str | None:
    """Checks if a single IP responds with 204 at /ping."""
    url = f"http://{ip}:{port}/ping"
    try:
        # Short timeout keeps the scan fast
        async with session.get(url, timeout=aiohttp.ClientTimeout(total=2.0)) as response:
            if response.status == 204:
                return ip
    except (aiohttp.ClientError, asyncio.TimeoutError, OSError):
        # Ignore connection errors, timeouts, and unreachable hosts
        pass
    return None

async def find_server(subnet_cidr: str, port: int, concurrency_limit: int = 50) -> str | None:
    """
    Scans a network subnet for a server returning 204 at /ping.

    :param subnet_cidr: Subnet to scan in CIDR notation (e.g., '192.168.1.0/24')
    :param port: API port to probe
    :param concurrency_limit: Max number of simultaneous requests
    :return: The IP address string if found, otherwise None
    """
    network = ipaddress.ip_network(subnet_cidr, strict=False)
    semaphore = asyncio.Semaphore(concurrency_limit)

    async def sem_check(session, ip_str):
        async with semaphore:
            return await check_host(session, ip_str, port)

    async with aiohttp.ClientSession() as session:
        # Create asynchronous tasks for all host IPs in the subnet
        tasks = [
            asyncio.create_task(sem_check(session, str(ip)))
            for ip in network.hosts()
        ]

        # Process results as they complete to return early as soon as the server is found
        for completed_task in asyncio.as_completed(tasks):
            result = await completed_task
            if result:
                # Cancel remaining pending tasks to free up resources
                for t in tasks:
                    if not t.done():
                        t.cancel()
                return result

    return None


def self_register(api_config: APIConfig) -> None:
    response = requests.post(f"{api_config.api_url}/devices/register", timeout=api_config.timeout)
    response.raise_for_status()
    return DeviceResponse.model_validate(response.json())


def fetch_new_job(api_config: APIConfig) -> RTSJobResponse:
    response = requests.get(f"{api_config.api_url}/jobs/fetch", timeout=api_config.timeout)
    logger.debug(f"Fetching job at {api_config.api_url}/jobs/fetch")

    if not response.ok or response.status_code == 204:
        return None

    return RTSJobResponse.model_validate(response.json())


def update_job_status(job_id: UUID, status: RTSJobStatus, api_config: APIConfig) -> RTSJobResponse:
    response = requests.put(f"{api_config.api_url}/jobs/{job_id}?job_status={status.value}", timeout=api_config.timeout)
    response.raise_for_status()
    return RTSJobResponse.model_validate(response.json())


def get_job_status(job_id: UUID, api_config: APIConfig) -> RTSJobStatus:
    response = requests.get(f"{api_config.api_url}/jobs/{job_id}/status", timeout=api_config.timeout)
    response.raise_for_status()
    return RTSJobStatus(response.json()["job_status"])


def post_measurement(new_measurement: AddMeasurementRequest, api_config: APIConfig) -> MeasurementResponse:
    response = requests.post(f"{api_config.api_url}/measurements", json=new_measurement.model_dump(mode='json'), timeout=api_config.timeout)
    response.raise_for_status()
    return MeasurementResponse.model_validate(response.json())


def post_static_measurement(new_measurement: AddMeasurementRequest, api_config: APIConfig) -> MeasurementResponse:
    response = requests.post(f"{api_config.api_url}/measurements/static", json=new_measurement.model_dump(mode='json'), timeout=api_config.timeout)
    response.raise_for_status()
    return MeasurementResponse.model_validate(response.json())


def get_rts(rts_id: UUID, api_config: APIConfig) -> RTSResponse:
    response = requests.get(f"{api_config.api_url}/rts/{rts_id}", timeout=api_config.timeout)
    response.raise_for_status()
    return RTSResponse.model_validate(response.json())


def get_tracking_settings(rts_id: UUID, api_config: APIConfig) -> dict:
    response = requests.get(f"{api_config.api_url}/rts/{rts_id}/tracking_settings", timeout=api_config.timeout)
    response.raise_for_status()
    return TrackingSettingsResponse.model_validate(response.json())


def get_latest_target_position(api_config: APIConfig) -> TargetPosition:
    response = requests.get(f"{api_config.api_url}/target", timeout=api_config.timeout)
    response.raise_for_status()
    return TargetPosition.model_validate(response.json())


def websocket_sender(job_id: UUID, data_queue: queue.Queue, shutdown_event: threading.Event, api_config: APIConfig):
    """Sends queued measurements until shutdown_event is set and the queue is drained.

    After shutdown is requested, a failed connection is retried only once more so that
    the thread cannot block the end of a job when the API is unreachable.
    """
    uri = api_config.websocket_url.format(job_id=job_id)
    pending_state = [None]

    while True:
        try:
            logger.info(f"Attempting WebSocket connection to {uri}...")
            asyncio.run(connect_and_send(uri, data_queue, shutdown_event, pending_state))
            break

        except (websockets.exceptions.ConnectionClosedError, ConnectionRefusedError, asyncio.TimeoutError) as e:
            logger.warning(f"WebSocket connection error: {e}. Retrying in {api_config.ws_reconnect_delay}s...")
        except Exception as e:
            logger.warning(f"Unexpected WebSocket error: {e}. Retrying in {api_config.ws_reconnect_delay}s...")

        if shutdown_event.is_set():
            unsent = data_queue.qsize() + (pending_state[0] is not None)
            logger.error(f"Shutdown while disconnected, {unsent} measurements were not sent.")
            break

        shutdown_event.wait(timeout=api_config.ws_reconnect_delay)

    logger.info("WebSocket sender thread shutting down.")


async def connect_and_send(uri: str, data_queue: queue.Queue, shutdown_event: threading.Event, pending_state: list):
    async with websockets.connect(uri, ping_interval=10, ping_timeout=10) as websocket:
        logger.info(f"WebSocket connected to {uri}")

        if pending_state[0]:
            logger.info("Sending pending measurement...")
            await websocket.send(pending_state[0].model_dump_json())
            pending_state[0] = None
            data_queue.task_done()

        while True:
            try:
                measurement: AddMeasurementRequest = await asyncio.to_thread(data_queue.get, timeout=1.0)
            except queue.Empty:
                if shutdown_event.is_set():
                    break
                continue

            pending_state[0] = measurement
            await websocket.send(measurement.model_dump_json())
            pending_state[0] = None
            data_queue.task_done()

    logger.info("WebSocket connection closed after draining the queue.")
