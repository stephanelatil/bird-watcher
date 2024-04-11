from django.conf import settings
from django.core.management import BaseCommand
from birdwatcher.utils import setup_logging
import uvicorn

class Command(BaseCommand):
    def add_arguments(self, parser):
        return
    
    def handle(self, *args, **options):
        setup_logging()
        uvicorn.run('bird_watcher_proj.asgi:app',
                    host=settings.WEBAPP_HOST,
                    port=settings.WEBAPP_PORT,
                    workers=3,
                    log_level=settings.LOGGING_LEVEL.lower())