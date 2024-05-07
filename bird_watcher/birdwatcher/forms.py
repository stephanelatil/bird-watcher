from constance.forms import ConstanceForm
from constance import config
from django.conf import settings
from django.forms.fields import Field
from django.forms.widgets import Textarea, TextInput
from birdwatcher.models import Tag, Video
from django import forms

class ShowNameModelChoiceField(forms.ModelChoiceField):
    def __init__(self, queryset, *, id=None, **kwargs) -> None:
        super().__init__(queryset, **kwargs)
        if not id is None:
            self.widget.attrs['id'] = id
        
    def label_from_instance(self, obj:Tag):
        return obj.name
    
class TagVideoForm(forms.ModelForm):
    class Meta:
        model = Video
        fields = ['tag']
        
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['tag'].widget.attrs['class'] = "form-select"
    
    tag = ShowNameModelChoiceField(Tag.objects.all(), id="add-tag-select", label="")
    
class ConstanceSettingsForm(ConstanceForm):
    def __init__(self, initial, request=None, *args, **kwargs):
        initial = initial or {}
        for key in settings.CONSTANCE_CONFIG.keys():
            initial[key] = getattr(config, key, None)
        super().__init__(initial, request=None, *args, **kwargs)
        for field in self.fields.values():
            if isinstance(field, Field) and isinstance(field.widget, Textarea):
                field.widget = TextInput(field.widget.attrs)
