"""Import of a v1 database (rts-api 1.x, SQLAlchemy schema).

The source is opened read-only and never modified. The import is idempotent: rows that
already exist are skipped, so it can be repeated (e.g. with a backup and the live database).
Afterwards every job is verified (number of measurements and checksum of the distances).
"""

import json
import logging
import math
import os
import sqlite3
import time
import uuid

from rtsapi.db import Database, connect

logger = logging.getLogger(__name__)

CHUNK = 20000

STATUS_MAP = {
    "pending": ("cancelled", "Was still pending when imported from v1"),
    "running": ("interrupted", "Was still running when imported from v1"),
    "finished": ("finished", None),
    "failed": ("failed", None),
}

TRACKING_FIELDS = [
    "tmc_measurement_mode", "tmc_inclination_mode", "edm_measurement_mode", "prism_type",
    "fine_adjust_position_mode", "fine_adjust_horizontal_search_range", "fine_adjust_vertical_search_range",
    "power_search_area_dcenterhz", "power_search_area_dcenterv", "power_search_area_drangehz",
    "power_search_area_drangev", "power_search_area_enabled", "power_search_min_range",
    "power_search_max_range", "power_search",
]


def uid(value) -> str | None:
    if value is None:
        return None
    return str(uuid.UUID(hex=str(value)))


def is_legacy_database(path: str) -> bool:
    if not os.path.isfile(path):
        return False
    try:
        conn = connect(path, readonly=True)
        try:
            tables = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type = 'table'")}
        finally:
            conn.close()
    except sqlite3.Error:
        return False
    return {"sessions", "rts", "rts_jobs", "measurements"} <= tables


