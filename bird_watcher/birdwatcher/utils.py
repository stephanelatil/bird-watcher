import logging.config
import logging.handlers
import filelock, sys
from django.conf import settings
from threading import Thread
from subprocess import Popen
from pathlib import Path
import logging.config
import logging.handlers
import atexit
from os import remove
from json import load

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
    def get_handler_by_name(name) -> logging.Handler|None:
        for h in logging.getLogger().handlers:
            if h.name == name:
                return h
        return None
    #setup logging config
    config_file = Path("birdwatcher/logging_config.json")
    with open(config_file, 'r') as f:
        config = load(f)
    logging.config.dictConfig(config)
    
    #start logging thread
    queue_handler = get_handler_by_name("queue_handler")
    if isinstance(queue_handler, logging.handlers.QueueHandler):
        listener = logging.handlers.QueueListener(
            queue_handler.queue,
            config["handlers"]["queue_handler"]["handlers"],
            respect_handler_level=True)
        listener.start()
        atexit.register(listener.stop)
        
def watcher_is_running() -> bool:
    lock = filelock.FileLock(settings.LOCK_FILE)
    return lock.is_locked
