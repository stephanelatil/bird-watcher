from django.shortcuts import render
from birdwatcher.models import Video, Tag
from django.views.generic import View, ListView, DetailView
from os import path
from django.http import FileResponse, StreamingHttpResponse, HttpResponse

# Create your views here.
class ThumbnailView(View):
    def get(self, request, pk):
        image = Video.objects.get(pk=pk).thumbnail_file.open('rb')
        return HttpResponse(image, content_type='image/webp')
    
class VideoListView(ListView):
    model = Video
    paginate = 50
    queryset = Video.objects.all().order_by('-date_created')
    template_name = 'videos.html'

    def get_context_data(self, **kwargs):
        # Call the base implementation first to get the context
        context = super(VideoListView, self).get_context_data(**kwargs)
        context['videos'] = self.queryset
        return context
    
class VideoStream(View):
    pass