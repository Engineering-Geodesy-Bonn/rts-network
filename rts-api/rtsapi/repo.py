"""Queries and write functions. Reads run on the calling thread, writes in the writer thread."""

import json
import sqlite3
import time
import uuid
from dataclasses import dataclass

import numpy as np

from rtsapi import models as m
from rtsapi.db import Database
from rtsapi.errors import BadRequest, NotFound

PURGE_CHUNK = 20000  # measurements deleted per write transaction


def new_id() -> str:
    return str(uuid.uuid4())


# ── meta ────────────────────────────────────────────────────────────────


def get_meta(db: Database, key: str) -> str | None:
    row = db.query_one("SELECT value FROM meta WHERE key = ?", (key,))
    return row["value"] if row else None


def set_meta(db: Database, key: str, value: str | None) -> None:
    db.execute("INSERT INTO meta (key, value) VALUES (?, ?) ON CONFLICT(key) DO UPDATE SET value = excluded.value", (key, value))


# ── sessions ────────────────────────────────────────────────────────────

SESSION_SELECT = """
SELECT s.*,
    (SELECT COUNT(*) FROM rts r WHERE r.session_id = s.id AND r.deleted = 0) AS rts_count,
    (SELECT COUNT(*) FROM jobs j JOIN rts r ON r.id = j.rts_id WHERE r.session_id = s.id AND j.deleted = 0) AS job_count,
    (SELECT COALESCE(SUM(j.count), 0) FROM jobs j JOIN rts r ON r.id = j.rts_id WHERE r.session_id = s.id AND j.deleted = 0) AS measurement_count,
    (SELECT MAX(COALESCE(j.last_rx, j.finished_at, j.created_at)) FROM jobs j JOIN rts r ON r.id = j.rts_id WHERE r.session_id = s.id AND j.deleted = 0) AS last_activity
FROM sessions s
"""


def _session(row: sqlite3.Row) -> m.Session:
    return m.Session(
        id=row["id"],
        name=row["name"],
        notes=row["notes"],
        created_at=row["created_at"],
        archived=bool(row["archived"]),
        rts_count=row["rts_count"],
        job_count=row["job_count"],
        measurement_count=row["measurement_count"],
        last_activity=row["last_activity"],
    )


def list_sessions(db: Database) -> list[m.Session]:
    return [_session(r) for r in db.query(SESSION_SELECT + " ORDER BY s.created_at DESC")]


def get_session(db: Database, session_id: str) -> m.Session:
    row = db.query_one(SESSION_SELECT + " WHERE s.id = ?", (session_id,))
    if row is None:
        raise NotFound(f"Session {session_id} not found")
    return _session(row)


def create_session(db: Database, data: m.SessionCreate) -> m.Session:
    session_id = new_id()
    db.execute(
        "INSERT INTO sessions (id, name, notes, created_at) VALUES (?, ?, ?, ?)",
        (session_id, data.name, data.notes, time.time()),
    )
    return get_session(db, session_id)


def update_session(db: Database, session_id: str, data: m.SessionUpdate) -> m.Session:
    get_session(db, session_id)
    fields = data.model_dump(exclude_unset=True)
    if "archived" in fields:
        fields["archived"] = int(fields["archived"])
    if fields:
        assignments = ", ".join(f"{k} = :{k}" for k in fields)
        db.execute(f"UPDATE sessions SET {assignments} WHERE id = :id", {**fields, "id": session_id})
    return get_session(db, session_id)


def delete_session(db: Database, session_id: str) -> None:
    get_session(db, session_id)
    job_nos = [r["no"] for r in db.query(
        "SELECT j.no FROM jobs j JOIN rts r ON r.id = j.rts_id WHERE r.session_id = ?", (session_id,)
    )]
    purge_measurements(db, job_nos)
    db.execute("DELETE FROM sessions WHERE id = ?", (session_id,))


# ── devices ─────────────────────────────────────────────────────────────


def _device(row: sqlite3.Row) -> m.Device:
    return m.Device(**{k: row[k] for k in ("id", "ip", "hostname", "name", "created_at", "last_seen")})


