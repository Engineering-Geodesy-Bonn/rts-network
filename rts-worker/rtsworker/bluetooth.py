"""GeoCOM over Bluetooth SPP (RFCOMM), e.g. to a Leica TS20.

A port of the form `bt://<address>[/<channel>]` (e.g. `bt://00:11:22:33:44:55/1`) selects a
Bluetooth connection. It uses the RFCOMM sockets of the Linux kernel (BlueZ), so neither
`rfcomm bind` nor an extra Python package is needed. The instrument must be paired with the
Raspberry Pi once (see README). In Docker the container needs host networking: the kernel only
allows Bluetooth sockets in the host network namespace.

Find the RFCOMM channel of the GeoCOM interface with

    python -m rtsworker.bluetooth <address>

which tries the channels one by one and asks each for the instrument name.
"""

import errno
import logging
import re
import socket
import sys
import time

logger = logging.getLogger(__name__)

PREFIX = "bt://"
DEFAULT_CHANNEL = 1
CONNECT_TIMEOUT = 15.0  # s, paging a sleeping instrument can take several seconds
CONNECT_ATTEMPTS = 3
_ADDRESS = re.compile(r"^[0-9A-F]{2}(:[0-9A-F]{2}){5}$")

# Hints for the errors that typically occur, shown in the dashboard when a job fails
_HINTS = {
    errno.EHOSTDOWN: "instrument switched off, out of range or its Bluetooth is disabled",
    errno.EHOSTUNREACH: "instrument switched off, out of range or its Bluetooth is disabled",
    errno.ECONNREFUSED: "no GeoCOM service on this channel: check the channel and that GeoCOM uses Bluetooth on the instrument",
    errno.EACCES: "not paired: pair the instrument with the Raspberry Pi (bluetoothctl)",
    errno.ECONNRESET: "connection rejected: pair and trust the instrument with the Raspberry Pi (bluetoothctl)",
    errno.EBUSY: "already connected, probably used by another job",
}
_NO_RETRY = {errno.ECONNREFUSED, errno.EACCES, errno.EBUSY}


def is_bluetooth_port(port: str) -> bool:
    return port.startswith(PREFIX)


def parse_port(port: str) -> tuple[str, int]:
    """`bt://00:11:22:33:44:55/1` -> ("00:11:22:33:44:55", 1); the channel defaults to 1."""
    address, _, channel = port[len(PREFIX):].strip().partition("/")
    address = address.upper().replace("-", ":")
    if not _ADDRESS.match(address):
        raise ValueError(f"Invalid Bluetooth address in port {port!r}, expected bt://00:11:22:33:44:55[/channel]")
    try:
        number = int(channel) if channel else DEFAULT_CHANNEL
    except ValueError:
        raise ValueError(f"Invalid RFCOMM channel in port {port!r}") from None
    if not 1 <= number <= 30:
        raise ValueError(f"RFCOMM channel must be between 1 and 30, got {number}")
    return address, number


class RfcommStream:
    """The part of serial.Serial that PyGeoCom uses, on a connected RFCOMM socket."""

    in_waiting = 0  # PyGeoCom then reads with read(1), which returns all bytes available

    def __init__(self, sock: socket.socket):
        self.sock = sock

    def write(self, data: bytes) -> int:
        self.sock.sendall(data)
        return len(data)

    def read(self, size: int = 1) -> bytes:
        """Blocks until data arrives; b"" on timeout (as serial.Serial)."""
        try:
            data = self.sock.recv(max(size, 4096))
        except TimeoutError:
            return b""
        if not data:
            raise ConnectionError("Bluetooth connection closed by the instrument")
        return data

    def reset_input_buffer(self) -> None:
        """Discards bytes left over from an earlier session."""
        timeout = self.sock.gettimeout()
        self.sock.setblocking(False)
        try:
            while self.sock.recv(4096):
                pass
        except (BlockingIOError, InterruptedError):
            pass
        finally:
            self.sock.settimeout(timeout)

    def close(self) -> None:
        self.sock.close()


def _describe(e: OSError, address: str, channel: int) -> str:
    hint = _HINTS.get(e.errno)
    return f"Bluetooth connection to {address} channel {channel} failed: {e.strerror or e}" + (f" ({hint})" if hint else "")


