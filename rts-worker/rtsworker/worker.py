import os
import time
import logging
from typing import Callable, Dict

import serial

from rtsworker import api
from rtsworker.dtos import CreateRTSRequest, DeviceResponse, RTSJobResponse, RTSJobStatus, RTSJobType
from rtsworker.pygeocom import PyGeoCom

logger = logging.getLogger("root")

SLEEP_TIME = 1

DEFAULT_EXTERNAL_DELAY = 95 / 1000
INTERNAL_DELAY_DICT = {"MS60": 0.0, "TS16": 7.22 / 1000, "TS60": 4.98 / 1000}


def get_rts_type_from_name(name: str) -> str:
    for key in INTERNAL_DELAY_DICT.keys():
        if key in name:
            return key
    return "MS60"


class Worker:

    def __init__(self, task_mapping: Dict[RTSJobType, Callable[[RTSJobResponse], None]]):
        self.task_mapping = task_mapping
        self.initialize()

    def initialize(self):
        try:
            device_response = api.self_register()
            self.scan_serial_ports(device_response)
        except Exception as e:
            logger.error(f"Initialization failed: {e}")

    def scan_serial_ports(self, device_response: DeviceResponse):
        if os.name == "nt":
            ports = [f"COM{i + 1}" for i in range(15)]
        else:
            ports = [f"/dev/ttyUSB{i}" for i in range(5)]

        baudrates_to_test = [115200, 230400, 9600, 19200, 38400, 57600, 460800, 921600]
        discovered_rts = []
        for port in ports:
            for baudrate in baudrates_to_test:
                try:
                    ser = serial.Serial(
                        port=port,
                        baudrate=baudrate,
                        timeout=1,
                        parity=serial.PARITY_NONE,
                        stopbits=serial.STOPBITS_ONE,
                        bytesize=serial.EIGHTBITS,
                    )
                    rts = PyGeoCom(ser, debug=False)
                    response = rts.get_software_version()
                    rts_name = rts.get_instrument_name()
                    logger.info(f"Discovered RTS {rts_name} on port {port}: {response}")
                    discovered_rts.append(port)
                    ser.close()
                    rts_type = get_rts_type_from_name(rts_name)
                    internal_delay = INTERNAL_DELAY_DICT[rts_type]
                    create_rts_request = CreateRTSRequest(
                        name=rts_name,
                        port=port,
                        baudrate=baudrate,
                        device_id=device_response.id,
                        external_delay=DEFAULT_EXTERNAL_DELAY,
                        internal_delay=internal_delay,
                    )
                    api.create_rts(create_rts_request)
                    break  # Exit baudrate loop if successful
                except Exception:
                    pass

    def _run_task(self, job: RTSJobResponse):
        try:
            task = self.task_mapping[job.job_type]
            task(job)
        except Exception as e:
            api.update_job_status(job.job_id, RTSJobStatus.FAILED)
            logger.error(e)

    def run(self):
        while True:
            try:
                job = api.fetch_new_job()

                if job is None:
                    logger.info("No job found")
                    time.sleep(SLEEP_TIME)
                    continue

                logger.info(f"Found job: {job.job_id}")
                # Reserving the job
                api.update_job_status(
                    job.job_id, RTSJobStatus.RUNNING
                )  # try it but do not set the job on failed if it fails
                self._run_task(job)

            except KeyboardInterrupt:
                break
            except Exception as e:
                logger.error(e)
            finally:
                time.sleep(SLEEP_TIME)
