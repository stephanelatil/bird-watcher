from django.shortcuts import render
from birdwatcher.models import Video, Tag
from birdwatcher.forms import TagVideoForm
from django.views.generic import View, ListView, DetailView
from django.http import HttpRequest
from os import stat, path, SEEK_SET
from django.shortcuts import get_object_or_404
from django.urls import reverse
from django.conf import settings
from django.http import HttpResponse, HttpResponseNotModified
from django.views.generic.edit import FormMixin
from json import loads
from fastapi import APIRouter
from fastapi.responses import StreamingResponse, FileResponse, Response
from multiprocessing import Condition
from threading import Thread

api_router = APIRouter()

class GlobalContextMixin:
    def get_context_data(self, **kwargs):
        # Call the base implementation first to get the context
        try:
            context = super().get_context_data(**kwargs)
        except:
            context = {}
        context['all_tags'] = list(Tag.objects.all().values_list('name',flat=True))
        if 'video' in context:
            context['url_edit_video_tags'] = reverse(VideoTagView.url_name, args=(context['video'].pk,))
            context['url_this_video'] = reverse(SingleVideoView.url_name, args=(context['video'].pk,))
        context['url_livestream_page'] = reverse(LiveStreamView.url_name)
        context['url_home_videos_page'] = reverse(VideoListView.url_name)
        return context

#####################
###### Pages

class VideoListView(ListView, GlobalContextMixin):
    model = Video
    paginate = 50
    queryset = Video.objects.order_by('-date_created')
    template_name = 'videos.html'
    url_name = 'video-list'

    def get_context_data(self, **kwargs):
        # Call the base implementation first to get the context
        context = super(VideoListView, self).get_context_data(**kwargs)
        context['videos'] = self.queryset.all()
        return context

class LiveStreamView(View, GlobalContextMixin):
    template_name = 'livestream.html'
    url_name = 'video-livestream'
    # must check if secondary video device is accessible
    # Cf. https://github.com/umlaeute/v4l2loopback to create a loopback livestream device
    
    def get(self, request, *args, **kwargs):
        context = {}
        return render(request, self.template_name, context)
    
class SingleVideoView(DetailView, FormMixin, GlobalContextMixin):
    model = Video
    queryset = Video.objects.all()
    template_name = 'single_video.html'
    form_class = TagVideoForm
    url_name = 'video-detail'

    def get_context_data(self, **kwargs):
        # Call the base implementation first to get the context
        context = super(SingleVideoView, self).get_context_data(**kwargs)
        context['video'] = context.pop('object')
        context['tag_list'] = list(context['video'].tags.values_list('name',flat=True))
        context['all_tags'] = list(Tag.objects.all().values_list('name',flat=True))
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
        LiveStreamVideo._singelton = self
        self._cv = Condition()
        self._frames_since_last_query = 0
        self._current_frame = b''
        self._interrupt = [False]
        self._thread = None
        
    def _start_thread(self):
        if not self._thread is None:
            return
        self._interrupt[0] = False
        self._thread = Thread(target=LiveStreamVideo._run, args=(self,))
        self._thread.start()
    
    @staticmethod
    def _run(singleton:'LiveStreamVideo'):
        #open camera and read frames
        singleton._cv.acquire()
        while not singleton._interrupt[0]:
            pass
        singleton._cv.release()
    
    @property
    def unread_frames(self):
        return self._frames_since_last_query
    
    def _kill_thread(self):
        if self._thread is None:
            return
        self._interrupt[0] = True
        self._thread.join()
        self._thread = None
                

    def get_frame(self):
        self._cv.wait()
        self._frames_since_last_query = 0
        #need format_frame(cv2.imencode(".jpg", output_frame))
        return self._current_frame
    
    @staticmethod
    def format_frame(frame):
        return (b'--frame\r\n' b'Content-Type: image/jpeg\r\n\r\n' + bytearray(frame) + b'\r\n')
    
    @staticmethod
    def getSingleton():
        if LiveStreamVideo._singelton is None:
            LiveStreamVideo._singelton = LiveStreamVideo()
        return LiveStreamVideo._singelton
    
    @staticmethod
    def livestream_frame_generator():
        stream = LiveStreamVideo.getSingleton()
        while stream.unread_frames < LiveStreamVideo._max_unread_frames:
            yield stream.get_frame()
        raise StopIteration()

@api_router.get('/stream/{pk}')
def stream_video_file(pk=None):
    def iter_file(file_path):
        CHUNK_SIZE = 1024*128 #128Kib
        with open(file_path, 'rb') as vid_file:
            while content := vid_file.read(CHUNK_SIZE):
                yield content
    
    try:
        vid = get_object_or_404(Video.objects.all(), pk=pk)
    except:
        return Response(status_code=404)
    return StreamingResponse(iter_file(vid.video_file))
        

@api_router.get('/stream/live')
async def livestream_video():
    if len(settings.STREAM_VID_DEVICE) == 0:
        return FileResponse(settings.STATICFILES_DIRS[0]/'no-stream.jpg')
    return StreamingResponse(LiveStreamVideo.livestream_frame_generator(),
                      media_type="multipart/x-mixed-replace;boundary=frame")
    
@api_router.get("/favicon.ico")
async def get_favicon():
    # Step 6: Return the favicon.ico file using FileResponse
    return FileResponse("static/favicon.ico")
