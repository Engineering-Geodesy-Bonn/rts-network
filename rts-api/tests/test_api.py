import time

from conftest import rows


def start_tracking(client, rts_id, worker="w1"):
    job = client.post("/jobs", json={"rts_id": rts_id, "type": "track_prism"}).json()
    assert job["status"] == "pending"
    claim = client.post("/worker/claim", json={"worker_id": worker, "hostname": "pi-1"})
    assert claim.status_code == 200, claim.text
    claimed = claim.json()
    assert claimed["job"]["id"] == job["id"]
    assert claimed["rts"]["name"] == "TS60"
    assert claimed["job"]["status"] == "running"
    return job["id"]


def test_session_crud(client):
    s = client.post("/sessions", json={"name": "A"}).json()
    assert client.get("/sessions").json()[0]["id"] == s["id"]
    assert client.patch(f"/sessions/{s['id']}", json={"notes": "n"}).json()["notes"] == "n"
    assert client.post("/sessions", json={"name": ""}).status_code == 422
    assert client.delete(f"/sessions/{s['id']}").status_code == 204
    assert client.get(f"/sessions/{s['id']}").status_code == 404


def test_device_identified_by_hostname(client):
    client.post("/worker/claim", json={"worker_id": "w1", "hostname": "pi-1"})
    client.post("/worker/claim", json={"worker_id": "w2", "hostname": "pi-1"})
    client.post("/worker/claim", json={"worker_id": "w3", "hostname": "pi-2"})
    devices = client.get("/devices").json()
    assert sorted(d["hostname"] for d in devices) == ["pi-1", "pi-2"]


def test_ingest_is_idempotent(client, setup):
    job_id = start_tracking(client, setup["rts"]["id"])
    r = client.post("/worker/measurements", json={"job_id": job_id, "rows": rows(0, 100)}).json()
    assert r == {"job_id": job_id, "acked_seq": 99, "inserted": 100, "rejected": None}
    # resend with overlap, plus duplicates within the batch
    r = client.post("/worker/measurements", json={"job_id": job_id, "rows": rows(50, 100) + rows(140, 5)}).json()
    assert r["acked_seq"] == 149 and r["inserted"] == 50
    job = client.get(f"/jobs/{job_id}").json()
    assert job["count"] == 150
    series = client.get(f"/jobs/{job_id}/measurements").json()
    assert series["seq"] == list(range(150))
    assert series["total"] == 150 and series["stride"] == 1
    assert abs(series["x"][0] - (10.0 + 10.0 * __import__("math").sin(1.5) * __import__("math").sin(0.1))) < 1e-9


def test_malformed_rows_are_dropped_not_fatal(client, setup):
    job_id = start_tracking(client, setup["rts"]["id"])
    bad = rows(0, 3)
    bad[1] = [1, "x"]
    bad[2][7] = float("nan")
    body = __import__("json").dumps({"job_id": job_id, "rows": bad})  # python json writes NaN
    r = client.post("/worker/measurements", content=body, headers={"Content-Type": "application/json"})
    assert r.status_code == 200, r.text
    assert r.json()["inserted"] == 1 and r.json()["acked_seq"] == 2


def test_unknown_job_is_rejected(client):
    r = client.post("/worker/measurements", json={"job_id": "nope", "rows": rows(0, 3)}).json()
    assert r["rejected"] == "unknown_job"


def test_downsampling(client, setup):
    job_id = start_tracking(client, setup["rts"]["id"])
    client.post("/worker/measurements", json={"job_id": job_id, "rows": rows(0, 1001)})
    series = client.get(f"/jobs/{job_id}/measurements?max_points=100").json()
    assert series["stride"] == 11
    assert series["seq"][0] == 0 and series["seq"][-1] == 1000
    window = client.get(f"/jobs/{job_id}/measurements?from_seq=500&to_seq=509").json()
    assert window["seq"] == list(range(500, 510))


def test_job_lifecycle_stop(client, setup):
    job_id = start_tracking(client, setup["rts"]["id"])
    assert client.post(f"/worker/jobs/{job_id}/renew?worker_id=w1").json() == {"status": "running", "stop": False}
    client.post(f"/jobs/{job_id}/stop")
    assert client.post(f"/worker/jobs/{job_id}/renew?worker_id=w1").json()["stop"] is True
    done = client.post(f"/worker/jobs/{job_id}/complete?worker_id=w1", json={"status": "finished"}).json()
    assert done["status"] == "finished" and done["finished_at"]


def test_one_job_per_rts_at_a_time(client, setup):
    start_tracking(client, setup["rts"]["id"])
    client.post("/jobs", json={"rts_id": setup["rts"]["id"], "type": "change_face"})
    assert client.post("/worker/claim", json={"worker_id": "w2", "hostname": "pi-1"}).status_code == 204


