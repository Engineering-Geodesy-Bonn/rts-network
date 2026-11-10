class ApiException(Exception):
    status_code = 500

    def __init__(self, message: str):
        super().__init__(message)
        self.message = message


class NotFound(ApiException):
    status_code = 404


class Conflict(ApiException):
    status_code = 409


class BadRequest(ApiException):
    status_code = 400
