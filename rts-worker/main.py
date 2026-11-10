import logging
import os

from rtsworker.worker import Worker

logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO").upper(),
    format="%(asctime)s %(levelname)-7s %(name)s: %(message)s",
)


def main():
    Worker().run()


if __name__ == "__main__":
    main()
