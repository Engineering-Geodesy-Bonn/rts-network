import pytest
from fastapi.testclient import TestClient

from rtsapi.app import create_app
from rtsapi.config import Settings


@pytest.fixture
def settings(tmp_path) -> Settings:
    return Settings(
        db_path=str(tmp_path / "test.db"),
        legacy_db_path=None,
        lease_duration=1.0,
        pending_timeout=300.0,
        lost_job_timeout=3600.0,
    )


@pytest.fixture
def client(settings):
    with TestClient(create_app(settings)) as c:
        yield c


@pytest.fixture
def setup(client):
    """A session with one RTS on the device of the test client."""
    session = client.post("/sessions", json={"name": "Test"}).json()
    # the test client registers its device by claiming (no job yet)
    assert client.post("/worker/claim", json={"worker_id": "w1", "hostname": "pi-1"}).status_code == 204
    device = client.get("/devices").json()[0]
    rts = client.post("/rts", json={"session_id": session["id"], "device_id": device["id"], "name": "TS60", "station_x": 10.0}).json()
    return {"session": session, "device": device, "rts": rts}


def rows(start: int, n: int, t0: float = 1000.0):
    return [[s, t0 + s * 0.04, s * 40.0 + 1, None, 146, 0, 0, 10.0 + s * 0.001, 0.1, 1.5] for s in range(start, start + n)]
