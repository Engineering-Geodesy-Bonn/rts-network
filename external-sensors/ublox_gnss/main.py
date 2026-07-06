import os
import queue
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
    
    return {"itow": unpacked[4], "ecefX": unpacked[5] + unpacked[8] / 100, "ecefY": unpacked[6] + unpacked[9] / 100, "ecefZ": unpacked[7] + unpacked[10] / 100}


def combine_to_dto(pvt_data: dict, hp_data: dict) -> AddExternalSensorMeasurementRequest:
    return AddExternalSensorMeasurementRequest(
        t=pvt_data["itow"] / 1000.0,
        x=hp_data["ecefX"],
        y=hp_data["ecefY"],
        z=hp_data["ecefZ"],
        vx=pvt_data["velN"],
        vy=pvt_data["velE"],
        vz=pvt_data["velD"],
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
                    itow = message.iTOW
                    if itow not in epoch_data:
                        epoch_data[itow] = {}
                    epoch_data[itow]["PVT"] = {
                        "itow": message.iTOW,
                        "velN": message.velN / 1000.0,
                        "velE": message.velE / 1000.0,
                        "velD": message.velD / 1000.0,
                    }
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

    except KeyboardInterrupt:
        print("\nKeyboard interrupt received. Shutting down...")
    except serial.SerialException as e:
        print(f"Failed to open serial port {UBLOX_DEVICE_PATH}: {e}")
    except Exception as e:
        print(f"Error in main loop: {e}")
    finally:
        print("Signaling sender thread to shut down...")
        shutdown_event.set()

        # Wait for the queue to be empty
        if not measurement_queue.empty():
            print(f"Waiting for measurement queue to drain ({measurement_queue.qsize()} items left)...")
            measurement_queue.join()

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