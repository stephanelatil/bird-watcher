import cv2, io
import numpy as np
from threading import Thread
from multiprocessing import Queue
from pathlib import Path
import av, logging, math, zoneinfo
from datetime import datetime
from collections import deque
from django.conf import settings
from constance import config
from django.core.management import BaseCommand
from birdwatcher.models import Video
from birdwatcher.utils import setup_logging, FrameConsumer, get_datetime_local
from os import path, chmod
from time import perf_counter
import signal
from ultralytics import YOLO

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
        logger.debug("Interrupting threads")
        if global_interrupt:
            StaticThreadInterrupt.interrupt_all()

class VideoWriter(Interruptable):
    def __init__(self, filename, creation_time=None, initial=None, codec="libx264", fps=30, height=1080, width=1920) -> None:
        #ensure assets dir exists
        Path(settings.MEDIA_ROOT).joinpath(settings.VIDEOS_DIRECTORY).mkdir(0o755, True, True)
        Path(settings.MEDIA_ROOT).joinpath(settings.THUMBNAIL_DIRECTORY).mkdir(0o755, True, True)
        
        logger.debug("Starting video writer")
        self._frame_queue = Queue()
        self._initial = initial if isinstance(initial, (tuple, list)) else []
        self._codec = codec
        self._fps = fps
        self._resolution = (height, width)
        self._write_thread = Thread(target=self._start_write, kwargs={"filename":filename, "creation_time":creation_time})
        super().__init__(self._write_thread)
        logger.debug("Starting Video Writer Thread")
        self._write_thread.start()
        
    def _start_write(self, filename, creation_time):
        #Create thumbnail
        if len(self._initial) > 0:
            #if there are images in the ring buffer use the most recent as thumbnail
            thumbnail_frame = self._initial[-1]
        else:
            #Otherwise take the first next frame
            thumbnail_frame = self._frame_queue.get(True)
            self._frame_queue.put_nowait(thumbnail_frame)
        _, thumbnail = cv2.imencode(".webp", cv2.cvtColor(thumbnail_frame, cv2.COLOR_BGR2RGB),
                    [cv2.IMWRITE_WEBP_QUALITY, 95])
        thumbnail = np.array(thumbnail).tobytes()
        thumbnail = io.BytesIO(thumbnail)
        logger.debug("Generating thumbnail")
        logger.info(f"Starting video write with codec:{self._codec} and {self._fps} fps")

        file_path = str(path.join(settings.MEDIA_ROOT, settings.VIDEOS_DIRECTORY, filename))
        stream_options = {'movflags':'+faststart', "crf":"18"}
        container = av.open(file_path, mode="w")
        stream:av.VideoStream = container.add_stream(self._codec, rate=self._fps, options=stream_options)
        stream.height,stream.width = self._resolution
        # stream.pix_fmt = settings.VID_OUTPUT_PXL_FORMAT
        logger.debug(f"Creating video file \"{file_path}\"")
        
        vid = Video.objects.create(video_file=file_path,
                                   num_frames=len(self._initial),
                                   framerate=self._fps)
        
        vid_time = creation_time or get_datetime_local()
        vid.title = vid_time.strftime("%A %-d %b %Y, %H:%M:%S")
        vid.thumbnail_file.save(str(vid.pk).rjust(7,'0')+'.webp', thumbnail)
        vid.save()
        logger.debug(f"Created video entry pk={vid.pk} and saved thumbnail")
        
        #write initial buffer
        for frame in self._initial:
            frame = av.VideoFrame.from_ndarray(frame, format="rgb24")
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
            container.mux(stream.encode(frame))
            vid.num_frames += 1


        vid.save()
        logger.debug(f"Wrote all {vid.num_frames} frames and flushing final data")
        #flush steam
        for packet in stream.encode():
            container.mux(packet)
        container.close()
        logger.debug(f"Video container written fully")
        logger.info(f"Video {vid.title} done : written all {vid.num_frames} frames.")
    
    def write_frame(self, frame):
        self._frame_queue.put_nowait(frame)
    
    def close(self):
        if self.is_interrupted:
            return #already interrupted
        logger.debug('Stopping writer thread')
        self.interrupt()
        self._write_thread.join()
        
