from django import forms
from django.core.exceptions import ValidationError

from core.models import User

from .models import NotificationCampaign

MAX_POSTER_BYTES = 5 * 1024 * 1024
ALLOWED_POSTER_TYPES = {"image/jpeg", "image/png", "image/webp", "image/gif"}


class NotificationCampaignForm(forms.ModelForm):
    poster_upload = forms.FileField(
        required=False,
        label="Poster / cover image",
        help_text="Optional JPG, PNG, WEBP, or GIF. Maximum 5 MB.",
        widget=forms.ClearableFileInput(attrs={"accept": ".jpg,.jpeg,.png,.webp,.gif,image/*"}),
    )
    remove_poster = forms.BooleanField(required=False, label="Remove current poster")

    class Meta:
        model = NotificationCampaign
        fields = ["title", "body", "audience", "target_user"]
        widgets = {"body": forms.Textarea(attrs={"rows": 10})}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["target_user"].queryset = User.objects.filter(is_active=True).order_by("name", "email")
        self.fields["target_user"].required = False
        self.fields["target_user"].help_text = "Required only for a specific-user notification."

    def clean_poster_upload(self):
        upload = self.cleaned_data.get("poster_upload")
        if not upload:
            return upload
        if upload.size > MAX_POSTER_BYTES:
            raise ValidationError("The poster must be 5 MB or smaller.")
        if upload.content_type not in ALLOWED_POSTER_TYPES:
            raise ValidationError("Upload a JPG, PNG, WEBP, or GIF image.")
        signature = upload.read(16)
        upload.seek(0)
        valid = (
            signature.startswith(b"\xff\xd8\xff")
            or signature.startswith(b"\x89PNG\r\n\x1a\n")
            or signature.startswith((b"GIF87a", b"GIF89a"))
            or (signature.startswith(b"RIFF") and signature[8:12] == b"WEBP")
        )
        if not valid:
            raise ValidationError("The uploaded file is not a valid supported image.")
        return upload

    def clean(self):
        cleaned = super().clean()
        if cleaned.get("audience") == NotificationCampaign.Audience.USER:
            if not cleaned.get("target_user"):
                self.add_error("target_user", "Choose the user who should receive this notification.")
        else:
            cleaned["target_user"] = None
        return cleaned

    def save(self, commit=True):
        campaign = super().save(commit=False)
        upload = self.cleaned_data.get("poster_upload")
        if self.cleaned_data.get("remove_poster"):
            campaign.poster = None
            campaign.poster_content_type = ""
            campaign.poster_filename = ""
        if upload:
            campaign.poster = upload.read()
            campaign.poster_content_type = upload.content_type
            campaign.poster_filename = upload.name[:255]
        if commit:
            campaign.save()
        return campaign
