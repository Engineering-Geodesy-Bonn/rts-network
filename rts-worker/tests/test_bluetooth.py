import socket
import threading

import pytest

from rtsworker import bluetooth
from rtsworker.bluetooth import RfcommStream, parse_port
from rtsworker.dtos import RTSConfig
from rtsworker.instrument import BluetoothInstrument, SerialInstrument, open_instrument
from rtsworker.pygeocom import PyGeoCom, TMCInclinationMode


def test_parse_port():
    assert parse_port("bt://00:11:22:aa:bb:cc") == ("00:11:22:AA:BB:CC", 1)
    assert parse_port("bt://00-11-22-AA-BB-CC/5") == ("00:11:22:AA:BB:CC", 5)
    for bad in ("bt://00:11:22:AA:BB", "bt://00:11:22:AA:BB:CC/x", "bt://00:11:22:AA:BB:CC/31"):
        with pytest.raises(ValueError):
            parse_port(bad)


def test_open_instrument_selects_bluetooth():
    assert isinstance(open_instrument(RTSConfig(id="a", port="bt://00:11:22:33:44:55/2")), BluetoothInstrument)
    assert isinstance(open_instrument(RTSConfig(id="a", port="/dev/ttyUSB0")), SerialInstrument)


def fake_instrument(sock: socket.socket, answers: dict[bytes, bytes]) -> threading.Thread:
    """Answers GeoCOM requests by RPC number, in two chunks like a radio link."""

    def run():
        buffer = b""
        with sock:
            while True:
                data = sock.recv(1024)
                if not data:
                    return
                buffer += data
                while b"\r\n" in buffer:
                    line, buffer = buffer.split(b"\r\n", 1)
                    line = line.strip()
                    if not line:
                        continue
                    rpc = line.split(b",")[1].split(b":")[0]
                    answer = answers[rpc]
                    sock.sendall(answer[:7])
                    sock.sendall(answer[7:])

    thread = threading.Thread(target=run, daemon=True)
    thread.start()
    return thread


def test_geocom_over_stream():
    ours, theirs = socket.socketpair()
    ours.settimeout(2.0)
    fake_instrument(theirs, {
        b"5004": b'%R1P,0,0:0,"TS20"\r\n',
        b"2167": b"%R1P,0,0:0,1.5,1.4,0,0,0,0,12.345,123456789\r\n",
    })
    stream = RfcommStream(ours)
    stream.reset_input_buffer()
    geocom = PyGeoCom(stream)
    assert geocom.get_instrument_name() == "TS20"
    m = geocom.get_full_measurement(TMCInclinationMode.AUTOMATIC)
    assert (m.h_angle, m.v_angle, m.distance, m.time) == (1.5, 1.4, 12.345, 123456789.0)
    stream.close()


def test_stream_timeout_and_close():
    ours, theirs = socket.socketpair()
    ours.settimeout(0.05)
    stream = RfcommStream(ours)
    assert stream.read() == b""  # timeout, like serial.Serial
    theirs.close()
    with pytest.raises(ConnectionError):
        stream.read()


def test_connect_error_has_hint(monkeypatch):
    class Refusing:
        def __init__(self, *args):
            pass

        def settimeout(self, t):
            pass

        def connect(self, address):
            raise ConnectionRefusedError(111, "Connection refused")

        def close(self):
            pass

    monkeypatch.setattr(bluetooth.socket, "socket", Refusing)
    for name, value in (("AF_BLUETOOTH", 31), ("BTPROTO_RFCOMM", 3)):  # missing in uv's standalone Python
        monkeypatch.setattr(bluetooth.socket, name, value, raising=False)
    with pytest.raises(ConnectionError, match="no GeoCOM service on this channel"):
        bluetooth.connect("00:11:22:33:44:55", 3, timeout=1.0)


def test_channel_order_tries_remembered_and_leica_channel_first():
    assert bluetooth.channel_order()[:2] == [11, 1] and len(bluetooth.channel_order()) == 30
    assert bluetooth.channel_order(5)[:3] == [5, 11, 1] and len(bluetooth.channel_order(5)) == 30


class FakeClient:
    def __init__(self):
        self.updates = []

    def bluetooth_update(self, request_id, worker_id, data):
        self.updates.append((request_id, data))


def test_scan_request_reports_progress_and_result(monkeypatch):
    from rtsworker import btrequests

    seen = [{"address": "F0:B5:D1:5D:FC:6F", "name": "TS885873", "rssi": -31, "paired": False}]

    class FakeBlueZ:
        def __enter__(self):
            return self

        def __exit__(self, *exc):
            pass

        def scan(self, duration, on_update):
            on_update(seen)
            return seen

    monkeypatch.setattr(btrequests, "BlueZ", FakeBlueZ)
    client = FakeClient()
    btrequests.run(client, {"id": "r1", "kind": "scan", "duration": 1})
    assert [u[1]["status"] for u in client.updates] == ["running", "done"]
    assert client.updates[-1][1]["found"] == seen


def test_identify_request(monkeypatch):
    from rtsworker import btrequests

    calls = []

    def fake_identify(address, channel, log):
        calls.append((address, channel))
        return {"address": address, "channel": 11, "instrument_name": "MS60", "serial_number": 885873}

    monkeypatch.setattr(btrequests.bluetooth, "identify", fake_identify)
    monkeypatch.setattr(btrequests, "_bluetooth_name", lambda a: "TS885873")
    client = FakeClient()
    btrequests.run(client, {"id": "r2", "kind": "identify", "address": "F0:B5:D1:5D:FC:6F", "channel": 11})
    assert calls == [("F0:B5:D1:5D:FC:6F", 11)]
    assert client.updates == [("r2", {"status": "done", "instrument": {
        "address": "F0:B5:D1:5D:FC:6F", "channel": 11, "instrument_name": "MS60", "serial_number": 885873, "name": "TS885873"}})]

    monkeypatch.setattr(btrequests.bluetooth, "identify", lambda *a, **k: (_ for _ in ()).throw(ConnectionError("Host is down")))
    btrequests.run(client, {"id": "r3", "kind": "identify", "address": "F0:B5:D1:5D:FC:6F"})
    assert client.updates[-1] == ("r3", {"status": "failed", "error": "Host is down"})