def list_devices(db: Database) -> list[m.Device]:
    return [_device(r) for r in db.query("SELECT * FROM devices ORDER BY COALESCE(name, hostname, ip)")]


def get_device(db: Database, device_id: str) -> m.Device:
    row = db.query_one("SELECT * FROM devices WHERE id = ?", (device_id,))
    if row is None:
        raise NotFound(f"Device {device_id} not found")
    return _device(row)


def upsert_device(db: Database, ip: str, hostname: str | None, touch: bool = True) -> str:
    """Finds the device of a worker by hostname (stable across DHCP leases), else by IP."""

    def write(conn: sqlite3.Connection) -> str:
        now = time.time()
        row = None
        if hostname:
            row = conn.execute("SELECT id FROM devices WHERE hostname = ? ORDER BY created_at LIMIT 1", (hostname,)).fetchone()
        if row is None:
            # A known IP without hostname (imported from v1 or an older registration)
            row = conn.execute(
                "SELECT id FROM devices WHERE ip = ? AND (hostname IS NULL OR ? IS NULL) ORDER BY created_at LIMIT 1",
                (ip, hostname),
            ).fetchone()
        if row is None:
            device_id = new_id()
            conn.execute(
                "INSERT INTO devices (id, ip, hostname, created_at, last_seen) VALUES (?, ?, ?, ?, ?)",
                (device_id, ip, hostname, now, now),
            )
            return device_id
        device_id = row["id"]
        conn.execute(
            "UPDATE devices SET ip = ?, hostname = COALESCE(?, hostname), last_seen = CASE WHEN ? THEN ? ELSE last_seen END WHERE id = ?",
            (ip, hostname, touch, now, device_id),
        )
        return device_id

    return db.write(write)


def update_device(db: Database, device_id: str, data: m.DeviceUpdate) -> m.Device:
    get_device(db, device_id)
    db.execute("UPDATE devices SET name = ? WHERE id = ?", (data.name or None, device_id))
    return get_device(db, device_id)


def delete_device(db: Database, device_id: str) -> None:
    get_device(db, device_id)
    db.execute("DELETE FROM devices WHERE id = ?", (device_id,))


# ── RTS ─────────────────────────────────────────────────────────────────

RTS_CONFIG_FIELDS = list(m.RTSConfig.model_fields)


def _rts(row: sqlite3.Row) -> m.RTS:
    report = json.loads(row["instrument_report"]) if row["instrument_report"] else None
    return m.RTS(
        id=row["id"],
        session_id=row["session_id"],
        device_id=row["device_id"],
        tracking=m.TrackingSettings(**json.loads(row["tracking"] or "{}")),
        instrument_report=m.InstrumentReportRecord(**report) if report else None,
        created_at=row["created_at"],
        deleted=bool(row["deleted"]),
        **{k: row[k] for k in RTS_CONFIG_FIELDS},
    )


def list_rts(db: Database, session_id: str | None = None, include_deleted: bool = False) -> list[m.RTS]:
    sql = "SELECT * FROM rts WHERE 1 = 1"
    params: list = []
    if session_id is not None:
        sql += " AND session_id = ?"
        params.append(session_id)
    if not include_deleted:
        sql += " AND deleted = 0"
    return [_rts(r) for r in db.query(sql + " ORDER BY name, created_at", tuple(params))]


def get_rts(db: Database, rts_id: str, deleted_ok: bool = True) -> m.RTS:
    row = db.query_one("SELECT * FROM rts WHERE id = ?", (rts_id,))
    if row is None or (row["deleted"] and not deleted_ok):
        raise NotFound(f"RTS {rts_id} not found")
    return _rts(row)


def create_rts(db: Database, data: m.RTSCreate) -> m.RTS:
    get_session(db, data.session_id)
    if data.device_id:
        get_device(db, data.device_id)
    rts_id = new_id()
    values = {k: getattr(data, k) for k in RTS_CONFIG_FIELDS}
    values.update(
        id=rts_id,
        session_id=data.session_id,
        device_id=data.device_id,
        tracking=data.tracking.model_dump_json(),
        created_at=time.time(),
    )
    columns = ", ".join(values)
    placeholders = ", ".join(f":{k}" for k in values)
    db.execute(f"INSERT INTO rts ({columns}) VALUES ({placeholders})", values)
    return get_rts(db, rts_id)


