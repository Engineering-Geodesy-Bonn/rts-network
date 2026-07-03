from uuid import UUID

from fastapi import APIRouter, Depends

from rtsapi.dtos import CreateSessionRequest, SessionResponse
from rtsapi.services.session_service import SessionService

router = APIRouter(tags=["Session"])


@router.get("/session", response_model=list[SessionResponse])
async def get_all_sessions(
    session_service: SessionService = Depends(SessionService),
) -> list[SessionResponse]:
    return session_service.get_sessions()


@router.post("/session", response_model=SessionResponse)
async def create_session(
    create_session_request: CreateSessionRequest,
    session_service: SessionService = Depends(SessionService),
) -> SessionResponse:
    return session_service.create_session(create_session_request)


@router.get("/session/{session_id}", response_model=SessionResponse)
async def get_session(
    session_id: UUID,
    session_service: SessionService = Depends(SessionService),
) -> SessionResponse:
    return session_service.get_session(session_id)


@router.delete("/session/{session_id}", status_code=204)
async def delete_session(
    session_id: UUID,
    session_service: SessionService = Depends(SessionService),
) -> None:
    return session_service.delete_session(session_id)