def test_cancel_pending(client, setup):
    job = client.post("/jobs", json={"rts_id": setup["rts"]["id"], "type": "change_face"}).json()
    assert client.post(f"/jobs/{job['id']}/stop").json()["status"] == "cancelled"
    assert client.post("/worker/claim", json={"worker_id": "w1", "hostname": "pi-1"}).status_code == 204


def test_lease_expiry_and_recovery(client, setup):
    job_id = start_tracking(client, setup["rts"]["id"])
    deadline = time.time() + 5
    while client.get(f"/jobs/{job_id}").json()["status"] != "lost":
        assert time.time() < deadline, "job was not marked lost"
        time.sleep(0.2)
    # measurements of a lost job are still accepted (worker kept measuring)
    assert client.post("/worker/measurements", json={"job_id": job_id, "rows": rows(0, 10)}).json()["inserted"] == 10
    assert client.post(f"/worker/jobs/{job_id}/renew?worker_id=w1").json() == {"status": "running", "stop": False}
    assert client.get(f"/jobs/{job_id}").json()["status"] == "running"


def test_stop_lost_job_interrupts(client, setup):
    job_id = start_tracking(client, setup["rts"]["id"])
    deadline = time.time() + 5
    while client.get(f"/jobs/{job_id}").json()["status"] != "lost":
        assert time.time() < deadline
        time.sleep(0.2)
    assert client.post(f"/jobs/{job_id}/stop").json()["status"] == "interrupted"
    assert client.post(f"/worker/jobs/{job_id}/renew?worker_id=w1").json()["stop"] is True
    # a late completion does not overwrite the user's decision
    assert client.post(f"/worker/jobs/{job_id}/complete?worker_id=w1", json={"status": "finished"}).json()["status"] == "interrupted"


def test_websocket_stream_and_events(client, setup):
    job_id = start_tracking(client, setup["rts"]["id"])
    with client.websocket_connect("/events") as events:
        assert events.receive_json()["type"] == "hello"
        events.send_json({"type": "subscribe", "session_id": setup["session"]["id"]})
        assert events.receive_json()["type"] == "status"
        with client.websocket_connect("/worker/stream") as ws:
            ws.send_json({"type": "batch", "job_id": job_id, "rows": rows(0, 20)})
            ack = ws.receive_json()
            assert ack["type"] == "ack" and ack["acked_seq"] == 19 and ack["inserted"] == 20
            ws.send_json({"type": "batch", "job_id": job_id, "rows": rows(0, 20)})
            assert ws.receive_json()["inserted"] == 0
        seen = []
        deadline = time.time() + 5
        while sum(len(m["seq"]) for m in seen) < 20:
            assert time.time() < deadline
            message = events.receive_json()
            if message["type"] == "live":
                seen.append(message)
        live_seq = [s for m in seen for s in m["seq"]]
        assert live_seq == list(range(20))  # duplicates were not re-published


def test_status_board(client, setup):
    job_id = start_tracking(client, setup["rts"]["id"])
    client.post("/worker/measurements", json={"job_id": job_id, "rows": rows(0, 50, t0=time.time() - 2)})
    board = client.get(f"/status?session_id={setup['session']['id']}").json()
    entry = board["rts"][0]
    assert entry["state"] == "running"
    assert entry["tracking"]["samples"] == 50
    assert {c["key"] for c in entry["checks"]} >= {"device", "serial_port", "jobs", "data_flow", "timing"}


def test_heartbeat(client):
    hb = {"worker_id": "w1", "sent_at": time.time(), "system": {"hostname": "pi-9"}}
    ack = client.post("/worker/heartbeat", json=hb).json()
    assert ack["server_send_time"] >= ack["server_receive_time"]
    assert client.get("/worker/workers").json()[0]["heartbeat"]["worker_id"] == "w1"
    assert any(d["hostname"] == "pi-9" for d in client.get("/devices").json())


def test_delete_job(client, setup):
    job_id = start_tracking(client, setup["rts"]["id"])
    client.post("/worker/measurements", json={"job_id": job_id, "rows": rows(0, 10)})
    assert client.delete(f"/jobs/{job_id}").status_code == 409  # still running
    client.post(f"/worker/jobs/{job_id}/complete?worker_id=w1", json={"status": "finished"})
    assert client.delete(f"/jobs/{job_id}").status_code == 204
    assert client.get(f"/jobs/{job_id}").status_code == 404


def test_exports(client, setup):
    job_id = start_tracking(client, setup["rts"]["id"])
    client.post("/worker/measurements", json={"job_id": job_id, "rows": rows(0, 200)})
    client.post(f"/worker/jobs/{job_id}/complete?worker_id=w1", json={"status": "finished"})
    raw = client.get(f"/jobs/{job_id}/csv?corrected=false")
    assert raw.status_code == 200 and raw.text.count("\n") == 201
    assert client.get(f"/jobs/{job_id}/csv").status_code == 200
    assert client.get(f"/jobs/{job_id}/trajectory").status_code == 200
    archive = client.get(f"/sessions/{setup['session']['id']}/export")
    assert archive.status_code == 200 and archive.content[:2] == b"PK"


