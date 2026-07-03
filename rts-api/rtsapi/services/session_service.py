from uuid import UUID

from fastapi import Depends

from rtsapi import dtos
from rtsapi.database.session_repository import SessionRepository
from rtsapi.mappers import SessionMapper


class SessionService:
    def __init__(
        self,
        session_repository: SessionRepository = Depends(SessionRepository),
    ) -> None:
        self.session_repository = session_repository

    def create_session(
        self, create_session_request: dtos.CreateSessionRequest
    ) -> dtos.SessionResponse:
        db_session = self.session_repository.add_session(
            SessionMapper.to_db(create_session_request)
        )
        return SessionMapper.to_dto(db_session)

    def get_session(self, session_id: UUID) -> dtos.SessionResponse:
        db_session = self.session_repository.get_session(session_id)
        return SessionMapper.to_dto(db_session)

    def delete_session(self, session_id: UUID) -> None:
        self.session_repository.delete_session(session_id)

    def get_sessions(self) -> list[dtos.SessionResponse]:
        db_sessions = self.session_repository.get_sessions()
        return [SessionMapper.to_dto(db_session) for db_session in db_sessions]
