import logging
import logging.config
import logging.handlers
import sys, os, select
import cv2
from socket import socket, AF_UNIX, SOCK_STREAM, SO_REUSEADDR, SOL_SOCKET
import numpy as np
from io import BytesIO
from django.conf import settings
from constance import config
import atexit
from struct import pack, unpack
from time import sleep
from multiprocessing import Semaphore, Condition, Lock, Queue
from multiprocessing.synchronize import Semaphore as _Semaphore_TYPE
from pystemd.systemd1 import Unit
from threading import Thread

motion_detect_unit = Unit("birdwatcher-motion-detection.service")
motion_detect_unit.load()
logger = logging.getLogger(settings.PROJECT_NAME)

def kill_birdwatcher():
    logger.debug("Stopping motion detection service")
    motion_detect_unit.Unit.Stop(b'replace')
    

def start_or_restart_birdwatcher():
    logger.debug("Restarting motion detection service")
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
    logger.debug(f"Logging successfully setup with level: {logging.getLevelName(stdout_handler.level)}")

def watcher_is_running() -> bool:
    try:
        return motion_detect_unit.Unit.ActiveState == b'active'
    except:
        return False
    
class BlockingSingleQueue:
    def __init__(self):
        self._lock = Lock()
        self._conditionVar = Condition(self._lock)
        self._value = None
        
    def put(self, value):
        with self._lock:
            self._value = value
            self._conditionVar.notify_all()
            
    def get(self):
        with self._lock:
            if self._value is None:
                self._conditionVar.wait()
            self._value, tmp = None,self._value
        return tmp

class FramePublisher:
    SOCKET_PATH = os.path.join(str(settings.BASE_DIR), "video_duplication_sock.s")
    
    def __init__(self) -> None:
        self._camera: cv2.VideoCapture|None = None
        self._connections:dict[socket,_Semaphore_TYPE] = dict()
        self._threads:list[Thread] = []
        self._stop = False
        self._broadcast_thread = Thread(target=self._broadcast_messages)
        
    def _send(self, sock, message):
        # Prefix each message with a 4-byte length (network byte order)
        message_length = len(message)
        message_header = pack('>I', message_length)
        sock.sendall(message_header + message)
        
    @property
    def _pause(self):
        return len(self._connections) == 0

    def handle_connection(self, connection:socket, release_sem:_Semaphore_TYPE):
        logger.debug("Handling new connection")
        connection.shutdown(0) #do not read (reads will not block and return wither b'' ot whatever is in its read buffer)
        self._connections[connection] = release_sem
        try:
            #wait forever until released, connection closed or force closed
            release_sem.acquire(True)
        finally:
            logger.debug("Connection released, clearing")
            connection.shutdown(2)
            connection.close()
            self._connections.pop(connection, None)

    def _broadcast_messages(self):
        logger.debug("Broadcasting to connected elements")
        try:
            while not self._stop:
                while self._pause:
                    # do not read frames for now
                    # Wait until frame request
                    sleep(0.3)
                    if self._stop:
                        return
                #get frame here
                check, frame = self._camera.read()
                buffer = BytesIO()
                if check:
                    np.save(buffer, frame, allow_pickle=False)
                    for conn,sem in self._connections.items():
                        try:
                            self._send(conn, buffer.getbuffer())
                        except: 
                            #connection failed. Maybe it's closed?
                            sem.release()
        finally:
            logger.debug("Releasing all connections")
            for sem in self._connections.values():
                sem.release()

    def start(self):
        self._camera = cv2.VideoCapture(settings.VID_CAMERA_DEVICE, cv2.CAP_V4L2)
        try:
            width, height = str(config.VID_RESOLUTION).split('x',1)
            self._camera.set(cv2.CAP_PROP_FRAME_WIDTH, int(width))
            self._camera.set(cv2.CAP_PROP_FRAME_HEIGHT, int(height))
        except:
            pass
        logger.debug("Started video capture")
        
        # make sure socket does not exist
        if os.path.exists(self.SOCKET_PATH):
            os.remove(self.SOCKET_PATH)
            #TODO add error handling
        logger.debug("Starting Unix socket")
        sock = socket(AF_UNIX, SOCK_STREAM)
        try:
            sock.setsockopt(SOL_SOCKET, SO_REUSEADDR, 1)
            sock.bind(self.SOCKET_PATH)
            sock.listen(1)
            
            self._broadcast_thread.start()
            
            while not self._stop:
                readlist, _, _ = select.select([sock], [], [], 0.1)
                if len(readlist) > 0:
                    conn,addr = sock.accept()
                    logger.debug("Got connection to unix socket")
                    t = Thread(target=self.handle_connection, args=(conn, Semaphore(0)))
                    self._threads.append(t)
                    t.start()
        finally:
            logger.debug("Stopping unix socket server")
            sock.close()
            self.release()
            
    def release(self):
        if self._stop:
            return
        self._stop = True
        logger.debug("Releasing Frame publisher")
        #make a copy to avoid error when another thread removes values
        for sem in list(self._connections.values()):
            logger.debug("Sem.release() called")
            sem.release()
        
        if not self._camera is None:
            self._camera.release()
            logger.debug("Releasing camera")
            self._camera = None
        
        logger.debug("Joining threads")
        for thread in self._threads:
            thread.join()
        self._threads.clear()
            
        logger.debug("Joining broadcast thread")
        self._broadcast_thread.join()
        logger.debug("Threads joined")
        
