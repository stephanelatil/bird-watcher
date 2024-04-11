from django.shortcuts import render
from birdwatcher.models import Video, Tag
from birdwatcher.forms import TagVideoForm
from birdwatcher.utils import kill_and_restart_birdwatcher
from django.views.generic import View, ListView, DetailView
from django.http import HttpRequest
from django.shortcuts import get_object_or_404
from django.urls import reverse
from django.conf import settings
from django.http import HttpResponse, HttpResponseNotModified
from django.views.generic.edit import FormMixin
from json import loads
from fastapi import APIRouter, Header, HTTPException, Request, status
from fastapi.responses import StreamingResponse, FileResponse, Response, RedirectResponse
from multiprocessing import Condition
from threading import Thread
from asgiref.sync import sync_to_async
from anyio import open_file
import os, cv2
from typing import BinaryIO
from starlette._compat import md5_hexdigest
from datetime import datetime
from time import sleep

api_router = APIRouter()

class GlobalContextMixin:
    def get_context_data(self, **kwargs):
        # Call the base implementation first to get the context
        try:
            context = super().get_context_data(**kwargs)
        except:
            context = {}
        context['all_tags'] = list(t.name for t in Tag.objects.all())
        if 'video' in context:
            context['url_edit_video_tags'] = reverse(VideoTagView.url_name, args=(context['video'].pk,))
            context['url_this_video'] = reverse(SingleVideoView.url_name, args=(context['video'].pk,))
        context['url_livestream_page'] = reverse(LiveStreamView.url_name)
        context['url_home_videos_page'] = reverse(VideoListView.url_name)
        return context

#####################
###### Pages

class VideoListView(GlobalContextMixin, ListView):
    model = Video
    paginate = 50
    queryset = Video.objects.order_by('-date_created')
    template_name = 'videos.html'
    url_name = 'video-list'

    def get_context_data(self, **kwargs):
        # Call the base implementation first to get the context
        return super().get_context_data(**kwargs)

class LiveStreamView(GlobalContextMixin, View):
    template_name = 'livestream.html'
    url_name = 'video-livestream'
    # must check if secondary video device is accessible
    # Cf. https://github.com/umlaeute/v4l2loopback to create a loopback livestream device
    
    def get(self, request, *args, **kwargs):
        context = {}
        return render(request, self.template_name, context)
    
class SingleVideoView(GlobalContextMixin, FormMixin, DetailView):
    model = Video
    queryset = Video.objects.all()
    template_name = 'single_video.html'
    form_class = TagVideoForm
    url_name = 'video-detail'

    def get_context_data(self, **kwargs):
        # Call the base implementation first to get the context
        context = super().get_context_data(**kwargs)
        context['video'] = context.pop('object')
        context['tag_list'] = list(context['video'].tags.values_list('name',flat=True))
        context['tag_url'] = reverse('video-tags', args=(context['video'].pk,))
        return context

##################
###### Metadata Views

class VideoTagView(View):   
    queryset = Video.objects.all()
    url_name = 'video-tags'
     
    def post(self, request:HttpRequest, *args, pk=None, **kwargs):
        post = loads(request.body)
        tag = get_object_or_404(Tag.objects.all(), pk=post.get('tag'))
        vid = get_object_or_404(self.queryset, pk=pk)
        vid.tags.add(tag)
        vid.save()
        return HttpResponse(tag.name, status=202)
    
    def delete(self, request:HttpRequest, *args, pk=None, **kwargs):
        vid:Video = get_object_or_404(self.queryset, pk=pk)
        post = loads(request.body)
        tag = vid.tags.filter(name=post.get('tag'))
        if tag.count() == 0:
            return HttpResponseNotModified()
        tag = tag.first()
        vid.tags.remove(tag)
        return HttpResponse('', status=204)

# Create your views here.
class ThumbnailView(View):
    url_name = 'get-thumbnail'
    queryset = Video.objects.all()
    
    def get(self, request, pk=None):
        video = get_object_or_404(self.queryset, pk=pk)
        image = video.thumbnail_file.open('rb')
        return HttpResponse(image, content_type='image/webp')
    
##################
#### Streaming views

