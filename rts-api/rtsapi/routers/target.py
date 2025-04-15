from fastapi import APIRouter, Depends

from rtsapi.dtos import TargetPosition
from rtsapi.services.target_service import TargetService

router = APIRouter(tags=["Target"])


@router.get("/target")
async def get_target_position(target_service: TargetService = Depends(TargetService)) -> TargetPosition:
    return target_service.get_latest_target_position()
