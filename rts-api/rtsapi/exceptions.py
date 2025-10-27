class RTSPortAlreadyExistsException(Exception):
    def __init__(self, port: str):
        super().__init__(f"Conflict: RTS with port {port} already exists")


class RTSNotFoundException(Exception):
    def __init__(self, rts_id: int):
        super().__init__(f"Not Found: RTS with id {rts_id} does not exist")


class RTSJobNotFoundException(Exception):
    def __init__(self, job_id: int):
        super().__init__(f"Not Found: RTS Job with id {job_id} does not exist")


class TrackingSettingsNotFoundException(Exception):
    def __init__(self, rts_id: int):
        super().__init__(f"Not Found: Tracking settings for RTS with id {rts_id} do not exist")


class RTSJobStatusChangeException(Exception):
    def __init__(self, job_id: int, current_status: str, new_status: str):
        super().__init__(
            f"Conflict: Cannot change status of RTS Job with id {job_id} from {current_status} to {new_status}"
        )


class DeviceNotFoundException(Exception):
    def __init__(self, device_id: int):
        super().__init__(f"Not Found: Device with id {device_id} does not exist")


class NoOverlapException(Exception):
    def __init__(self):
        super().__init__("Both RTS measurements must have overlapping timestamps")


class NoMeasurementsAvailableException(Exception):
    def __init__(self, message: str):
        super().__init__(message)
