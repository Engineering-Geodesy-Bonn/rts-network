from typing import Generator

from fastapi.requests import HTTPConnection
from sqlalchemy.orm import Session

from rtsapi.app_state import AppState
from rtsapi.database import SessionLocal

def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def get_app_state(connection: HTTPConnection) -> AppState:
    return connection.app.state.app_state
