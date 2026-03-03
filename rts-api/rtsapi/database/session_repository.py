from fastapi import Depends
from sqlalchemy.orm import Session
from uuid import UUID

from rtsapi.database import models
from rtsapi.dependencies import get_db
from rtsapi.exceptions import SessionNotFoundException


class SessionRepository:
    def __init__(self, db: Session = Depends(get_db)):
        self.db = db

    def add_session(self, session: models.Session) -> models.Session:
        self.db.add(session)
        self.db.commit()
        self.db.refresh(session)
        return session
    
    def get_session(self, session_id: UUID) -> models.Session:
        db_session =  self.db.query(models.Session).filter(models.Session.id == session_id).first()

        if db_session is None:
            raise SessionNotFoundException(f"Session with id {session_id} not found")
        
        return db_session
    
    def get_sessions(self) -> list[models.Session]:
        return self.db.query(models.Session).all()
    
    def delete_session(self, session_id: UUID) -> None:
        session = self.get_session(session_id)
        if session:
            self.db.delete(session)
            self.db.commit()

