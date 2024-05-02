from constance.forms import ConstanceForm
from constance.models import Constance
from constance import config
from django.conf import settings
from birdwatcher.models import Tag, Video
from django import forms

class ShowNameModelChoiceField(forms.ModelChoiceField):
    def label_from_instance(self, obj:Tag):
        return obj.name
    
class TagVideoForm(forms.ModelForm):
    class Meta:
        model = Video
        fields = ['tag']
        
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['tag'].widget.attrs['class'] = "form-select"
    
    tag = ShowNameModelChoiceField(Tag.objects.all(), label="")
    
class ConstanceSettingsForm(ConstanceForm):
    def __init__(self, initial, request=None, *args, **kwargs):
        initial = initial or {}
        for key in settings.CONSTANCE_CONFIG.keys():
            initial[key] = getattr(settings.config, key, None)
        super().__init__(initial, request=None, *args, **kwargs)