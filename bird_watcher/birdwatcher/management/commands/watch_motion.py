import cv2, io
import numpy as np
from threading import Thread
from multiprocessing import Queue
from pathlib import Path
import av, logging, atexit
from datetime import datetime
from collections import deque
from django.conf import settings
from django.core.management import BaseCommand
from birdwatcher.models import Video
from birdwatcher.utils import setup_logging
from os import path
from time import perf_counter

logger = logging.getLogger(settings.PROJECT_NAME)

class StaticThreadInterrupt:
    _INTERRUPT = False
    _subscribers:list[Thread] = []

    def __init__(self) -> None:
        pass
    
    @staticmethod
    def is_interrupted():
        return StaticThreadInterrupt._INTERRUPT
    
    @staticmethod
    def interrupt_all():
        StaticThreadInterrupt._INTERRUPT = True
        threads = StaticThreadInterrupt._subscribers.copy()
        while len(threads) > 0:
            for i in range(len(threads)-1, -1, -1):
                #join in reverse order to ensure that the pop() will not kill the iterator
                threads[i].join()
                if not threads[i].is_alive():
                    threads.pop(i)

    @staticmethod
    def subscribe(joinable):
        StaticThreadInterrupt._subscribers.append(joinable)
        
class Interruptable:
    def __init__(self, thread:Thread) -> None:
        self._interrupted = False
        self._thread = thread
    
    def subscribe(self):
        StaticThreadInterrupt.subscribe(self._thread)
    
    @property
    def is_interrupted(self):
        return self._interrupted or StaticThreadInterrupt.is_interrupted()
    
    def interrupt(self, global_interrupt=False):
        self._interrupted = True
        if global_interrupt:
            StaticThreadInterrupt.interrupt_all()

class VideoWriter(Interruptable):
    def __init__(self, filename, initial=None, codec="h264_omx", fps=30, height=1080, width=1920) -> None:
        #ensure assets dir exists
        Path(settings.MEDIA_ROOT).joinpath(settings.VIDEOS_DIRECTORY).mkdir(0o755, True, True)
        Path(settings.MEDIA_ROOT).joinpath(settings.THUMBNAIL_DIRECTORY).mkdir(0o755, True, True)
        
        logger.debug("Starting video writer")
        self._frame_queue = Queue()
        self._initial = initial if isinstance(initial, (tuple, list)) else []
        self._codec = codec
        self._fps = fps
        self._resolution = (height, width)
        self._write_thread = Thread(target=self._start_write, kwargs={"filename":filename})
        super().__init__(self._write_thread)
        logger.debug("Starting Video Writer Thread")
        self._write_thread.start()
        
    def _start_write(self, filename):
        #Create thumbnail
        if len(self._initial) > 0:
            #if there are images in the ring buffer use the most recent as thumbnail
            thumbnail_frame = self._initial[-1]
        else:
            #Otherwise take the first next frame
            # TODO can stay stuck here if interrupted
            thumbnail_frame = self._frame_queue.get(True)
            self._frame_queue.put_nowait(thumbnail_frame)
        _, thumbnail = cv2.imencode(".webp", cv2.cvtColor(thumbnail_frame, cv2.COLOR_BGR2RGB),
                    [cv2.IMWRITE_WEBP_QUALITY, 95])
        thumbnail = np.array(thumbnail).tobytes()
        thumbnail = io.BytesIO(thumbnail)
        logger.debug("Generating thumbnail")
        logger.info(f"Starting video write with codec:{self._codec} and {self._fps} fps")

        file_path = str(path.join(settings.MEDIA_ROOT, settings.VIDEOS_DIRECTORY, filename))
        container = av.open(file_path, mode="w")
        stream = container.add_stream(self._codec, rate=self._fps)
        stream.height,stream.width = self._resolution
        stream.pix_fmt = settings.VID_OUTPUT_PXL_FORMAT
        stream.options = {'movflags':'+faststart', "crf":"18"}
        logger.debug(f"Creating video file \"{file_path}\"")
        
        vid = Video.objects.create(video_file=file_path,
                             num_frames=len(self._initial),
                             framerate=self._fps)
        vid.thumbnail_file.save(str(vid.pk).rjust(7,'0')+'.webp', thumbnail)
        vid.save()
        logger.debug(f"Created video entry pk={vid.pk} and saved thumbnail")
        
        #write initial buffer
        for frame in self._initial:
            frame = av.VideoFrame.from_ndarray(frame, format="rgb24")            
            # for packet in stream.encode(frame):
            #     container.mux(packet)
            container.mux(stream.encode(frame))
        logger.debug(f"Wrote first {len(self._initial)} frames")
        del self._initial #clear mem
                
        #write other frames
        while not self.is_interrupted or not self._frame_queue.empty():
            try:
                f = self._frame_queue.get(block=True, timeout=0.1)
            except:
                f = None
                continue
            frame = av.VideoFrame.from_ndarray(f, format="rgb24")            
            for packet in stream.encode(frame):
                container.mux(packet)
            vid.num_frames += 1


        vid.save()
        logger.debug(f"Wrote all {vid.num_frames} frames and flushing final data")
        #flush steam
        for packet in stream.encode():
            container.mux(packet)
        container.close()
        logger.debug(f"Video container written fully")
    
    def write_frame(self, frame):
        self._frame_queue.put_nowait(frame)
    
    def close(self):
        if self.is_interrupted:
            return #already interrupted
        logger.debug('Stopping writer thread')
        self.interrupt()
        self._write_thread.join()
        
