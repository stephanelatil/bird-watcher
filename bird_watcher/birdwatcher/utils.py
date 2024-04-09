import logging.config
import logging.handlers
import filelock, sys
from django.conf import settings
from threading import Thread
from subprocess import Popen
import logging
import logging.handlers
from multiprocessing import Queue
import atexit
from os import remove

def _kill_birdwatcher():
    lock, stop_lock = filelock.FileLock(settings.LOCK_FILE), filelock.FileLock(settings.LOCK_FILE+'stop')
    try:
        with stop_lock.acquire(blocking=False):
            # Get the stop_lock (if locked the birdwatcher will detect it and stop itself)
            # wait for birdwatcher to stop (will return immediately if it's not running)
            with lock.acquire(timeout=5): pass                   
    except filelock.Timeout:
        #another thread/process is restarting so nothing to do
        pass
    
def delete_lock_file_on_delete(*args, **kwargs):
    #release locks
    for lock in (filelock.FileLock(settings.LOCK_FILE+'stop'),
                 filelock.FileLock(settings.LOCK_FILE)):
        try:
            remove(settings.LOCK_FILE)
        except:
            pass
    

def kill_and_restart_birdwatcher(start_new_birdwatcher=True):
    if start_new_birdwatcher:
        #kills and restarts in new process
        Popen([sys.executable, 'manage.py', "watch_motion", "--kill-existing"])
    else:
        #just kills birdwatcher
        Thread(target=_kill_birdwatcher, daemon=True).start()

def setup_logging():
    root_logger = logging.getLogger()
    
    #create formatters here
    
    simple_formatter = logging.Formatter("[{levelname}]: {message}",
                               datefmt="%Y/%m/%d-T%H:%M:%S%z",
                               style='{')
    detailed_formatter = logging.Formatter("[{levelname}|{filename}|L_{lineno}] {asctime}: {message}",
                               datefmt="%Y/%m/%d-T%H:%M:%S%z",
                               style='{')
    
    #Create filters here (if applicable)
    
    #create handlers here
    stdout_handler = logging.StreamHandler(sys.stderr)
    stdout_handler.setFormatter(simple_formatter)
    stdout_handler.setLevel(logging.WARNING)
    
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

def watcher_is_running() -> bool:
    lock = filelock.FileLock(settings.LOCK_FILE)
    return lock.is_locked