def update_rts(db: Database, rts_id: str, data: m.RTSUpdate) -> m.RTS:
    get_rts(db, rts_id, deleted_ok=False)
    fields = data.model_dump(exclude_unset=True)
    if "device_id" in fields and fields["device_id"]:
        get_device(db, fields["device_id"])
    if "tracking" in fields:
        fields["tracking"] = data.tracking.model_dump_json() if data.tracking else "{}"
    fields = {k: v for k, v in fields.items() if v is not None or k == "device_id"}
    if fields:
        assignments = ", ".join(f"{k} = :{k}" for k in fields)
        db.execute(f"UPDATE rts SET {assignments} WHERE id = :id", {**fields, "id": rts_id})
    return get_rts(db, rts_id)


def delete_rts(db: Database, rts_id: str) -> None:
    """Soft delete: measurements of the RTS stay available in the job history."""
    get_rts(db, rts_id, deleted_ok=False)
    db.execute("UPDATE rts SET deleted = 1 WHERE id = ?", (rts_id,))


def set_instrument_report(db: Database, rts_id: str, report: m.InstrumentReportRecord) -> None:
    get_rts(db, rts_id)
    db.execute("UPDATE rts SET instrument_report = ? WHERE id = ?", (report.model_dump_json(), rts_id))


# ── jobs ────────────────────────────────────────────────────────────────


def job_from_row(row: sqlite3.Row) -> m.Job:
    return m.Job(
        id=row["id"],
        rts_id=row["rts_id"],
        type=m.JobType(row["type"]),
        status=m.JobStatus(row["status"]),
        payload=json.loads(row["payload"] or "{}"),
        created_at=row["created_at"],
        started_at=row["started_at"],
        finished_at=row["finished_at"],
        worker_id=row["worker_id"],
        stop_requested=bool(row["stop_requested"]),
        error=row["error"],
        note=row["note"],
        count=row["count"],
        first_t=row["first_t"],
        last_t=row["last_t"],
        last_rx=row["last_rx"],
    )


def get_job_row(db: Database, job_id: str) -> sqlite3.Row:
    row = db.query_one("SELECT * FROM jobs WHERE id = ? AND deleted = 0", (job_id,))
    if row is None:
        raise NotFound(f"Job {job_id} not found")
    return row


def get_job(db: Database, job_id: str) -> m.Job:
    return job_from_row(get_job_row(db, job_id))


def list_jobs(
    db: Database,
    session_id: str | None = None,
    rts_id: str | None = None,
    statuses: list[m.JobStatus] | None = None,
    types: list[m.JobType] | None = None,
    with_measurements: bool = False,
    before: float | None = None,
    limit: int = 50,
    before_no: int | None = None,
) -> m.JobPage:
    sql = "SELECT j.* FROM jobs j JOIN rts r ON r.id = j.rts_id WHERE j.deleted = 0"
    params: list = []
    if session_id:
        sql += " AND r.session_id = ?"
        params.append(session_id)
    if rts_id:
        sql += " AND j.rts_id = ?"
        params.append(rts_id)
    if statuses:
        sql += f" AND j.status IN ({','.join('?' * len(statuses))})"
        params += [s.value for s in statuses]
    if types:
        sql += f" AND j.type IN ({','.join('?' * len(types))})"
        params += [t.value for t in types]
    if with_measurements:
        sql += " AND j.count > 0"
    if before is not None:
        if before_no is None:
            sql += " AND j.created_at < ?"
            params.append(before)
        else:  # keyset on (created_at, no): jobs with the same created_at are not skipped
            sql += " AND (j.created_at < ? OR (j.created_at = ? AND j.no < ?))"
            params += [before, before, before_no]
    sql += " ORDER BY j.created_at DESC, j.no DESC LIMIT ?"
    params.append(limit + 1)
    rows = db.query(sql, tuple(params))
    items = [job_from_row(r) for r in rows[:limit]]
    more = len(rows) > limit
    return m.JobPage(
        items=items,
        next_before=items[-1].created_at if more else None,
        next_before_no=rows[limit - 1]["no"] if more else None,
    )


