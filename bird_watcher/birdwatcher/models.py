from django.db import models
from django.conf import settings
from django.urls import reverse

class Tag(models.Model):
    name = models.CharField(max_length=32)
    #videos = related_name
    
    def save(self, *args, **kwargs):
        self.name = self.name.title()
        super().save(*args ,**kwargs)
    
class Video(models.Model):
    video_file = models.FilePathField(path=settings.VIDEOS_DIRECTORY)
    thumbnail_file = models.ImageField(upload_to=settings.THUMBNAIL_DIRECTORY)
    num_frames = models.IntegerField()
    framerate = models.FloatField()
    date_created = models.DateTimeField(auto_created=True, auto_now=True, editable=False)
    tags = models.ManyToManyField(Tag, related_name='videos', default=[])
    
    @property
    def thumbnail_url(self):
        return reverse('get-thumbnail', kwargs={'pk':self.pk})