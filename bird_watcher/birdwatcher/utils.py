import filelock
from django.conf import settings
from time import sleep
from threading import Thread


def _start_birdwatcher():
    lock, stop_lock = filelock.FileLock(settings.LOCK_FILE), filelock.FileLock(settings.LOCK_FILE+'stop')
    with lock.acquire():
        from birdwatcher.management.commands.watch_motion import CapAndRecord
        cam_options = {}
        if settings.VID_FORCED_FRAMERATE > 0:
            cam_options['r'] = str(settings.VID_FORCED_FRAMERATE)
        
        c = CapAndRecord(cam_options={"input_format":settings.VID_INPUT_FORMAT,
                                    "videosize":settings.VID_RESOLUTION, **cam_options},
                        movement_check=settings.MOTION_CHECKS_PER_SECOND,
                        before_movement=settings.RECORD_SECONDS_BEFORE_MOVEMENT,
                        after_movement=settings.RECORD_SECONDS_AFTER_MOVEMENT,
                        motion_threshold=settings.MOTION_DETECTION_THRESHOLD)
        c.start()
        while not stop_lock.is_locked:
            sleep(0.5) #poll to see if stop is demanded
        #if stop demanded then stop threads
        c.stop()
    

def _kill_and_start_birdwatcher(start_new_birdwatcher=True):
    lock, stop_lock = filelock.FileLock(settings.LOCK_FILE), filelock.FileLock(settings.LOCK_FILE+'stop')
    try:
        with stop_lock.acquire(blocking=False):
            #Get the stop_lock (if locked the birdwatcher will detect it and stop itself)
            
            #wait for birdwatcher to stop (will return immediately if it's not running)
            with lock.acquire(timeout=5): pass
            
        #start new birdwatcher
        if start_new_birdwatcher:
            _start_birdwatcher()
            
    except filelock.Timeout:
        #another thread/process is restarting so nothing to do
        pass
    
def kill_and_restart_birdwatcher(start_new_birdwatcher=True):
    Thread(target=_kill_and_start_birdwatcher,
           kwargs={"start_new_birdwatcher":start_new_birdwatcher}).start()