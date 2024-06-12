from adrf.serializers import ModelSerializer
from rest_framework.serializers import ModelSerializer as SyncModelSerializer
from rest_framework.serializers import PrimaryKeyRelatedField, URLField, CharField, DateTimeField, SerializerMethodField
from birdwatcher.models import Video, Tag
from constance.models import Constance
from django.conf import settings
from constance import config

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
        
class ConfigSerializer(SyncModelSerializer):
    defaultValue = SerializerMethodField(method_name='get_default_value')
    helpText = SerializerMethodField(method_name='get_help_text')
    value = SerializerMethodField(method_name='get_value')
    valueType = SerializerMethodField(method_name='get_type')

    class Meta:
        model = Constance
        fields = ('key', 'defaultValue', 'helpText', 'value', 'valueType')

    def get_default_value(self, obj):
        return settings.CONSTANCE_CONFIG.get(obj.key)[0]

    def get_help_text(self, obj):
        return settings.CONSTANCE_CONFIG.get(obj.key)[1]

    def get_value(self, obj):
        return getattr(config, obj.key, None)

    def get_type(self, obj):
        val = getattr(config, obj.key, None)
        if isinstance(val, (float, int)):
            return 'number'
        elif isinstance(val, bool):
            return 'bool'
        return 'string'
        