def active_jobs(db: Database) -> list[m.Job]:
    rows = db.query(
        "SELECT * FROM jobs WHERE deleted = 0 AND status IN ('pending', 'running', 'lost') ORDER BY created_at"
    )
    return [job_from_row(r) for r in rows]


def last_completed_jobs(db: Database, rts_ids: list[str]) -> dict[str, m.Job]:
    """Most recent terminal job per RTS, ignoring v1 static measurement containers."""
    if not rts_ids:
        return {}
    rows = db.query(
        f"""SELECT j.* FROM jobs j
        JOIN (SELECT rts_id, MAX(created_at) AS created_at FROM jobs
              WHERE deleted = 0 AND status NOT IN ('pending', 'running', 'lost') AND type != 'static_measurement'
                AND rts_id IN ({','.join('?' * len(rts_ids))})
              GROUP BY rts_id) last
        ON last.rts_id = j.rts_id AND last.created_at = j.created_at""",
        tuple(rts_ids),
    )
    return {r["rts_id"]: job_from_row(r) for r in rows}


def create_job(db: Database, data: m.JobCreate) -> m.Job:
    rts = get_rts(db, data.rts_id, deleted_ok=False)
    if data.type == m.JobType.STATIC_MEASUREMENT:
        raise BadRequest("Static measurements are taken with jobs of type add_static_measurement")
    job_id = new_id()
    db.execute(
        "INSERT INTO jobs (id, rts_id, type, status, payload, created_at) VALUES (?, ?, ?, 'pending', ?, ?)",
        (job_id, rts.id, data.type.value, json.dumps(data.payload), time.time()),
    )
    return get_job(db, job_id)


def update_job(db: Database, job_id: str, data: m.JobUpdate) -> m.Job:
    get_job_row(db, job_id)
    if data.note is not None:
        db.execute("UPDATE jobs SET note = ? WHERE id = ?", (data.note, job_id))
    return get_job(db, job_id)


def purge_measurements(db: Database, job_nos: list[int]) -> None:
    """Deletes measurements in chunks, so that ingest is never blocked for long."""
    for job_no in job_nos:
        while True:
            deleted = db.write(
                lambda conn, no=job_no: conn.execute(
                    "DELETE FROM measurements WHERE job_no = ? AND seq IN "
                    "(SELECT seq FROM measurements WHERE job_no = ? LIMIT ?)",
                    (no, no, PURGE_CHUNK),
                ).rowcount
            )
            if deleted < PURGE_CHUNK:
                break


def delete_job(db: Database, job_id: str) -> int:
    row = get_job_row(db, job_id)
    db.execute("UPDATE jobs SET deleted = 1 WHERE no = ?", (row["no"],))
    return row["no"]


def finish_job_deletion(db: Database, job_no: int) -> None:
    purge_measurements(db, [job_no])
    db.execute("DELETE FROM jobs WHERE no = ?", (job_no,))


def pending_job_deletions(db: Database) -> list[int]:
    return [r["no"] for r in db.query("SELECT no FROM jobs WHERE deleted = 1")]


# ── measurements ────────────────────────────────────────────────────────


@dataclass
class MeasurementArrays:
    seq: np.ndarray
    t: np.ndarray
    ts: np.ndarray
    tr: np.ndarray
    length: np.ndarray
    grc: np.ndarray
    rrc: np.ndarray
    d: np.ndarray
    hz: np.ndarray
    v: np.ndarray

    def __len__(self) -> int:
        return len(self.seq)


def _arrays(rows: list[tuple]) -> MeasurementArrays:
    if rows:
        data = np.array(rows, dtype=float)
    else:
        data = np.empty((0, 10))
    return MeasurementArrays(
        seq=data[:, 0].astype(np.int64),
        t=data[:, 1],
        ts=data[:, 2],
        tr=data[:, 3],
        length=data[:, 4].astype(np.int64),
        grc=data[:, 5].astype(np.int64),
        rrc=data[:, 6].astype(np.int64),
        d=data[:, 7],
        hz=data[:, 8],
        v=data[:, 9],
    )


