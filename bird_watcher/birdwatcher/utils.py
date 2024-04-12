import logging.config
import logging.handlers
import sys
from django.conf import settings
import logging
import logging.handlers
from multiprocessing import Queue
import atexit
from pystemd.systemd1 import Unit

motion_detect_unit = Unit("birdwatcher-motion-detection.service")
motion_detect_unit.load()
logger = logging.getLogger(settings.PROJECT_NAME)

def kill_birdwatcher():
    logger.info("Stopping motion detection service")
    motion_detect_unit.Unit.Stop(b'replace')
    

def start_or_restart_birdwatcher():
    logger.info("Restarting motion detection service")
    motion_detect_unit.Unit.Restart(b'replace')
        
class ColoredSimpleFormatter(logging.Formatter):
    green = "\x1b[32m"
    yellow = "\x1b[33m"
    red = "\x1b[31m"
    bold_red = "\x1b[31m"
    reset = "\x1b[0m"

    FORMATS = {
        logging.DEBUG: green,
        logging.INFO: green,
        logging.WARNING: yellow,
        logging.WARN: yellow,
        logging.ERROR: red,
        logging.CRITICAL: bold_red,
        logging.ERROR: bold_red,
        logging.FATAL: bold_red
    }
    
    def __init__(self, fmt: str | None = None, datefmt: str | None = None,
                 validate: bool = True, *, defaults=None) -> None:
        self.style:logging._FormatStyle = '{'
        self.validate = validate
        super().__init__(fmt, datefmt, style=self.style, validate=validate, defaults=defaults)

    def format(self, record):
        log_fmt = self.FORMATS.get(record.levelno)
        fmt = self._fmt.replace('{levelname}', rf'{log_fmt}{{levelname}}{self.reset}')
        return logging.Formatter(fmt,
                                 datefmt=self.datefmt,
                                 style=self.style,
                                 validate=self.validate
                                 ).format(record)

def setup_logging():
    root_logger = logging.getLogger()
    
    #create formatters here
    simple_formatter = ColoredSimpleFormatter("{levelname}: {message}",
                               datefmt="%Y/%m/%d-T%H:%M:%S%z")
    detailed_formatter = logging.Formatter("[{levelname}|{filename}|L_{lineno}] {asctime}: {message}",
                               datefmt="%Y/%m/%d-T%H:%M:%S%z",
                               style='{')
    
    #Create filters here (if applicable)
    
    #create handlers here
    stdout_handler = logging.StreamHandler(sys.stdout)
    stdout_handler.setFormatter(simple_formatter)
    stdout_handler.setLevel(logging.getLevelName(settings.LOGGING_LEVEL))
    
    logfile_handler = logging.handlers.RotatingFileHandler("birdwatcher.log",
                                                           maxBytes=100_000, 
                                                           backupCount=2,
                                                           encoding='utf-8')
    logfile_handler.setFormatter(detailed_formatter)
    logfile_handler.setLevel(logging.INFO)
    
    # create queue handler
    queue_handler = logging.handlers.QueueHandler(Queue())
    listener = logging.handlers.QueueListener(queue_handler.queue,
                                              stdout_handler,
                                              logfile_handler,
                                              respect_handler_level=True)
    listener.start()
    atexit.register(listener.stop)
    
    # add queue handler to root logger for app
    root_logger.addHandler(queue_handler)
    root_logger.setLevel(logging.DEBUG)
    
    logger = logging.getLogger(settings.PROJECT_NAME)    
    logger.info(f"Logging successfully setup with level: {logging.getLevelName(stdout_handler.level)}")

def watcher_is_running() -> bool:
    return motion_detect_unit.Unit.ActiveState == b'active'
