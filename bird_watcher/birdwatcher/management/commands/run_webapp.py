from django.conf import settings
from constance import config
from django.core.management import BaseCommand
from birdwatcher.utils import setup_logging, start_or_restart_birdwatcher
import uvicorn

class Command(BaseCommand):
    def add_arguments(self, parser):
        return
    
    def handle(self, *args, **options):
        setup_logging()
        if config.START_MOTION_DETECTOR_ON_SERVER_START:
            start_or_restart_birdwatcher()
        uvicorn.run('bird_watcher_proj.asgi:app',
                    host=settings.WEBAPP_HOST,
                    port=settings.WEBAPP_PORT,
                    workers=3,
                    log_level=settings.LOGGING_LEVEL.lower())