def test_external_sensor_and_sync(client, setup):
    client.post("/external_sensors/measurement", json={"t": 1.0, "x": 1, "y": 2, "z": 3})
    sensor = client.get("/external-sensors").json()[0]
    assert sensor["count"] == 0  # logging disabled by default
    client.patch(f"/external-sensors/{sensor['id']}", json={"logging_active": True, "name": "GNSS"})
    for i in range(5):
        client.post("/external_sensors/measurement", json={"t": 2.0 + i, "x": 1, "y": 2, "z": 3})
    deadline = time.time() + 3
    while client.get(f"/external-sensors/{sensor['id']}").json()["count"] < 5:
        assert time.time() < deadline
        time.sleep(0.1)
    roles = client.put("/synchronizer/roles", json={"primary_sensor_id": sensor["id"], "secondary_sensor_id": setup["rts"]["id"]}).json()
    assert roles["primary_sensor_id"] == sensor["id"]
    assert "delta_t" in client.get("/synchronizer/state").json()


def test_timed_out_job_resumes_when_worker_returns(client, setup, settings):
    job_id = start_tracking(client, setup["rts"]["id"])
    client.app.state.core.settings.lost_job_timeout = 0.5
    deadline = time.time() + 6
    while client.get(f"/jobs/{job_id}").json()["status"] != "interrupted":
        assert time.time() < deadline
        time.sleep(0.2)
    assert client.post(f"/worker/jobs/{job_id}/renew?worker_id=w1").json() == {"status": "running", "stop": False}
    job = client.get(f"/jobs/{job_id}").json()
    assert job["status"] == "running" and job["error"] is None


def test_auto_import_runs_once_and_resumes(tmp_path):
    import sqlite3

    from rtsapi import repo
    from rtsapi.config import Settings
    from rtsapi.core import Core

    legacy = tmp_path / "v1.db"
    c = sqlite3.connect(legacy)
    c.executescript(
        """
        CREATE TABLE sessions (id CHAR(32), name, created_at);
        CREATE TABLE devices (id CHAR(32), ip, last_seen);
        CREATE TABLE rts (id CHAR(32), name, baudrate, port, timeout, parity, stopbits, bytesize, internal_delay,
            external_delay, station_x, station_y, station_z, orientation, distance_std_dev, angle_std_dev,
            distance_ppm, deleted, session_id, device_id);
        CREATE TABLE rts_jobs (id CHAR(32), status, job_type, created_at, finished_at, duration, datarate,
            num_measurements, payload, rts_id);
        CREATE TABLE measurements (id INTEGER PRIMARY KEY, controller_timestamp, sensor_timestamp, response_length,
            geocom_return_code, rpc_return_code, distance, horizontal_angle, vertical_angle, rts_id, rts_job_id);
        INSERT INTO sessions VALUES ('11111111111111111111111111111111', 'S', 1.0);
        INSERT INTO devices VALUES ('22222222222222222222222222222222', '10.0.0.2', 1.0);
        INSERT INTO rts VALUES ('33333333333333333333333333333333', 'R', 115200, '/dev/ttyUSB0', 30, 'N', 1, 8, 0, 0,
            1, 2, 3, 0, 0.001, 0.000005, 1, 0, '11111111111111111111111111111111', '22222222222222222222222222222222');
        INSERT INTO rts_jobs VALUES ('44444444444444444444444444444444', 'running', 'track_prism', 5.0, NULL, NULL,
            NULL, NULL, '{}', '33333333333333333333333333333333');
        """
    )
    c.executemany(
        "INSERT INTO measurements VALUES (NULL, ?, ?, 146, 0, 0, 10.0, 0.1, 1.5, ?, ?)",
        [(10.0 + i, 1000.0 + i, "33333333333333333333333333333333", "44444444444444444444444444444444") for i in range(50)],
    )
    c.commit()
    c.close()

    settings = Settings(db_path=str(tmp_path / "v2.db"), legacy_db_path=str(legacy))
    core = Core(settings)
    assert core.legacy_import["ok"] and core.legacy_import["counts"]["measurements"] == 50
    job = repo.get_job(core.db, "44444444-4444-4444-4444-444444444444")
    assert job.status.value == "interrupted" and job.count == 50
    # an interrupted import (no report) is resumed on the next start, without duplicates
    repo.set_meta(core.db, "legacy_import", None)
    core.db.execute("DELETE FROM meta WHERE key = 'legacy_import'")
    core.db.close()
    core = Core(settings)
    assert core.legacy_import["ok"] and repo.get_job(core.db, job.id).count == 50
    core.db.close()