def read_measurements(
    db: Database,
    job_no: int,
    from_seq: int | None = None,
    to_seq: int | None = None,
    stride: int = 1,
) -> MeasurementArrays:
    sql = "SELECT seq, t, ts, COALESCE(tr, 'nan'), len, grc, rrc, d, hz, v FROM measurements WHERE job_no = ?"
    params: list = [job_no]
    if from_seq is not None:
        sql += " AND seq >= ?"
        params.append(from_seq)
    if to_seq is not None:
        sql += " AND seq <= ?"
        params.append(to_seq)
    if stride > 1:
        sql += " AND seq % ? = 0"
        params.append(stride)
    sql += " ORDER BY seq"
    conn = db.reader()
    cursor = conn.execute(sql, tuple(params))
    cursor.row_factory = None
    return _arrays(cursor.fetchall())


def count_measurements(db: Database, job_no: int, from_seq: int | None, to_seq: int | None) -> tuple[int, int, int]:
    """Number of stored measurements and the seq range within the bounds."""
    sql = "SELECT COUNT(*), MIN(seq), MAX(seq) FROM measurements WHERE job_no = ?"
    params: list = [job_no]
    if from_seq is not None:
        sql += " AND seq >= ?"
        params.append(from_seq)
    if to_seq is not None:
        sql += " AND seq <= ?"
        params.append(to_seq)
    row = db.reader().execute(sql, tuple(params)).fetchone()
    return row[0], row[1], row[2]


# ── external sensors ────────────────────────────────────────────────────


def _external_sensor(row: sqlite3.Row) -> m.ExternalSensor:
    return m.ExternalSensor(
        id=row["id"],
        ip=row["ip"],
        name=row["name"],
        logging_active=bool(row["logging_active"]),
        created_at=row["created_at"],
        last_seen=row["last_seen"],
        count=row["count"] if "count" in row.keys() else 0,
    )


def list_external_sensors(db: Database) -> list[m.ExternalSensor]:
    rows = db.query(
        "SELECT s.*, (SELECT COUNT(*) FROM external_measurements e WHERE e.sensor_id = s.id) AS count "
        "FROM external_sensors s ORDER BY s.name"
    )
    return [_external_sensor(r) for r in rows]


def get_external_sensor(db: Database, sensor_id: str) -> m.ExternalSensor:
    row = db.query_one(
        "SELECT s.*, (SELECT COUNT(*) FROM external_measurements e WHERE e.sensor_id = s.id) AS count "
        "FROM external_sensors s WHERE s.id = ?",
        (sensor_id,),
    )
    if row is None:
        raise NotFound(f"External sensor {sensor_id} not found")
    return _external_sensor(row)


def update_external_sensor(db: Database, sensor_id: str, data: m.ExternalSensorUpdate) -> m.ExternalSensor:
    get_external_sensor(db, sensor_id)
    fields = {k: v for k, v in data.model_dump(exclude_unset=True).items() if v is not None}
    if "logging_active" in fields:
        fields["logging_active"] = int(fields["logging_active"])
    if fields:
        assignments = ", ".join(f"{k} = :{k}" for k in fields)
        db.execute(f"UPDATE external_sensors SET {assignments} WHERE id = :id", {**fields, "id": sensor_id})
    return get_external_sensor(db, sensor_id)


def delete_external_sensor(db: Database, sensor_id: str) -> None:
    get_external_sensor(db, sensor_id)
    while db.execute(
        "DELETE FROM external_measurements WHERE id IN (SELECT id FROM external_measurements WHERE sensor_id = ? LIMIT ?)",
        (sensor_id, PURGE_CHUNK),
    ) >= PURGE_CHUNK:
        pass
    db.execute("DELETE FROM external_sensors WHERE id = ?", (sensor_id,))


def read_external_measurements(db: Database, sensor_id: str) -> np.ndarray:
    cursor = db.reader().execute(
        "SELECT t, x, y, z, vx, vy, vz, epsg FROM external_measurements WHERE sensor_id = ? ORDER BY t", (sensor_id,)
    )
    cursor.row_factory = None
    rows = cursor.fetchall()
    return np.array(rows, dtype=float) if rows else np.empty((0, 8))