def connect(address: str, channel: int, timeout: float, attempts: int = CONNECT_ATTEMPTS) -> RfcommStream:
    """Connects to the RFCOMM channel. Retries a few times: the first page of an instrument
    that has just been switched on or was idle often fails."""
    if not hasattr(socket, "AF_BLUETOOTH"):
        raise ConnectionError("This Python has no Bluetooth socket support (needs Linux and Python built with BlueZ headers)")
    last: OSError | None = None
    for attempt in range(1, attempts + 1):
        sock = socket.socket(socket.AF_BLUETOOTH, socket.SOCK_STREAM, socket.BTPROTO_RFCOMM)
        sock.settimeout(CONNECT_TIMEOUT)
        try:
            sock.connect((address, channel))
        except OSError as e:
            sock.close()
            if e.errno == errno.EAFNOSUPPORT:
                raise ConnectionError(
                    "Bluetooth sockets are not available: run the container with host networking "
                    "and make sure the Bluetooth service of the host is running"
                ) from e
            last = e
            logger.warning("%s (attempt %d of %d)", _describe(e, address, channel), attempt, attempts)
            if e.errno in _NO_RETRY:
                break
            time.sleep(1.0)
            continue
        sock.settimeout(timeout)
        logger.info("Bluetooth connection to %s channel %d established", address, channel)
        return RfcommStream(sock)
    if isinstance(last, TimeoutError):
        raise ConnectionError(f"Bluetooth connection to {address} channel {channel} timed out (instrument off or out of range?)") from last
    raise ConnectionError(_describe(last, address, channel)) from last


LEICA_CHANNEL = 11  # "TS Bluetooth 1" of Captivate instruments
_UNREACHABLE = (errno.EHOSTDOWN, errno.EHOSTUNREACH, errno.EACCES)


def channel_order(first: int | None = None) -> list[int]:
    """The remembered channel, then Leica's, then all others."""
    order = [c for c in (first, LEICA_CHANNEL) if c]
    return order + [c for c in range(1, 31) if c not in order]


def identify(address: str, first_channel: int | None = None, log=print) -> dict | None:
    """Finds the RFCOMM channel that answers GeoCOM. Returns the instrument (channel, GeoCOM
    name, serial number) or None. Raises ConnectionError if the instrument is not reachable."""
    from rtsworker.pygeocom import PyGeoCom  # the channel helper also runs without the worker dependencies

    for channel in channel_order(first_channel):
        try:
            stream = connect(address, channel, timeout=3.0, attempts=1)
        except ConnectionError as e:
            cause = e.__cause__
            if isinstance(cause, TimeoutError) or getattr(cause, "errno", None) in _UNREACHABLE:
                raise  # the instrument itself is not reachable: no use trying the other channels
            log(f"channel {channel:2d}: {cause.strerror if isinstance(cause, OSError) and cause.strerror else e}")
            continue
        try:
            stream.reset_input_buffer()
            geocom = PyGeoCom(stream)
            name = geocom.get_instrument_name()
            try:
                serial = geocom.get_instrument_number()
            except Exception:
                serial = None
            log(f"channel {channel:2d}: GeoCOM, instrument {name}")
            return {"address": address, "channel": channel, "instrument_name": name, "serial_number": serial}
        except Exception as e:  # connected, but no (valid) GeoCOM answer: another service
            log(f"channel {channel:2d}: connected, but no GeoCOM answer ({e!r})")
        finally:
            stream.close()
    return None


def main(argv: list[str]) -> int:
    if len(argv) != 1:
        print("usage: python -m rtsworker.bluetooth <bluetooth address>")
        return 2
    logging.basicConfig(level=logging.ERROR)
    address, _ = parse_port(PREFIX + argv[0])
    try:
        found = identify(address)
    except ConnectionError as e:
        print(e)
        return 1
    if found is None:
        print("No channel answered GeoCOM. Is the instrument switched on and is GeoCOM set to Bluetooth?")
        return 1
    print(f"\nUse the port bt://{address}/{found['channel']} for this instrument.")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
