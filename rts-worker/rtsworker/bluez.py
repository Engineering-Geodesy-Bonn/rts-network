"""Bluetooth scan through the Bluetooth service of the host (BlueZ over the system D-Bus).

The worker container needs the D-Bus socket of the host (see docker-compose.yaml). Only the
scan uses BlueZ; connections to instruments are plain RFCOMM sockets (rtsworker.bluetooth).
"""

import logging
import os
import time
from collections.abc import Callable

from jeepney import DBusAddress, DBusErrorResponse, new_method_call
from jeepney.io.blocking import open_dbus_connection

logger = logging.getLogger(__name__)

BUS_SOCKET = "/run/dbus/system_bus_socket"
BLUEZ = "org.bluez"


class BluetoothUnavailable(RuntimeError):
    pass


def _value(variant):
    return variant[1] if isinstance(variant, tuple) and len(variant) == 2 else variant


class BlueZ:
    def __init__(self):
        if "DBUS_SYSTEM_BUS_ADDRESS" not in os.environ and not os.path.exists(BUS_SOCKET):
            raise BluetoothUnavailable(
                "No access to the Bluetooth service of the Raspberry Pi: the worker container needs "
                f"the volume {BUS_SOCKET} (see docker-compose.yaml of the worker)"
            )
        try:
            self.conn = open_dbus_connection(bus="SYSTEM")
        except OSError as e:
            raise BluetoothUnavailable(f"System D-Bus not reachable: {e}") from e

    def close(self) -> None:
        self.conn.close()

    def __enter__(self) -> "BlueZ":
        return self

    def __exit__(self, *exc) -> None:
        self.close()

    def _call(self, path: str, interface: str, method: str, signature: str | None = None, body: tuple = ()):
        message = new_method_call(DBusAddress(path, bus_name=BLUEZ, interface=interface), method, signature, body)
        try:
            return self.conn.send_and_get_reply(message, timeout=10).body
        except DBusErrorResponse as e:
            if e.name == "org.freedesktop.DBus.Error.ServiceUnknown":
                raise BluetoothUnavailable("The Bluetooth service (bluetoothd) is not running on the Raspberry Pi") from e
            if e.name == "org.freedesktop.DBus.Error.AccessDenied":
                raise BluetoothUnavailable("Access to the Bluetooth service denied: the worker must run as root") from e
            raise

    def objects(self) -> dict:
        (objects,) = self._call("/", "org.freedesktop.DBus.ObjectManager", "GetManagedObjects")
        return objects

    def adapter(self) -> str:
        """Path of the first Bluetooth adapter, powered on if necessary."""
        adapters = sorted(path for path, ifaces in self.objects().items() if "org.bluez.Adapter1" in ifaces)
        if not adapters:
            raise BluetoothUnavailable("This Raspberry Pi has no Bluetooth adapter (or it is blocked: rfkill unblock bluetooth)")
        path = adapters[0]
        powered = _value(self.objects()[path]["org.bluez.Adapter1"].get("Powered"))
        if not powered:
            logger.info("Switching on the Bluetooth adapter %s", path)
            try:
                self._call(path, "org.freedesktop.DBus.Properties", "Set", "ssv", ("org.bluez.Adapter1", "Powered", ("b", True)))
            except DBusErrorResponse as e:
                raise BluetoothUnavailable(f"Bluetooth adapter cannot be switched on ({e.name}): rfkill unblock bluetooth") from e
        return path

    def devices(self, adapter: str, seen_only: bool) -> list[dict]:
        """Classic Bluetooth devices of the adapter. seen_only: found by the running scan
        (BlueZ only keeps RSSI for those) or paired."""
        result = []
        for path, ifaces in self.objects().items():
            device = ifaces.get("org.bluez.Device1")
            if device is None or not path.startswith(adapter + "/"):
                continue
            props = {k: _value(v) for k, v in device.items()}
            rssi, paired = props.get("RSSI"), bool(props.get("Paired"))
            if seen_only and rssi is None and not paired:
                continue
            address = str(props.get("Address", "")).upper()
            name = props.get("Name")
            result.append({
                "address": address,
                # BlueZ shows the address as name until the real name is known
                "name": name if name and name.replace("-", ":").upper() != address else None,
                "rssi": int(rssi) if rssi is not None else None,
                "paired": paired,
            })
        return result

    def scan(self, duration: float, on_update: Callable[[list[dict]], None] | None = None) -> list[dict]:
        adapter = self.adapter()
        self._call(adapter, "org.bluez.Adapter1", "SetDiscoveryFilter", "a{sv}", ({"Transport": ("s", "bredr")},))
        try:
            self._call(adapter, "org.bluez.Adapter1", "StartDiscovery")
        except DBusErrorResponse as e:
            if e.name != "org.bluez.Error.InProgress":  # someone else is scanning: use their results
                raise
        found: list[dict] = []
        try:
            end = time.time() + duration
            while time.time() < end:
                time.sleep(1.0)
                found = self.devices(adapter, seen_only=True)
                if on_update:
                    on_update(found)
        finally:
            try:
                self._call(adapter, "org.bluez.Adapter1", "StopDiscovery")
            except DBusErrorResponse:
                pass
        return found
