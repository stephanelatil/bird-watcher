from django.db import models
from django.conf import settings

class Tag(models.Model):
    id = models.BigAutoField()
    name = models.CharField(max_length=32)
    #videos = related_name
    
class Video(models.Model):
    id = models.BigAutoField()
    video_file = models.FilePathField(path=settings.VIDEOS_DIRECTORY)
    thumbnail_file = models.ImageField(upload_to=settings.THUMBNAIL_DIRECTORY)
    num_frames = models.IntegerField()
    framerate = models.FloatField()
    date_created = models.DateTimeField(auto_created=True, auto_now=True, editable=False)
    tags = models.ManyToManyField(Tag, related_name='videos')
