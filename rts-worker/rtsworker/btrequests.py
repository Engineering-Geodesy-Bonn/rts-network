"""Bluetooth requests of the dashboard, handed to this worker with the reply to a heartbeat.

- scan: search for classic Bluetooth devices for a few seconds, reporting what was found every second
- identify: connect to an instrument and find the RFCOMM channel that answers GeoCOM

Each request runs in its own thread so that heartbeats and jobs continue.
"""

import logging
import threading

from rtsworker import bluetooth
from rtsworker.bluez import BlueZ
from rtsworker.state import STATE

logger = logging.getLogger(__name__)


def _bluetooth_name(address: str) -> str | None:
    """Name of the device as known to BlueZ (from the last scan), best effort."""
    try:
        with BlueZ() as bluez:
            for device in bluez.devices(bluez.adapter(), seen_only=False):
                if device["address"] == address:
                    return device["name"]
    except Exception as e:
        logger.debug("Bluetooth name of %s unknown: %r", address, e)
    return None


def run(client, request: dict) -> None:
    request_id, kind = request["id"], request["kind"]

    def report(status: str, **data) -> None:
        try:
            client.bluetooth_update(request_id, STATE.worker_id, {"status": status, **data})
        except Exception as e:
            logger.warning("Cannot report Bluetooth %s %s: %r", kind, status, e)

    logger.info("Bluetooth %s requested by the dashboard", kind)
    try:
        if kind == "scan":
            with BlueZ() as bluez:
                found = bluez.scan(request.get("duration") or 10.0, lambda f: report("running", found=f))
            report("done", found=found)
            logger.info("Bluetooth scan found %d devices", len(found))
        elif kind == "identify":
            address = request["address"]
            found = bluetooth.identify(address, request.get("channel"), log=logger.info)
            if found is None:
                report("failed", error="The instrument answers, but no channel speaks GeoCOM: set GeoCOM to Bluetooth (TS Bluetooth 1) on the instrument")
                return
            report("done", instrument={**found, "name": _bluetooth_name(address)})
        else:
            report("failed", error=f"Unknown request {kind}")
    except Exception as e:
        logger.warning("Bluetooth %s failed: %s", kind, e)
        report("failed", error=str(e))


def start(client, requests: list[dict]) -> None:
    for request in requests:
        threading.Thread(target=run, args=(client, request), name=f"bluetooth-{request['kind']}", daemon=True).start()