class LiveStreamVideo:
    _singelton = None
    _max_unread_frames = 60
    
    def __init__(self):
        """The class is used by the livestream endpoint.
        It creates a singleton that reads from a camera device (must be an unused device)
        and posts the frames read to a shared variable. 
        
        Whenever a client requests a frame it waits to be notified by the camera reader thread.
        Once notified it can send the frame to the client.
        
        To be able to reuse the camera device for motion detection and livestream a device
        loopback like v4l2loopback should be used
        """
        self._cv = Condition()
        self._frames_since_last_query = 0
        self._current_frame = b''
        self._interrupt = [False]
        self._thread = None
        LiveStreamVideo._singelton = self
        
    def _start_thread(self):
        if not self._thread is None:
            return
        self._interrupt[0] = False
        self._thread = Thread(target=LiveStreamVideo._run, args=(self,))
        self._thread.start()
    
    @staticmethod
    def _run(singleton:'LiveStreamVideo'):
        #open camera and read frames
        try:
            sleep(0.1) #wait for frame request
            vid = None
            vid = cv2.VideoCapture(settings.STREAM_VID_DEVICE, cv2.CAP_V4L2)
            try:
                width, height = str(settings.VID_RESOLUTION).split('x',1)
                vid.set(cv2.CAP_PROP_FRAME_WIDTH, int(width))
                vid.set(cv2.CAP_PROP_FRAME_HEIGHT, int(height))
            except: pass
            while not singleton._interrupt[0]:
                flag, frame = vid.read()
                if not flag: continue
                with singleton._cv:
                    singleton._current_frame = LiveStreamVideo.format_frame(cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, 70])[1])
                    singleton._frames_since_last_query += 1
                    singleton._cv.notify_all()
                if singleton.unread_frames >= singleton._max_unread_frames:
                    singleton._kill_thread()
        finally:
            if not vid is None:
                vid.release()
    
    @property
    def unread_frames(self):
        return self._frames_since_last_query
    
    def _kill_thread(self):
        if self._thread is None:
            return
        self._interrupt[0] = True
        self._thread = None

    async def get_frame(self):
        def wait_frame(cv:Condition):
            with cv:
                cv.wait()
        await sync_to_async(wait_frame)(self._cv)
        self._frames_since_last_query = 0
        return self._current_frame
    
    @staticmethod
    def format_frame(frame):
        return b'--frame\r\nContent-Type: image/jpeg\r\n\r\n' + bytearray(frame) + b'\r\n'
    
    @staticmethod
    def getSingleton():
        if LiveStreamVideo._singelton is None:
            LiveStreamVideo._singelton = LiveStreamVideo()
        return LiveStreamVideo._singelton
    
    @staticmethod
    async def livestream_frame_generator():
        stream = LiveStreamVideo.getSingleton()
        stream._start_thread()
        while stream.unread_frames < LiveStreamVideo._max_unread_frames:
            yield await stream.get_frame()
        stream._kill_thread()
        raise StopIteration()

@api_router.get('/stream/live')
async def livestream_video():
    if len(settings.STREAM_VID_DEVICE) == 0:
        return RedirectResponse('/static/no-stream.jpg')
    return StreamingResponse(LiveStreamVideo.livestream_frame_generator(),
                      media_type="multipart/x-mixed-replace;boundary=frame")

def send_bytes_range_requests(file_obj: BinaryIO,
                              start: int, end: int, chunk_size: int = 128*1024):
    """Send a file in chunks using Range Requests specification RFC7233
    `start` and `end` parameters are inclusive due to specification
    """
    with file_obj as f:
        f.seek(start)
        while (pos := f.tell()) <= end:
            read_size = min(chunk_size, end + 1 - pos)
            yield f.read(read_size)


def _get_range_header(range_header: str, file_size: int) -> tuple[int, int]:
    def _invalid_range():
        return HTTPException(
            status.HTTP_416_REQUESTED_RANGE_NOT_SATISFIABLE,
            detail=f"Invalid request range (Range:{range_header!r})")

    try:
        h = range_header.replace("bytes=", "").split("-")
        start = int(h[0]) if h[0] != "" else 0
        end = int(h[1]) if h[1] != "" else file_size - 1
    except ValueError:
        raise _invalid_range()

    if start > end or start < 0 or end > file_size - 1:
        raise _invalid_range()
    return start, end


def range_requests_response(
    request: Request, file_path: str, content_type: str
):
    """Returns StreamingResponse using Range Requests of a given file"""

    file_size = os.stat(file_path).st_size
    range_header = request.headers.get("range")

    """Compose etag from last_modified and file_size"""
    last_modified = datetime.fromtimestamp(os.stat(file_path).st_mtime).strftime("%a, %d %b %Y %H:%M:%S")
    etag_base = str(last_modified) + "-" + str(file_size)
    etag = f'"{md5_hexdigest(etag_base.encode(), usedforsecurity=False)}"'

    """Check if the browser sent etag matches the videos etag"""
    request_if_non_match_etag = request.headers.get("if-none-match")

    """if there is a match return 304 unmodified instead of 206 response without video file"""
    if request_if_non_match_etag == etag:
        headers = {
            "cache-control": "public, max-age=86400, stale-while-revalidate=2592000",
            "etag" : etag,
            "last-modified":str(last_modified),
        }
        status_code = status.HTTP_304_NOT_MODIFIED
        return Response(None, status_code=status_code, headers=headers)

    headers = {
        "etag" : etag,
        "content-type": content_type,
        "accept-ranges": "bytes",
        "content-encoding": "identity",
        "content-length": str(file_size),
        "access-control-expose-headers": (
            "content-type, accept-ranges, content-length, "
            "content-range, content-encoding"
        ),
    }

    if range_header is not None:
        start, end = _get_range_header(range_header, file_size)
        size = end - start + 1
        headers["content-length"] = str(size)
        headers["content-range"] = f"bytes {start}-{end}/{file_size}"
        status_code = status.HTTP_206_PARTIAL_CONTENT
    else:
        start, end = 0, file_size - 1
        status_code = status.HTTP_200_OK        

    return StreamingResponse(
        send_bytes_range_requests(open(file_path, mode="rb"), start, end),
        headers=headers,
        status_code=status_code,
    )

@api_router.get('/stream/{pk}')
async def stream_video_file(request:Request, pk:int):
    try:
        vid = await sync_to_async(get_object_or_404)(Video.objects.all(), pk=pk)
    except:
        return Response(status_code=404)
    
    return range_requests_response(request, vid.video_file, content_type='media/mp4')

@api_router.get("/favicon.ico")
async def get_favicon():
    # Step 6: Return the favicon.ico file using FileResponse
    return FileResponse("static/favicon.ico")

@api_router.put("/birdwatcher/restart")
async def restart_watcher():
    kill_and_restart_birdwatcher(True)