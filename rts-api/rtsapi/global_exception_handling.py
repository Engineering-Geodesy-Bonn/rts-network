import logging

from fastapi import Request
from fastapi.responses import JSONResponse
from pydantic import ValidationError

from rtsapi.exceptions import (DeviceNotFoundException, NoOverlapException,
                               RTSJobNotFoundException,
                               RTSJobStatusChangeException,
                               RTSNotFoundException,
                               RTSPortAlreadyExistsException,
                               TrackingSettingsNotFoundException)

logger = logging.getLogger("root")

EXCEPTION_MAPPING = {
    RTSNotFoundException: 404,
    RTSJobNotFoundException: 404,
    RTSPortAlreadyExistsException: 409,
    TrackingSettingsNotFoundException: 404,
    RTSJobStatusChangeException: 409,
    DeviceNotFoundException: 404,
    PermissionError: 500,
    NoOverlapException: 400,
    ValidationError: 400,
}


async def catch_exceptions_middleware(request: Request, call_next):
    try:
        logger.info(f"Request: {request.method} {request.url}")
        return await call_next(request)
    except Exception as e:

        return JSONResponse(
            status_code=EXCEPTION_MAPPING.get(type(e), 500),
            content={"message": str(e)},
        )
