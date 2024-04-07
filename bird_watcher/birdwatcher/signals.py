from django.conf import settings
from django.dispatch import receiver
import filelock
from os import remove
from constance.signals import config_updated
from birdwatcher.utils import kill_and_restart_birdwatcher


def delete_lock_file_on_delete(*args, **kwargs):
    #release locks
    for lock in (filelock.FileLock(settings.LOCK_FILE+'stop'),
                 filelock.FileLock(settings.LOCK_FILE)):
        try:
            lock.release(force=True)
            if lock.is_locked:
                remove(settings.LOCK_FILE)
        except:
            pass
    raise KeyboardInterrupt()

@receiver(config_updated)
def start_or_restart_birdwatcher_process(sender, key, old_value, new_value, **kwargs):
    config_keys_that_need_restart = ["VID_OUTPUT_PXL_FORMAT",
                                    "VID_CAMERA_FORMAT","VID_RESOLUTION",
                                    "VID_INPUT_FORMAT","VID_FORCED_FRAMERATE",
                                    "MOTION_CHECKS_PER_SECOND","MOTION_DETECTION_THRESHOLD",
                                    "RECORD_SECONDS_BEFORE_MOVEMENT","RECORD_SECONDS_AFTER_MOVEMENT"]
    if key in config_keys_that_need_restart:
        kill_and_restart_birdwatcher(start_new_birdwatcher=True)