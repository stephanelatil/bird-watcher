from django.dispatch import receiver
from constance.signals import config_updated
from birdwatcher.utils import start_or_restart_birdwatcher, watcher_is_running
from django.conf import settings
import logging

logger = logging.getLogger(settings.PROJECT_NAME)