class FrameConsumer(object):
    SOCKET_PATH = os.path.join(str(settings.BASE_DIR), "video_duplication_sock.s")
    
    def __init__(self):
        self._frame_queue = BlockingSingleQueue()
        self._stop = False
        self._recvThread = Thread(target=self._start)
        self._recvThread.start()

    def _recv_message(self, sock):
        """Receives an entire message (without the 4byte length header)
        Returns None if the socket is half closed and no longer receives
        """
        # Read message length (first 4 bytes)
        message_header = self._recv_all(sock, 4)
        if not message_header:
            return None
        
        message_length = unpack('>I', message_header)[0]
        
        # Read the message data based on the length
        message = self._recv_all(sock, message_length)
        return message

    def _recv_all(self, sock, length):
        # Helper function to receive a fixed number of bytes
        data = b''
        while len(data) < length:
            packet = sock.recv(length - len(data))
            if not packet:
                return None
            data += packet
        return data
        
    def __enter__(self):
        return self
        
    def __exit__(self):
        self.release()
    
    def _start(self):
        sock = socket(AF_UNIX, SOCK_STREAM)
        try:
            logger.debug("Connecting to unix socket")
            sock.connect(self.SOCKET_PATH)
            sock.shutdown(1)
            logger.debug("Connection Success")
            errnum = 0
            while not self._stop:
                readable,[],[] = select.select([sock], [],[], 1)
                if len(readable) == 0:
                    errnum += 1
                    logger.debug("No frame gotten from socket")
                    if errnum > 5:
                        break # 5 sec without new frame. Error probably occured
                    else:
                        continue #nothing to do, no frame yet
                errnum = 0
                frame = self._recv_message(sock)
                if frame is None:
                    self._stop = True
                    break
                    
                self._frame_queue.put(frame)
        finally:
            logger.debug("Releasing connection")
            sock.shutdown(2)
            sock.close()
                
    def read(self):
        #returns (True, $Frame) if there is a frame otherwise if timeout returns (False, None)
        try:
            data = self._frame_queue.get()
            if data is None:
                return False, None
            buffer = BytesIO(data)
            return True, np.load(buffer, allow_pickle=False)
        except:
            return False, None
    
    def release(self):
        self._stop = True
        logger.debug("Stopping Frame consumer recv thread")
        self._recvThread.join()
        logger.debug("FrameConsumer recv thread joined")