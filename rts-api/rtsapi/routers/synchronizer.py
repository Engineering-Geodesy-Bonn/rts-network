from uuid import UUID

from fastapi import APIRouter, Depends

from rtsapi.dtos import SensorRolesResponse, SynchronizerStateResponse
from rtsapi.services.synchronizer_service import SynchronizerService

router = APIRouter(tags=["Synchronizer"])


@router.put("/synchronizer/roles", status_code=204)
def set_sensor_roles(
    primary_sensor_id: UUID | None = None,
    secondary_sensor_id: UUID | None = None,
    synchronizer_service: SynchronizerService = Depends(SynchronizerService),
) -> None:
    synchronizer_service.set_sensor_roles(primary_sensor_id, secondary_sensor_id)


@router.get("/synchronizer/roles", status_code=200)
def get_sensor_roles(
    synchronizer_service: SynchronizerService = Depends(SynchronizerService),
) -> SensorRolesResponse:
    return synchronizer_service.get_sensor_roles()


@router.get("/synchronizer/state", status_code=200)
def get_synchronizer_state(
    synchronizer_service: SynchronizerService = Depends(SynchronizerService),
) -> SynchronizerStateResponse:
    return synchronizer_service.get_state()


@router.patch("/synchronizer/reset", status_code=204)
def reset_synchronizer(
    synchronizer_service: SynchronizerService = Depends(SynchronizerService),
) -> None:
    synchronizer_service.reset()
