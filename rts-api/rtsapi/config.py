"""Runtime configuration, read once from environment variables."""

import os
from dataclasses import dataclass, field


def _env_float(name: str, default: float) -> float:
    return float(os.getenv(name, default))


def _default_db_path() -> str:
    url = os.getenv("DATABASE_URL")  # v1 compatibility: sqlite:////data/database.db
    if url and url.startswith("sqlite:///"):
        legacy = url.removeprefix("sqlite:///")
        return os.path.join(os.path.dirname(legacy) or ".", "rtsnet.db")
    return os.getenv("RTS_DB_PATH", "./rtsnet.db")


def _default_legacy_path() -> str | None:
    """The v1 database that is imported automatically on the first start."""
    if "RTS_LEGACY_DB" in os.environ:
        return os.environ["RTS_LEGACY_DB"] or None
    url = os.getenv("DATABASE_URL")
    if url and url.startswith("sqlite:///"):
        return url.removeprefix("sqlite:///")
    return None


@dataclass
class Settings:
    db_path: str = field(default_factory=_default_db_path)
    legacy_db_path: str | None = field(default_factory=_default_legacy_path)

    # Job lifecycle
    lease_duration: float = field(default_factory=lambda: _env_float("RTS_LEASE_DURATION", 15.0))
    pending_timeout: float = field(default_factory=lambda: _env_float("RTS_PENDING_TIMEOUT", 300.0))
    lost_job_timeout: float = field(default_factory=lambda: _env_float("RTS_LOST_JOB_TIMEOUT", 60.0))

    # Live data
    live_buffer_seconds: float = field(default_factory=lambda: _env_float("RTS_LIVE_BUFFER_SECONDS", 900.0))
    live_flush_interval: float = 0.2  # s between live updates pushed to the dashboards
    status_interval: float = 2.0  # s between health evaluations

    # Writer
    writer_max_batch: int = 500  # write tasks combined into one transaction

    log_level: str = field(default_factory=lambda: os.getenv("RTS_LOG_LEVEL", "INFO"))


settings = Settings()
