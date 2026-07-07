from uuid import UUID

from fastapi import APIRouter, Depends

from rtsapi.dtos import CreateSessionRequest, SessionResponse
from rtsapi.services.session_service import SessionService

router = APIRouter(tags=["Session"])


@router.get(
    "/session",
    response_model=list[SessionResponse],
    summary="List all sessions.",
    response_description="A list of sessions.",
    responses={
        200: {"description": "Successfully retrieved sessions."},
        500: {"description": "Internal server error."},
    },
)
async def get_all_sessions(
    session_service: SessionService = Depends(SessionService),
) -> list[SessionResponse]:
    return session_service.get_sessions()


@router.post(
    "/session",
    response_model=SessionResponse,
    summary="Create session.",
    response_description="Created session.",
    responses={
        200: {"description": "Successfully created session."},
        500: {"description": "Internal server error."},
    },
)
async def create_session(
    create_session_request: CreateSessionRequest,
    session_service: SessionService = Depends(SessionService),
) -> SessionResponse:
    return session_service.create_session(create_session_request)


@router.get(
    "/session/{session_id}",
    response_model=SessionResponse,
    summary="Get session with ID.",
    response_description="Requested session.",
    responses={
        200: {"description": "Successfully retrieved session."},
        404: {"description": "Requested session does not exist."},
        500: {"description": "Internal server error."},
    },
)
async def get_session(
    session_id: UUID,
    session_service: SessionService = Depends(SessionService),
) -> SessionResponse:
    return session_service.get_session(session_id)


@router.delete(
    "/session/{session_id}",
    status_code=204,
    summary="Delete session with ID.",
    response_description="No content.",
    responses={
        204: {"description": "Successfully deleted session."},
        404: {"description": "Requested session does not exist."},
        500: {"description": "Internal server error."},
    },
)
async def delete_session(
    session_id: UUID,
    session_service: SessionService = Depends(SessionService),
) -> None:
    return session_service.delete_session(session_id)
