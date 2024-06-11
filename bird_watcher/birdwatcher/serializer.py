from rest_framework.serializers import ModelSerializer, PrimaryKeyRelatedField, URLField, CharField, DateTimeField
from birdwatcher.models import Video, Tag

class TagSerializer(ModelSerializer):
    videos = PrimaryKeyRelatedField(many=True, read_only=True)
    
    class Meta:
        model = Tag
        fields = ['id', 'name', 'videos']

class TagMinimalSerializer(ModelSerializer):
    class Meta:
        model = Tag
        fields = ['name']
    

class VideoSerializer(ModelSerializer):
    title = CharField()
    date_created = DateTimeField(read_only=True)
    tags = TagSerializer(many=True, read_only=True)
    thumbnail_url = URLField(read_only=True)
    
    class Meta:
        model = Video
        fields = ['id', 'title', 'thumbnail_url', 'date_created', 'tags']