import time
import logging
from typing import Callable, Dict

import requests

from rtsworker import api
from rtsworker.dtos import RTSJobResponse, RTSJobStatus, RTSJobType

logger = logging.getLogger("root")

SLEEP_TIME = 1


class Worker:

    def __init__(self, task_mapping: Dict[RTSJobType, Callable[[RTSJobResponse, api.APIConfig], None]]):
        self.task_mapping = task_mapping
        self.api_config = api.APIConfig()
        self.initialize()

    def initialize(self):
        try:
            self.api_config.resolve()
            api.self_register(self.api_config)
        except Exception as e:
            logger.error(f"Initialization failed: {e}")

    def _run_task(self, job: RTSJobResponse):
        try:
            task = self.task_mapping[job.job_type]
            task(job, self.api_config)
        except Exception as e:
            logger.error(e)
            try:
                api.update_job_status(job.job_id, RTSJobStatus.FAILED, self.api_config)
            except Exception as status_error:
                logger.error(f"Could not mark job {job.job_id} as failed: {status_error}")

    def run(self):
        while True:
            try:
                job = api.fetch_new_job(self.api_config)

                if job is None:
                    logger.info("No job found")
                    time.sleep(SLEEP_TIME)
                    continue

                logger.info(f"Found job: {job.job_id}")
                # Reserving the job
                api.update_job_status(
                    job.job_id, RTSJobStatus.RUNNING, self.api_config
                )  # try it but do not set the job on failed if it fails
                self._run_task(job)

            except KeyboardInterrupt:
                break
            except requests.ConnectionError as e:
                logger.error(f"Lost connection to API: {e}")
                self.api_config.resolve()
            except Exception as e:
                logger.error(e)
            finally:
                time.sleep(SLEEP_TIME)