def import_legacy(source_path: str, db: Database) -> dict:
    if not is_legacy_database(source_path):
        raise ValueError(f"{source_path} is not a v1 RTS database")
    started = time.time()
    src = connect(source_path, readonly=True)
    tables = {r[0] for r in src.execute("SELECT name FROM sqlite_master WHERE type = 'table'")}
    report: dict = {"source": os.path.abspath(source_path), "started_at": started, "counts": {}, "problems": []}

    def count(name: str, n: int) -> None:
        report["counts"][name] = report["counts"].get(name, 0) + n

    def insert(sql: str, rows: list[tuple]) -> int:
        if not rows:
            return 0

        def write(conn: sqlite3.Connection) -> int:
            before = conn.total_changes
            conn.executemany(sql, rows)
            return conn.total_changes - before

        return db.write(write, timeout=600)

    # ── sessions ────────────────────────────────────────────────────────
    sessions = src.execute("SELECT id, name, created_at FROM sessions").fetchall()
    count("sessions", insert(
        "INSERT OR IGNORE INTO sessions (id, name, created_at) VALUES (?, ?, ?)",
        [(uid(r["id"]), r["name"] or "Session", r["created_at"] or started) for r in sessions],
    ))

    # ── devices ─────────────────────────────────────────────────────────
    devices = src.execute("SELECT id, ip, last_seen FROM devices").fetchall()
    count("devices", insert(
        "INSERT OR IGNORE INTO devices (id, ip, created_at, last_seen) VALUES (?, ?, ?, ?)",
        [(uid(r["id"]), r["ip"], r["last_seen"] or started, r["last_seen"]) for r in devices],
    ))

    # ── RTS with tracking settings ──────────────────────────────────────
    settings = {}
    if "settings" in tables:
        for r in src.execute("SELECT * FROM settings"):
            values = {k: r[k] for k in TRACKING_FIELDS if k in r.keys()}
            if "power_search" in values:
                values["power_search"] = bool(values["power_search"])
            settings[r["rts_id"]] = values
    first_job = {r[0]: r[1] for r in src.execute("SELECT rts_id, MIN(created_at) FROM rts_jobs GROUP BY rts_id")}
    session_created = {r["id"]: r["created_at"] for r in sessions}
    orphan_session = None
    rts_rows = []
    for r in src.execute("SELECT * FROM rts"):
        session_id = r["session_id"]
        if session_id is None:
            if orphan_session is None:
                orphan_session = str(uuid.uuid4())
                insert(
                    "INSERT OR IGNORE INTO sessions (id, name, notes, created_at) VALUES (?, ?, ?, ?)",
                    [(orphan_session, "Imported RTS without session", "Created by the v1 import", started)],
                )
            session = orphan_session
        else:
            session = uid(session_id)
        created = first_job.get(r["id"]) or session_created.get(session_id) or started
        rts_rows.append((
            uid(r["id"]), session, uid(r["device_id"]), r["name"] or "RTS", r["port"], r["baudrate"], r["timeout"],
            r["parity"], r["stopbits"], r["bytesize"], r["internal_delay"] or 0.0, r["external_delay"] or 0.0,
            r["station_x"] or 0.0, r["station_y"] or 0.0, r["station_z"] or 0.0, r["orientation"] or 0.0,
            r["distance_std_dev"], r["angle_std_dev"], r["distance_ppm"],
            json.dumps(settings.get(r["id"], {})), created, int(bool(r["deleted"])),
        ))
    known_devices = {uid(r["id"]) for r in devices}
    rts_rows = [row[:2] + ((row[2] if row[2] in known_devices else None),) + row[3:] for row in rts_rows]
    count("rts", insert(
        """INSERT OR IGNORE INTO rts (id, session_id, device_id, name, port, baudrate, timeout, parity, stopbits,
           bytesize, internal_delay, external_delay, station_x, station_y, station_z, orientation,
           distance_std_dev, angle_std_dev, distance_ppm, tracking, created_at, deleted)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        rts_rows,
    ))

    # ── jobs ────────────────────────────────────────────────────────────
    known_rts = {r[0] for r in rts_rows}
    job_rows = []
    for r in src.execute("SELECT * FROM rts_jobs ORDER BY created_at"):
        rts_id = uid(r["rts_id"])
        if rts_id not in known_rts:
            report["problems"].append(f"Job {uid(r['id'])} skipped: its RTS does not exist")
            continue
        status, error = STATUS_MAP.get(r["status"], ("failed", f"Unknown v1 status {r['status']}"))
        payload = r["payload"] if isinstance(r["payload"], str) else json.dumps(r["payload"] or {})
        job_rows.append((
            uid(r["id"]), rts_id, r["job_type"], status, payload or "{}", r["created_at"],
            r["created_at"] if status != "cancelled" else None, r["finished_at"], error,
        ))
    count("jobs", insert(
        """INSERT OR IGNORE INTO jobs (id, rts_id, type, status, payload, created_at, started_at, finished_at, error)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        job_rows,
    ))

    # ── measurements (seq in time order) ────────────────────────────────
    target_jobs = {r["id"]: (r["no"], r["count"]) for r in db.query("SELECT id, no, count FROM jobs")}
    verified = 0
    for job in job_rows:
        job_id = job[0]
        hex_id = uuid.UUID(job_id).hex
        no, existing = target_jobs[job_id]
        src_count, src_sum = src.execute(
            "SELECT COUNT(*), TOTAL(distance) FROM measurements WHERE rts_job_id = ?", (hex_id,)
        ).fetchone()
        if existing == 0 and src_count > 0:
            cursor = src.execute(
                """SELECT controller_timestamp, sensor_timestamp, response_length, geocom_return_code,
                   rpc_return_code, distance, horizontal_angle, vertical_angle
                   FROM measurements WHERE rts_job_id = ? ORDER BY controller_timestamp, id""",
                (hex_id,),
            )
            seq = 0
            while True:
                chunk = cursor.fetchmany(CHUNK)
                if not chunk:
                    break
                rows = []
                for r in chunk:
                    rows.append((no, seq, r[0], r[1], None, r[2], r[3], r[4], r[5], r[6], r[7]))
                    seq += 1
                count("measurements", insert(
                    "INSERT OR IGNORE INTO measurements (job_no, seq, t, ts, tr, len, grc, rrc, d, hz, v) "
                    "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    rows,
                ))
            db.write(lambda conn, no=no: conn.execute(
                """UPDATE jobs SET count = (SELECT COUNT(*) FROM measurements WHERE job_no = :no),
                   first_t = (SELECT MIN(t) FROM measurements WHERE job_no = :no),
                   last_t = (SELECT MAX(t) FROM measurements WHERE job_no = :no),
                   max_seq = COALESCE((SELECT MAX(seq) FROM measurements WHERE job_no = :no), -1)
                   WHERE no = :no""",
                {"no": no},
            ), timeout=600)
        dst_count, dst_sum = db.query_one(
            "SELECT COUNT(*), TOTAL(d) FROM measurements WHERE job_no = ?", (no,)
        )
        if dst_count != src_count or not math.isclose(dst_sum, src_sum, rel_tol=1e-9, abs_tol=1e-6):
            report["problems"].append(
                f"Job {job_id}: {src_count} measurements in v1, {dst_count} imported (distance sum {src_sum} vs {dst_sum})"
            )
        else:
            verified += 1
    report["jobs_verified"] = verified

    # ── external sensors ────────────────────────────────────────────────
    if "external_sensors" in tables:
        sensors = src.execute("SELECT * FROM external_sensors").fetchall()
        count("external_sensors", insert(
            "INSERT OR IGNORE INTO external_sensors (id, ip, name, logging_active, created_at, last_seen) VALUES (?, ?, ?, ?, ?, ?)",
            [(uid(r["id"]), r["ip"], r["name"] or "External Sensor", int(bool(r["logging_active"])), r["last_seen"] or started, r["last_seen"]) for r in sensors],
        ))
        existing_sensors = {r["sensor_id"] for r in db.query("SELECT DISTINCT sensor_id FROM external_measurements")}
        for sensor in sensors:
            sensor_id = uid(sensor["id"])
            if sensor_id in existing_sensors:
                continue
            cursor = src.execute(
                """SELECT timestamp, position_x, position_y, position_z, velocity_x, velocity_y, velocity_z, epsg
                   FROM external_sensor_measurements WHERE external_sensor_id = ? ORDER BY timestamp""",
                (sensor["id"],),
            )
            while True:
                chunk = cursor.fetchmany(CHUNK)
                if not chunk:
                    break
                count("external_measurements", insert(
                    "INSERT INTO external_measurements (sensor_id, t, x, y, z, vx, vy, vz, epsg) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    [(sensor_id, *tuple(r)) for r in chunk],
                ))

    src.close()
    report["duration"] = time.time() - started
    report["ok"] = not report["problems"]
    logger.info(
        "v1 import of %s finished in %.1f s: %s, %i jobs verified, %i problem(s)",
        source_path, report["duration"], report["counts"], verified, len(report["problems"]),
    )
    for problem in report["problems"]:
        logger.warning("Import: %s", problem)
    return report