class MotionDetector:
    def __init__(self, shrink_ratio=1/12, background_fade_rate=0.7, mov_check_every=5, mov_on_frame_amount=0.1) -> None:
        self._shrink_ratio = shrink_ratio
        self._background = np.zeros((0,0)) #no detected background yet
        self._background_fade_rate = background_fade_rate
        self._mov_check_every = mov_check_every
        self._frame_check_num = 0
        self._mov_on_frame_amount = mov_on_frame_amount
        logger.debug("Starting Motion Detector")
    
    def _gray_and_resize_frame(self, frame:cv2.typing.MatLike) -> cv2.typing.MatLike:
        frame = cv2.cvtColor(frame, cv2.COLOR_RGB2GRAY)
        #pass a (0,0) destination size so that it will be auto determined by the shrink ratio
        return cv2.resize(frame, (0,0), fx=self._shrink_ratio, fy=self._shrink_ratio)
    
    def update_backgroud(self, normalized_frame):
        self._background = self._background * self._background_fade_rate/(1+self._background_fade_rate) + normalized_frame/(1+self._background_fade_rate)
        self._background = self._background.astype(np.uint8)
    
    def has_movement(self, frame:cv2.typing.MatLike) -> bool:
        #need movement check?
        self._frame_check_num += 1
        if self._frame_check_num <= self._mov_check_every:
            return False #no check
        self._frame_check_num = 0
        
        frame = self._gray_and_resize_frame(frame)
        if self._background.shape[0] == 0: #no background yet
            self._background = frame
            return False
        
        diff = cv2.absdiff(self._background, frame)
        self.update_backgroud(frame)
        _,diff = cv2.threshold(diff, 45, 255, cv2.THRESH_BINARY)
        num_pixels_theshold = self._mov_on_frame_amount*diff.shape[0]*diff.shape[1]
        nonZero = cv2.countNonZero(diff)
        if nonZero > num_pixels_theshold/2:
            logging.debug(f"Motion check 1/2-MVNT {nonZero}/{num_pixels_theshold}")
        if nonZero > num_pixels_theshold:
            logging.debug(f"Motion check MOVEMENT {nonZero}/{num_pixels_theshold}")
            return True
        logging.debug(f"Motion check nothing: {nonZero}/{num_pixels_theshold}")
        return False

class CamInterface:
    def __init__(self, options=None):
        if options is None:
            options = {}
        # logger.debug(f"Starting CamInterface on {settings.VID_CAMERA_DEVICE} with options: {options}")
        logger.debug("Starting CamInterface with CV2 v4l2")
        self._inner_gen = None
        self._start_cam()
        
        start = perf_counter()
        frame_setup_count = 10
        for i in range(frame_setup_count):
            frame = next(self._frame_generator)

        self._fps = round((perf_counter()-start)/frame_setup_count,2)
        self._resolution = frame.shape[:2]
        logger.debug(f"CamInterface started with resolution {self._resolution} and {self._fps} FPS")
        
    def get_next_frame(self):
        return next(self._frame_generator,None)
    
    def _start_cam(self):
        self._camera = cv2.VideoCapture(settings.STREAM_VID_DEVICE, cv2.CAP_V4L2)
        try:
            width, height = str(settings.VID_RESOLUTION).split('x',1)
            self._camera.set(cv2.CAP_PROP_FRAME_WIDTH, int(width))
            self._camera.set(cv2.CAP_PROP_FRAME_HEIGHT, int(height))
        except: pass
    
    def _get_frame_gen(self):
        err_count = 0
        while err_count < 10:
            if self._camera is None:
                self._start_cam()
            check, frame = self._camera.read()
            if check:
                yield cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            else:
                err_count += 1
        if not self._camera is None:
            self._camera.release()
        self._camera = None
        raise StopIteration()
    
    @property
    def _frame_generator(self):
        if self._inner_gen is None:
            self._inner_gen = self._get_frame_gen()
        return self._inner_gen
    
    @property
    def frame_rate(self):
        return self._fps
    
    @property
    def resolution(self):
        return self._resolution
    
    def close(self):
        if not self._camera is None:
            self._camera.release()
            self._camera = None
        
