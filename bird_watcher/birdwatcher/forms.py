from constance.forms import ConstanceForm
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
    pass