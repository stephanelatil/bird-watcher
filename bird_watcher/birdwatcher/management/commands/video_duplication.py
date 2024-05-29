from constance import config
from django.conf import settings
from django.core.management import BaseCommand
from birdwatcher.utils import setup_logging, FramePublisher
from subprocess import Popen, DEVNULL
from signal import SIGINT, SIGKILL, SIGTERM, signal
import asyncio
from threading import Thread
import atexit

class Command(BaseCommand):
    def add_arguments(self, parser):
        return
    
    def handle(self, *args, **options):
        setup_logging()
        method = settings.DEVICE_DUPLICATION
        if method.lower() == 'socket':
            pub = FramePublisher()
            try:
                signal(SIGTERM, lambda *args, **kwargs : (pub.release()))
                signal(SIGINT, lambda *args, **kwargs : (pub.release()))
                pub.start()
            finally:
                pub.release()
        
        elif method.lower() == 'v4l2loopback':
            def killProc(p:Popen):
                p.send_signal(SIGINT)
                p.wait(2)
                if p.poll() is None:
                    p.send_signal(SIGKILL)
                exit(0)
                
            proc = Popen(["/usr/bin/ffmpeg", "-hide_banner", "-loglevel", "warning",
                          "-f", "v4l2", "-i", "/dev/video0", "-codec", "copy", "-f",
                          "v4l2", "/dev/video100"],
                         stdout=DEVNULL, stderr=DEVNULL)
            atexit.register(lambda : killProc(proc))
            signal(SIGTERM, lambda *args, **kwargs : killProc(proc))
            signal(SIGINT, lambda *args, **kwargs : killProc(proc))
            try:
                proc.wait()
            except KeyboardInterrupt:
                killProc(proc)
            except:
                pass
        else:
            #nothing to do for default (no duplication)
            try:
                input('')
            except KeyboardInterrupt:
                pass #no issue
            except:
                pass
