from django.apps import AppConfig


class BirdwatcherConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'birdwatcher'
    _lock_file = name+'.lock'
    
    def ready(self) -> None:
        from birdwatcher import signals
        super().ready()
        