class MotionDetector:
    def __init__(self, check_area:tuple[tuple[float,float],tuple[float,float]],
                 shrink_ratio=1/16, background_fade_rate=0.8,
                 mov_check_every=5, mov_on_frame_amount=0.1) -> None:
        self._check_area = np.rint(check_area).astype(int)
        #make sure check area is at least 1px by 1px in size Otherwise possible div by 0 errors
        for i in range(2):
            if self._check_area[0][i] == self._check_area[1][i]:
                self._check_area[0][i] = max(0, self._check_area[0][i]-1)
                if self._check_area[0][i] == 0:
                    self._check_area[1][i] += 1
        # _shrink_ratio is how much to scale the frame before doing motion detection on: Less pixels = less power needed
        # Here we calculate the shrink ratio to make both the X and Y 60 pix wide/tall and average the two. 
        self._shrink_ratio = (60/(check_area[1][1] - check_area[0][1]) + 60/(check_area[1][0] - check_area[0][0]))/2
        #we make sure the image is not upscaled (useless just adds noise and more overhead)
        self._shrink_ratio = min(1, self._shrink_ratio)
        #TODO select model in settings
        self._yolo = YOLO(model=path.join(settings.MODEL_DIR, "yolo11small-cls.pt"),
                          task="classify", verbose=settings.DEBUG)
        self._yolo_resize = (224,224)
        self._motion_sensitivity = config.MOTION_SENSITIVITY_THRESHOLD
        self._background = np.zeros((0,0)) #no detected background yet
        self._background_fade_rate = background_fade_rate
        self._mov_check_every = mov_check_every
        self._frame_check_num = 0
        self._mov_on_frame_amount = mov_on_frame_amount
        logger.debug("Starting Motion Detector")
    
    def _gray_and_resize_frame(self, frame:cv2.typing.MatLike) -> cv2.typing.MatLike:
        #select only the part of the frame to consider
        frame = frame[self._check_area[0][0]:self._check_area[1][0],
                      self._check_area[0][1]:self._check_area[1][1],:]
        # frame = cv2.cvtColor(frame, cv2.COLOR_RGB2GRAY)
        return cv2.resize(frame, self._yolo_resize) #resize image to pass to YOLO for detection
        #pass a (0,0) destination size so that it will be auto determined by the shrink ratio
        if self._shrink_ratio == 1:
            return frame #no resize needed
        return cv2.resize(frame, (0,0), fx=self._shrink_ratio, fy=self._shrink_ratio)
    
    def update_background(self, normalized_frame):
        self._background = self._background * self._background_fade_rate/(1+self._background_fade_rate) + normalized_frame/(1+self._background_fade_rate)
        self._background = self._background.astype(np.uint8)
    
    def has_movement(self, frame:cv2.typing.MatLike) -> bool:
        #need movement check?
        self._frame_check_num += 1
        if self._frame_check_num <= self._mov_check_every:
            return False #no check
        self._frame_check_num = 0
        
        frame = self._gray_and_resize_frame(frame)
        # if self._background.shape[0] == 0: #no background yet
        #     self._background = frame
        #     return False
        
        # diff = cv2.absdiff(self._background, frame)
        # self.update_background(frame)
        # _,diff = cv2.threshold(diff, self._motion_sensitivity, 255, cv2.THRESH_BINARY)
        # num_pixels_theshold = self._mov_on_frame_amount*diff.shape[0]*diff.shape[1]
        # nonZero = cv2.countNonZero(diff)
        # if nonZero > num_pixels_theshold/2 and not nonZero > num_pixels_theshold:
        #     logging.debug(f"Motion check 1/2-MVNT {nonZero}/{num_pixels_theshold}")
        # if nonZero > num_pixels_theshold:
        #     logging.debug(f"Motion check MOVEMENT {nonZero}/{num_pixels_theshold}")
        #     return True
        # logging.debug(f"Motion check nothing: {nonZero}/{num_pixels_theshold}")
        # return False
        
        result = self._yolo.predict(frame, conf=0.7, imgsz=frame.shape[0], max_det=5,
                                    #Need to edit classes here to consider all animals
                                    classes=[14,15,16])[0] #get the result
        return False if result.probs is None else result.probs.top1conf.item() > 0.75

