from birdwatcher.models import Tag, Video
from django import forms

class ShowNameModelChoiceField(forms.ModelChoiceField):
    def label_from_instance(self, obj:Tag):
        return obj.name
    
class TagVideoForm(forms.ModelForm):
    class Meta:
        model = Video
        fields = ['tag']
    
    tag = ShowNameModelChoiceField(Tag.objects.all(), label="")