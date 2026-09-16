from django import forms

from core.forms import RegistrationForm

from .models import EditorAvailability


class EditorRegistrationForm(RegistrationForm):
    phone = forms.CharField(max_length=30)
    experience = forms.CharField(max_length=5000, widget=forms.Textarea(attrs={"rows": 3}))
    tools = forms.CharField(max_length=500, label="Software / tools")
    portfolio = forms.URLField(max_length=500, label="Portfolio URL")
    previous_work = forms.CharField(
        max_length=5000, label="Previous work / sample links", widget=forms.Textarea(attrs={"rows": 3})
    )
    expertise = forms.CharField(max_length=1000, label="Areas of expertise")
    availability = forms.ChoiceField(choices=EditorAvailability.Status.choices)
    other_information = forms.CharField(
        required=False, max_length=5000, widget=forms.Textarea(attrs={"rows": 2})
    )


class AvailabilityForm(forms.ModelForm):
    def __init__(self, *args, **kwargs):
        kwargs.setdefault("label_suffix", "")
        super().__init__(*args, **kwargs)

    class Meta:
        model = EditorAvailability
        fields = ["status"]
