from django.shortcuts import render
from birdwatcher.models import Video, Tag
from django.views.generic import View, ListView, DetailView
from os import stat, path, SEEK_SET
from django.shortcuts import get_object_or_404
from django.http import FileResponse, StreamingHttpResponse, HttpResponse

# Create your views here.
class ThumbnailView(View):
    queryset = Video.objects.all()
    
    def get(self, request, pk=None):
        video = get_object_or_404(self.queryset, pk=pk)
        image = video.thumbnail_file.open('rb')
        return HttpResponse(image, content_type='image/webp')

class VideoListView(ListView):
    model = Video
    paginate = 50
    queryset = Video.objects.order_by('-date_created')
    template_name = 'videos.html'

    def get_context_data(self, **kwargs):
        # Call the base implementation first to get the context
        context = super(VideoListView, self).get_context_data(**kwargs)
        context['videos'] = self.queryset.all()
        return context
    
class SingleVideoView(DetailView):
    model = Video
    queryset = Video.objects.all()
    template_name = 'single_video.html'

    def get_context_data(self, **kwargs):
        # Call the base implementation first to get the context
        context = super(SingleVideoView, self).get_context_data(**kwargs)
        context['video'] = context.pop('object')
        context['tag_list'] =  list(Tag.objects.all().values_list('name',flat=True))
        return context
    
class StreamVideoView(View):
    queryset = Video.objects.all()
    
    def get(self, request, pk=None):
        def file_iterator(file, chunk_size=8192, offset=0):
            """iterate file chunk by chunk in generator mode"""
            with file:
                file.seek(offset, SEEK_SET)
                while True:
                    data = file.read(chunk_size)
                    if not data:
                        break
                    yield data
        vid = get_object_or_404(self.queryset, pk=pk)
        vid_file = open(vid.video_file, 'rb')
        response = StreamingHttpResponse(file_iterator(vid_file),
                                         #read 25Kb chunks
                                         content_type='video/mp4')
        response['Content-Length'] = stat(vid.video_file).st_size
        response['Accept-Ranges'] = 'bytes'
        return response

class LiveStreamView(View):
    pass
    # must check if secondary video device is accessible
    # Cf. https://github.com/umlaeute/v4l2loopback to create a loopback livestream device
