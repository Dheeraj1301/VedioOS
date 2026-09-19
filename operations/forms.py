from django import forms

from .models import EditorAvailability


class AvailabilityForm(forms.ModelForm):
    def __init__(self, *args, **kwargs):
        kwargs.setdefault("label_suffix", "")
        super().__init__(*args, **kwargs)

    class Meta:
        model = EditorAvailability
        fields = ["status"]
