import os


def env_float(name: str, default: float) -> float:
    return float(os.getenv(name, default))


API_HOST = os.getenv("API_HOST") or "192.168.0.101"  # empty (unset in .env) means the default
API_PORT = int(os.getenv("API_PORT") or 8000)
API_TIMEOUT = env_float("API_TIMEOUT", 5.0)
MEASUREMENT_LOG_DIR = os.getenv("MEASUREMENT_LOG_DIR", "measurements")
OUTBOX_PATH = os.getenv("OUTBOX_PATH", os.path.join(MEASUREMENT_LOG_DIR, "outbox.db"))
HEARTBEAT_INTERVAL = env_float("HEARTBEAT_INTERVAL", 2.0)
CLAIM_INTERVAL = env_float("CLAIM_INTERVAL", 1.0)  # s between polls for new jobs while idle
RENEW_INTERVAL = env_float("RENEW_INTERVAL", 1.0)  # s between lease renewals (API lease: 15 s)
UPLOAD_BATCH = int(os.getenv("UPLOAD_BATCH", 500))
