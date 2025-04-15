import time
import logging
from typing import Callable, Dict

from rtsworker import api
from rtsworker.dtos import RTSJobResponse, RTSJobStatus, RTSJobType

logger = logging.getLogger("root")

SLEEP_TIME = 0.25


class Worker:

    def __init__(self, task_mapping: Dict[RTSJobType, Callable[[RTSJobResponse], None]]):
        self.task_mapping = task_mapping

    def _run_task(self, job: RTSJobResponse):
        try:
            task = self.task_mapping[job.job_type]
            task(job)
        except Exception as e:
            api.update_job_status(job.job_id, RTSJobStatus.FAILED)
            logger.error(e)

    def run(self):
        while True:
            try:
                job = api.fetch_new_job()

                if job is None:
                    logger.info("No job found")
                    time.sleep(SLEEP_TIME)
                    continue

                logger.info(f"Found job: {job.job_id}")
                # Reserving the job
                api.update_job_status(
                    job.job_id, RTSJobStatus.RUNNING
                )  # try it but do not set the job on failed if it fails
                self._run_task(job)

            except KeyboardInterrupt:
                break
            except Exception as e:
                logger.error(e)
            finally:
                time.sleep(SLEEP_TIME)
