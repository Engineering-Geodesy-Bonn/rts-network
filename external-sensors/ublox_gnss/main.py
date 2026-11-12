import math
import os
import queue
import time
from datetime import datetime, timezone
import struct
import threading
import asyncio
import serial
import websockets
import json
from pyubx2 import UBXReader
from pydantic import BaseModel

UBLOX_DEVICE_PATH = os.getenv("UBLOX_DEVICE_PATH", "/dev/ttyACM0")
UBLOX_BAUDRATE = int(os.getenv("UBLOX_BAUDRATE", 460800))

API_HOST = os.getenv("API_HOST", "192.168.0.101")
API_PORT = os.getenv("API_PORT", 8000)
API_URL = f"http://{API_HOST}:{API_PORT}"
WEBSOCKET_URL = f"ws://{API_HOST}:{API_PORT}/ws/external_sensors"
WS_RECONNECT_DELAY = 5
TIMEOUT = 5

class AddExternalSensorMeasurementRequest(BaseModel):
    t: float
    x: float
    y: float
    z: float
    vx: float
    vy: float
    vz: float
    epsg: int = 0

    

def parse_ubx_bytes(data):
    # 1. Prüfen, ob es sich um einen gültigen UBX-Header handelt (B5 62)
    if data[0:2] != b'\xb5\x62':
        raise ValueError("Ungültiger UBX-Header")
        
    # 2. Payload extrahieren (Länge steht an Byte 4-5)
    payload_length = struct.unpack('<H', data[4:6])[0]
    payload = data[6 : 6 + payload_length]
    
    # 3. Format-String für struct.unpack (Little-Endian)
    # B: version (1B), 3B: reserved0 (3B), I: iTOW (4B), i: ecefX/Y/Z (je 4B), b: Hp-Werte (je 1B)
    unpack_format = '<B 3B I i i i b b b'
    
    # Die ersten 23 Bytes der Payload entpacken
    unpacked = struct.unpack(unpack_format, payload[:23])
    
    # ecefX/Y/Z in cm, the high precision parts in 0.1 mm: converted to m (EPSG:4978)
    return {
        "itow": unpacked[4],
        "ecefX": (unpacked[5] + unpacked[8] / 100) / 100,
        "ecefY": (unpacked[6] + unpacked[9] / 100) / 100,
        "ecefZ": (unpacked[7] + unpacked[10] / 100) / 100,
    }


def ned_to_ecef(lat_deg: float, lon_deg: float, v_n: float, v_e: float, v_d: float) -> tuple[float, float, float]:
    """Rotates a velocity from the local north/east/down frame into ECEF."""
    lat, lon = math.radians(lat_deg), math.radians(lon_deg)
    sin_lat, cos_lat, sin_lon, cos_lon = math.sin(lat), math.cos(lat), math.sin(lon), math.cos(lon)
    return (
        -sin_lat * cos_lon * v_n - sin_lon * v_e - cos_lat * cos_lon * v_d,
        -sin_lat * sin_lon * v_n + cos_lon * v_e - cos_lat * sin_lon * v_d,
        cos_lat * v_n - sin_lat * v_d,
    )


def utc_timestamp(message) -> float | None:
    """Unix time of a NAV-PVT epoch, None while the receiver has no valid UTC date and time."""
    if not (message.validDate and message.validTime and message.fullyResolved):
        return None
    t = datetime(message.year, message.month, message.day, message.hour, message.min, message.second, tzinfo=timezone.utc)
    return t.timestamp() + message.nano * 1e-9  # nano may be negative


def combine_to_dto(pvt_data: dict, hp_data: dict) -> AddExternalSensorMeasurementRequest:
    return AddExternalSensorMeasurementRequest(
        t=pvt_data["t"],
        x=hp_data["ecefX"],
        y=hp_data["ecefY"],
        z=hp_data["ecefZ"],
        vx=pvt_data["vx"],
        vy=pvt_data["vy"],
        vz=pvt_data["vz"],
        epsg=4978
    )

def websocket_sender(data_queue: queue.Queue, shutdown_event: threading.Event):
    pending_state = [None]

    while not shutdown_event.is_set():
        try:
            print(f"Attempting WebSocket connection to {WEBSOCKET_URL}...")
            asyncio.run(connect_and_send(WEBSOCKET_URL, data_queue, shutdown_event, pending_state))
            break

        except (websockets.exceptions.ConnectionClosedError, ConnectionRefusedError, asyncio.TimeoutError) as e:
            print(f"WebSocket connection error: {e}. Retrying in {WS_RECONNECT_DELAY}s...")
        except Exception as e:
            print(f"Unexpected WebSocket error: {e}. Retrying in {WS_RECONNECT_DELAY}s...")

        shutdown_event.wait(timeout=WS_RECONNECT_DELAY)

    print("WebSocket sender thread shutting down.")


