from pathlib import PurePath

from django import forms
from django.core.exceptions import ValidationError

from .landing_content import LANDING_FIELDS

MAX_HERO_VIDEO_BYTES = 100 * 1024 * 1024


class LandingPageForm(forms.Form):
    hero_video = forms.FileField(
        required=False,
        label="Hero video",
        help_text="Optional MP4, maximum 100 MB. It will autoplay muted and loop in the existing frame.",
        widget=forms.ClearableFileInput(attrs={"accept": ".mp4,video/mp4"}),
    )
    remove_hero_video = forms.BooleanField(required=False, label="Remove the current hero video")

    def __init__(self, *args, content=None, **kwargs):
        super().__init__(*args, **kwargs)
        for key, label, default, multiline in LANDING_FIELDS:
            widget = forms.Textarea(attrs={"rows": 3}) if multiline else forms.TextInput()
            self.fields[key] = forms.CharField(
                label=label,
                max_length=2000 if multiline else 240,
                initial=(content or {}).get(key, default),
                widget=widget,
            )

    def clean_hero_video(self):
        upload = self.cleaned_data.get("hero_video")
        if not upload:
            return upload
        if upload.size > MAX_HERO_VIDEO_BYTES:
            raise ValidationError("The hero video must be 100 MB or smaller.")
        if upload.content_type != "video/mp4" or PurePath(upload.name).suffix.lower() != ".mp4":
            raise ValidationError("Upload an MP4 video.")
        signature = upload.read(32)
        upload.seek(0)
        if len(signature) < 12 or signature[4:8] != b"ftyp":
            raise ValidationError("The uploaded file is not a valid MP4 video.")
        return upload

    def content(self):
        return {key: self.cleaned_data[key] for key, *_rest in LANDING_FIELDS}


class FAQItemForm(forms.Form):
    id = forms.CharField(required=False, widget=forms.HiddenInput())
    title = forms.CharField(label="Title", max_length=240)
    content = forms.CharField(
        label="Content / answer", max_length=2000, widget=forms.Textarea(attrs={"rows": 3})
    )
    published = forms.BooleanField(required=False, initial=True, label="Published")


FAQFormSet = forms.formset_factory(
    FAQItemForm, extra=0, can_delete=True, can_order=True, max_num=50, validate_max=True
)
