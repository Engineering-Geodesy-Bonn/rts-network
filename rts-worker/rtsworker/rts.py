import serial
from rtsworker.dtos import RTSResponse
from rtsworker.pygeocom import PyGeoCom


class RTSSerialConnection:
    def __init__(self, rts_connection: RTSResponse) -> None:
        self.rts_connection = rts_connection

    def __enter__(self):
        self.ser = serial.Serial(
            port=self.rts_connection.port,
            baudrate=self.rts_connection.baudrate,
            timeout=self.rts_connection.timeout,
            parity=self.rts_connection.parity,
            stopbits=self.rts_connection.stopbits,
            bytesize=self.rts_connection.bytesize,
        )
        rts = PyGeoCom(self.ser, debug=False)
        return rts

    def __exit__(self, exc_type, exc_value, traceback):
        if self.ser is None:
            print("Serial port was never opened!")
            return
        self.ser.reset_input_buffer()
        self.ser.reset_output_buffer()
        self.ser.close()
        print("Serial port closed")
