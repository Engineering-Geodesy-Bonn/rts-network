import logging
from rtsworker import tasks
from rtsworker.dtos import RTSJobType
from rtsworker.worker import Worker

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(message)s")

task_mapping = {
    RTSJobType.CHANGE_FACE: tasks.change_face,
    RTSJobType.DUMMY_TRACKING: tasks.dummy_tracking,
    RTSJobType.TEST_CONNECTION: tasks.test_rts,
    RTSJobType.TRACK_PRISM: tasks.track_prism,
    RTSJobType.TURN_TO_TARGET: tasks.turn_to_target,
    RTSJobType.ADD_STATIC_MEASUREMENT: tasks.add_single_measurement_dummy,
}


def main():
    worker = Worker(task_mapping)
    worker.run()


if __name__ == "__main__":
    main()