async def connect_and_send(uri: str, data_queue: queue.Queue, shutdown_event: threading.Event, pending_state: list):
    async with websockets.connect(uri, ping_interval=10, ping_timeout=10) as websocket:
        print(f"WebSocket connected to {uri}")

        if pending_state[0]:
            print("Sending pending measurement...")
            await websocket.send(json.dumps(pending_state[0]))
            pending_state[0] = None
            data_queue.task_done()
            print("Pending measurement sent.")

        while not shutdown_event.is_set():
            try:
                measurement = await asyncio.to_thread(data_queue.get, timeout=1.0)
                pending_state[0] = measurement
                await websocket.send(json.dumps(measurement))
                pending_state[0] = None

                data_queue.task_done()

            except queue.Empty:
                continue
            except websockets.exceptions.ConnectionClosed:
                print("WebSocket connection closed during send.")
                raise

    if shutdown_event.is_set():
        print("WebSocket connection closing due to shutdown signal.")
    else:
        print("WebSocket connection closed unexpectedly.")

def post_ublox_positions():
    measurement_queue = queue.Queue()
    shutdown_event = threading.Event()

    sender_thread = threading.Thread(
        target=websocket_sender,
        args=(measurement_queue, shutdown_event),
        daemon=True,
    )
    sender_thread.start()


    try:
        # open serial port
        with serial.Serial(UBLOX_DEVICE_PATH, UBLOX_BAUDRATE, timeout=1) as ublox_device:
            ubr = UBXReader(ublox_device, protfilter=2)
            epoch_data = {}

            while not shutdown_event.is_set():
                try:
                    # Read binary data from the u-blox device
                    binary_data, message = ubr.read()
                except serial.SerialException as e:
                    print(f"Serial port error: {e}")
                    break

                if message is None:
                    continue  # Skip if no message is read

                itow = None
                if message.identity == 'NAV-PVT':
                    t = utc_timestamp(message)
                    if t is None:
                        continue  # no valid UTC time yet: positions could not be synchronized
                    itow = message.iTOW
                    if itow not in epoch_data:
                        epoch_data[itow] = {}
                    vx, vy, vz = ned_to_ecef(message.lat, message.lon, message.velN / 1000.0, message.velE / 1000.0, message.velD / 1000.0)
                    epoch_data[itow]["PVT"] = {"itow": message.iTOW, "t": t, "vx": vx, "vy": vy, "vz": vz}
                elif message.identity == 'NAV-HPPOSECEF':
                    itow = message.iTOW
                    if itow not in epoch_data:
                        epoch_data[itow] = {}
                    epoch_data[itow]["HP"] = parse_ubx_bytes(binary_data)

                if itow is not None and "PVT" in epoch_data.get(itow, {}) and "HP" in epoch_data.get(itow, {}):
                    pvt_data = epoch_data[itow]["PVT"]
                    hp_data = epoch_data[itow]["HP"]
                    position = combine_to_dto(pvt_data, hp_data)
                    measurement_queue.put(position.model_dump())
                    epoch_data.pop(itow, None)
                # epochs of which only one message arrived are never completed
                for old in [k for k in epoch_data if itow is not None and k < itow]:
                    del epoch_data[old]

    except KeyboardInterrupt:
        print("\nKeyboard interrupt received. Shutting down...")
    except serial.SerialException as e:
        print(f"Failed to open serial port {UBLOX_DEVICE_PATH}: {e}")
    except Exception as e:
        print(f"Error in main loop: {e}")
    finally:
        # Give the sender a few seconds to drain the queue (it stops sending once shutdown is set)
        deadline = time.time() + 5.0
        if not measurement_queue.empty():
            print(f"Waiting for measurement queue to drain ({measurement_queue.qsize()} items left)...")
        while not measurement_queue.empty() and time.time() < deadline and sender_thread.is_alive():
            time.sleep(0.1)
        if not measurement_queue.empty():
            print(f"{measurement_queue.qsize()} measurements were not sent.")
        print("Signaling sender thread to shut down...")
        shutdown_event.set()

        sender_thread.join(timeout=10.0)  # Wait for thread to exit
        if sender_thread.is_alive():
            print("Warning: Sender thread did not shut down cleanly.")
        else:
            print("Sender thread shut down. Exiting.")



def main():
    try:
        post_ublox_positions()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()