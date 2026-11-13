"""Database schema as an ordered list of migrations (PRAGMA user_version = index + 1).

Never edit a released migration: append a new one instead.
"""

MIGRATIONS: list[list[str]] = [
    # 1: initial v2 schema
    [
        """CREATE TABLE meta (
            key TEXT PRIMARY KEY,
            value TEXT
        )""",
        """CREATE TABLE sessions (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            notes TEXT NOT NULL DEFAULT '',
            created_at REAL NOT NULL,
            archived INTEGER NOT NULL DEFAULT 0
        )""",
        """CREATE TABLE devices (
            id TEXT PRIMARY KEY,
            ip TEXT NOT NULL,
            hostname TEXT,
            name TEXT,
            created_at REAL NOT NULL,
            last_seen REAL
        )""",
        "CREATE INDEX ix_devices_ip ON devices (ip)",
        "CREATE INDEX ix_devices_hostname ON devices (hostname)",
        """CREATE TABLE rts (
            id TEXT PRIMARY KEY,
            session_id TEXT NOT NULL REFERENCES sessions(id) ON DELETE CASCADE,
            device_id TEXT REFERENCES devices(id) ON DELETE SET NULL,
            name TEXT NOT NULL,
            port TEXT NOT NULL,
            baudrate INTEGER NOT NULL,
            timeout INTEGER NOT NULL,
            parity TEXT NOT NULL,
            stopbits INTEGER NOT NULL,
            bytesize INTEGER NOT NULL,
            internal_delay REAL NOT NULL,
            external_delay REAL NOT NULL,
            station_x REAL NOT NULL,
            station_y REAL NOT NULL,
            station_z REAL NOT NULL,
            orientation REAL NOT NULL,
            distance_std_dev REAL NOT NULL,
            angle_std_dev REAL NOT NULL,
            distance_ppm REAL NOT NULL,
            tracking TEXT NOT NULL DEFAULT '{}',
            instrument_report TEXT,
            created_at REAL NOT NULL,
            deleted INTEGER NOT NULL DEFAULT 0
        )""",
        "CREATE INDEX ix_rts_session ON rts (session_id)",
        "CREATE INDEX ix_rts_device ON rts (device_id)",
        """CREATE TABLE jobs (
            no INTEGER PRIMARY KEY,
            id TEXT NOT NULL UNIQUE,
            rts_id TEXT NOT NULL REFERENCES rts(id) ON DELETE CASCADE,
            type TEXT NOT NULL,
            status TEXT NOT NULL,
            payload TEXT NOT NULL DEFAULT '{}',
            created_at REAL NOT NULL,
            started_at REAL,
            finished_at REAL,
            worker_id TEXT,
            lease_until REAL,
            stop_requested INTEGER NOT NULL DEFAULT 0,
            error TEXT,
            note TEXT NOT NULL DEFAULT '',
            count INTEGER NOT NULL DEFAULT 0,
            first_t REAL,
            last_t REAL,
            max_seq INTEGER NOT NULL DEFAULT -1,
            last_rx REAL,
            deleted INTEGER NOT NULL DEFAULT 0
        )""",
        "CREATE INDEX ix_jobs_rts_created ON jobs (rts_id, created_at)",
        "CREATE INDEX ix_jobs_status ON jobs (status)",
        # Clustered by (job, seq): a job's measurements are stored contiguously.
        # seq is assigned by the worker, so resending a measurement is harmless.
        """CREATE TABLE measurements (
            job_no INTEGER NOT NULL REFERENCES jobs(no) ON DELETE CASCADE,
            seq INTEGER NOT NULL,
            t REAL NOT NULL,
            ts REAL NOT NULL,
            tr REAL,
            len INTEGER NOT NULL,
            grc INTEGER NOT NULL,
            rrc INTEGER NOT NULL,
            d REAL NOT NULL,
            hz REAL NOT NULL,
            v REAL NOT NULL,
            PRIMARY KEY (job_no, seq)
        ) WITHOUT ROWID""",
        """CREATE TABLE external_sensors (
            id TEXT PRIMARY KEY,
            ip TEXT NOT NULL UNIQUE,
            name TEXT NOT NULL,
            logging_active INTEGER NOT NULL DEFAULT 0,
            created_at REAL NOT NULL,
            last_seen REAL
        )""",
        """CREATE TABLE external_measurements (
            id INTEGER PRIMARY KEY,
            sensor_id TEXT NOT NULL REFERENCES external_sensors(id) ON DELETE CASCADE,
            t REAL NOT NULL,
            x REAL NOT NULL,
            y REAL NOT NULL,
            z REAL NOT NULL,
            vx REAL NOT NULL,
            vy REAL NOT NULL,
            vz REAL NOT NULL,
            epsg INTEGER NOT NULL DEFAULT 0
        )""",
        "CREATE INDEX ix_external_measurements_sensor ON external_measurements (sensor_id, t)",
    ],
    # 2: instruments that answered GeoCOM over Bluetooth
    [
        """CREATE TABLE bluetooth_instruments (
            address TEXT PRIMARY KEY,
            name TEXT,
            instrument_name TEXT,
            serial_number INTEGER,
            channel INTEGER NOT NULL,
            last_device_id TEXT REFERENCES devices(id) ON DELETE SET NULL,
            last_seen REAL
        )""",
    ],
]
