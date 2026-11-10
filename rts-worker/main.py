import logging
import os
import signal

from rtsworker.worker import Worker

logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO").upper(),
    format="%(asctime)s %(levelname)-7s %(name)s: %(message)s",
)


def main():
    worker = Worker()
    for sig in (signal.SIGTERM, signal.SIGINT):
        signal.signal(sig, lambda *_: worker.request_shutdown())
    worker.run()


if __name__ == "__main__":
    main()
