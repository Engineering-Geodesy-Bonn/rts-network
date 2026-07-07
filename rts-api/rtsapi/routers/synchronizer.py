from uuid import UUID

from fastapi import APIRouter, Depends

from rtsapi.dtos import SensorRolesResponse, SynchronizerStateResponse
from rtsapi.services.synchronizer_service import SynchronizerService

router = APIRouter(tags=["Synchronizer"])


@router.put(
    "/synchronizer/roles",
    status_code=204,
    summary="Set synchronizer sensor roles.",
    response_description="No content.",
    responses={
        204: {"description": "Successfully set synchronizer sensor roles."},
        500: {"description": "Internal server error."},
    },
)
def set_sensor_roles(
    primary_sensor_id: UUID | None = None,
    secondary_sensor_id: UUID | None = None,
    synchronizer_service: SynchronizerService = Depends(SynchronizerService),
) -> None:
    synchronizer_service.set_sensor_roles(primary_sensor_id, secondary_sensor_id)


@router.get(
    "/synchronizer/roles",
    response_model=SensorRolesResponse,
    status_code=200,
    summary="Get synchronizer sensor roles.",
    response_description="Current synchronizer sensor roles.",
    responses={
        200: {"description": "Successfully retrieved synchronizer sensor roles."},
        500: {"description": "Internal server error."},
    },
)
def get_sensor_roles(
    synchronizer_service: SynchronizerService = Depends(SynchronizerService),
) -> SensorRolesResponse:
    return synchronizer_service.get_sensor_roles()


@router.get(
    "/synchronizer/state",
    response_model=SynchronizerStateResponse,
    status_code=200,
    summary="Get synchronizer state.",
    response_description="Current synchronizer state.",
    responses={
        200: {"description": "Successfully retrieved synchronizer state."},
        500: {"description": "Internal server error."},
    },
)
def get_synchronizer_state(
    synchronizer_service: SynchronizerService = Depends(SynchronizerService),
) -> SynchronizerStateResponse:
    return synchronizer_service.get_state()


@router.patch(
    "/synchronizer/reset",
    status_code=204,
    summary="Reset synchronizer state.",
    response_description="No content.",
    responses={
        204: {"description": "Successfully reset synchronizer state."},
        500: {"description": "Internal server error."},
    },
)
def reset_synchronizer(
    synchronizer_service: SynchronizerService = Depends(SynchronizerService),
) -> None:
    synchronizer_service.reset()