class CapAndRecord(Interruptable):
    def __init__(self, movement_check=0.5, after_movement=3, before_movement=3, motion_threshold=0.07,
                 cam_options=None) -> None:
        if cam_options is None:
            cam_options = {}
        self._cam = CamInterface(options=cam_options)
        self._capThread = Thread(target=self._run, daemon=False)
        super().__init__(self._capThread)
        self._frame_movement_check = self._cam.frame_rate*movement_check
        self._record_n_frames_without_movement = self._cam.frame_rate*after_movement
        self._frame_ring_buffer = deque(maxlen=int(self._cam.frame_rate*before_movement))
        self._motion_threshold = motion_threshold
        logger.debug(f"Motion Detection and capture created: Check every {self._frame_movement_check} frames")
    
    def _run(self):
        try:
            logger.info("Motion Detection and Capture starting")
            motion = MotionDetector(shrink_ratio=1/20, mov_on_frame_amount=self._motion_threshold,
                                    #mov check twice a sec
                                    mov_check_every=int(self._frame_movement_check))
            writer = None
            frames_without_motion = 0
            
            while not self.is_interrupted:
                frame = self._cam.get_next_frame()
                frames_without_motion -= 1
                if frame is None:
                    raise EOFError('Camera interface is closed')
                self._frame_ring_buffer.append(frame)
                #on every nth frame check for movement
                if motion.has_movement(frame):
                    frames_without_motion = self._record_n_frames_without_movement
                        
                #motion detected within frame limit
                if frames_without_motion > 0:
                    if writer is None:
                        writer = VideoWriter(datetime.now().strftime("%Y-%m-%d_%H-%M-%S.mp4"),
                                            initial=list(self._frame_ring_buffer),
                                            fps=self._cam.frame_rate,
                                            height=self._cam.resolution[0],
                                            width=self._cam.resolution[1])
                        self._frame_ring_buffer.clear()
                    writer.write_frame(frame)
                elif not writer is None: #otherwise close writer if open
                    logger.debug(f"No motion detected for {frames_without_motion}. Stopping writer")
                    writer.close()
                    writer = None
        except:
            logger.exception("Error in CapAndRecord")
        finally:
            #flush and close all
            if not writer is None:
                writer.close()
            self._cam.close()
            logger.info("Motion Detection and Capture Thread stopping")
            
    def start(self):
        self._capThread.start()

    def stop(self):
        logger.debug(f"Motion Detection and capture STOP requested")
        #interrupts all threads and joins them
        self.interrupt(global_interrupt=True)
        self._capThread.join() #last join just for good measure
        logger.debug(f"Motion Detection and capture stopped successfully")


class Command(BaseCommand):
    def add_arguments(self, parser):
        return
    
    def handle(self, *args, **options):
        setup_logging()
        
        cam_options = {}
        if settings.VID_FORCED_FRAMERATE > 0:
            cam_options['r'] = str(settings.VID_FORCED_FRAMERATE)
        
        c = CapAndRecord(cam_options={"input_format":settings.VID_INPUT_FORMAT,
                                    "videosize":settings.VID_RESOLUTION, **cam_options},
                        movement_check=1.0/settings.MOTION_CHECKS_PER_SECOND,
                        before_movement=settings.RECORD_SECONDS_BEFORE_MOVEMENT,
                        after_movement=settings.RECORD_SECONDS_AFTER_MOVEMENT,
                        motion_threshold=settings.MOTION_DETECTION_THRESHOLD)
        atexit.register(c.stop)
        c.start()
        try:
            input("Press enter to stop detecting motion.")
        except KeyboardInterrupt: pass
        except EOFError: pass
