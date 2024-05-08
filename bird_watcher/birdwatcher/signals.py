from django.dispatch import receiver
from constance.signals import config_updated
from birdwatcher.utils import start_or_restart_birdwatcher, watcher_is_running
from django.conf import settings
import logging

logger = logging.getLogger(settings.PROJECT_NAME)

@receiver(config_updated)
def start_or_restart_birdwatcher_process(sender, key, old_value, new_value, **kwargs):
    logging.debug(f"Signal: config_update triggered with key {key}: '{old_value}' -> '{new_value}'")
    config_keys_that_need_restart = ["VID_OUTPUT_PXL_FORMAT","VID_RESOLUTION",
                                    "VID_INPUT_FORMAT","VID_FORCED_FRAMERATE",
                                    "MOTION_CHECKS_PER_SECOND","MOTION_DETECTION_THRESHOLD",
                                    "RECORD_SECONDS_BEFORE_MOVEMENT","RECORD_SECONDS_AFTER_MOVEMENT"]
    if key in config_keys_that_need_restart and watcher_is_running():
        try:
            start_or_restart_birdwatcher()
        except:
            pass