class CamInterface:
    def __init__(self, options=None):
        if options is None:
            options = {}    
        # logger.debug(f"Starting CamInterface on {settings.VID_CAMERA_DEVICE} with options: {options}")
        logger.debug("Starting CamInterface with CV2 v4l2")
        self._inner_gen = None
        self._start_cam()
        
        frame = self._frame_generator.__next__()
        # get fps
        start = perf_counter()
        frame_setup_count = 10
        for i in range(frame_setup_count):
            frame = self._frame_generator.__next__()
        self._fps = int(math.ceil(frame_setup_count/(perf_counter()-start)))

        logger.debug(f"Read {frame_setup_count} frames in {(perf_counter()-start)} seconds for {self._fps} fps")
        self._resolution = frame.shape[:2]
        logger.debug(f"CamInterface started with resolution {self._resolution} and {self._fps} FPS")
        
    def get_next_frame(self):
        return self._frame_generator.__next__()
    
    def _start_cam(self):
        if settings.DEVICE_DUPLICATION.lower() == 'socket':
            self._camera = FrameConsumer()
        else:
            self._camera = cv2.VideoCapture(settings.VID_CAMERA_DEVICE, cv2.CAP_V4L2)
            try:
                width, height = str(config.VID_RESOLUTION).split('x',1)
                self._camera.set(cv2.CAP_PROP_FRAME_WIDTH, int(width))
                self._camera.set(cv2.CAP_PROP_FRAME_HEIGHT, int(height))
            except: pass
    
    def _get_frame_gen(self):
        try:
            while 1:
                if self._camera is None:
                    self._start_cam()
                check, frame = self._camera.read()
                if check:
                    yield cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                else:
                    logger.info("Camera issue. Stopping recorder")
                    break
        finally:
            if not self._camera is None:
                self._camera.release()
            self._camera = None
            self._inner_gen = None
    
    @property
    def _frame_generator(self):
        if self._inner_gen is None:
            self._inner_gen = self._get_frame_gen()
        return self._inner_gen
    
    @property
    def frame_rate(self):
        return self._fps
    
    @property
    def resolution(self) -> tuple[int,int]:
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
        self._check_area = (
            (config.MOTION_DETECT_AREA_TL_X*self._cam.resolution[0]/100.0,
             config.MOTION_DETECT_AREA_TL_Y*self._cam.resolution[1]/100.0),
            
            (config.MOTION_DETECT_AREA_BR_X*self._cam.resolution[0]/100.0,
             config.MOTION_DETECT_AREA_BR_Y*self._cam.resolution[1]/100.0)
        )
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
            motion = MotionDetector(self._check_area,
                                    shrink_ratio=max(0.001,min(100/max(self._check_area[1][0]-self._check_area[0][0], self._check_area[1][1]-self._check_area[1][0]),1)),
                                    mov_on_frame_amount=self._motion_threshold,
                                    mov_check_every=int(self._frame_movement_check))
            writer = None
            frames_without_motion = 0
            
            frame = self._cam.get_next_frame()
            frame_path = str(path.join(settings.STATICFILES_DIRS[0], "single_frame.webp"))
            try:
                chmod(frame_path, 0o666)
            except:
                pass
            cv2.imwrite(frame_path,
                        cv2.cvtColor(frame, cv2.COLOR_BGR2RGB),
                        [cv2.IMWRITE_WEBP_QUALITY, 95])
            
            while not self.is_interrupted:
                frame = self._cam.get_next_frame()
                frames_without_motion -= 1
                if frame is None:
                    raise EOFError('Camera interface is closed')
                self._frame_ring_buffer.append(frame)
                #check for movement
                #check only happens every nth frame (set in settings). Returns false on other frames
                if motion.has_movement(frame):
                    frames_without_motion = self._record_n_frames_without_movement
                        
                #motion detected within frame limit
                if frames_without_motion > 0:
                    if writer is None:
                        localtime = get_datetime_local()
                        writer = VideoWriter(localtime.strftime("%Y-%m-%d_%H-%M-%S.mp4"),
                                             creation_time=localtime,
                                            initial=list(self._frame_ring_buffer),
                                            fps=self._cam.frame_rate,
                                            height=self._cam.resolution[0],
                                            width=self._cam.resolution[1])
                        # self._frame_ring_buffer.clear()
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
                                    "videosize":config.VID_RESOLUTION, **cam_options},
                        movement_check=1.0/config.MOTION_CHECKS_PER_SECOND,
                        before_movement=config.RECORD_SECONDS_BEFORE_MOVEMENT,
                        after_movement=config.RECORD_SECONDS_AFTER_MOVEMENT,
                        motion_threshold=config.MOTION_DETECTION_THRESHOLD)
        #register sigterm signal handler
        signal.signal(signal.SIGTERM, lambda *a, **kw : c.stop())
        c.start()
        try:
            logger.info("Motion detector started. Press Ctrl-C or SigTerm to stop")
            c._capThread.join()
        except KeyboardInterrupt: 
            logger.debug("Got keyboard interrupt")
        except EOFError: pass
        finally:
            c.stop()
        c._capThread.join() #ensure to wait forever or until stop