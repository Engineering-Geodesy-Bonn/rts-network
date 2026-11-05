from uuid import UUID

from fastapi import APIRouter, Depends

from rtsapi.dtos import StatusBoardResponse
from rtsapi.services.status_service import StatusService

router = APIRouter(tags=["Status"])


@router.get(
    "/status",
    response_model=StatusBoardResponse,
    summary="Evaluate the health of the whole RTS network.",
    response_description="Status board with checks for the network, devices, RTS and external sensors.",
    responses={
        200: {"description": "Successfully evaluated the status board."},
        500: {"description": "Internal server error."},
    },
)
def get_status(
    session_id: UUID | None = None,
    status_service: StatusService = Depends(StatusService),
) -> StatusBoardResponse:
    return status_service.get_status_board(session_id)
