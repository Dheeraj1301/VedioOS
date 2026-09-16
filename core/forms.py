from django import forms
from django.contrib.auth.forms import AuthenticationForm, UserCreationForm

from .models import Project, User


class RegistrationForm(UserCreationForm):
    def __init__(self, *args, **kwargs):
        kwargs.setdefault("label_suffix", "")
        super().__init__(*args, **kwargs)

    class Meta:
        model = User
        fields = ["name", "email", "password1", "password2"]

    def clean_email(self):
        email = self.cleaned_data["email"].strip().lower()
        if User.objects.filter(email__iexact=email).exists():
            raise forms.ValidationError("An account with this email already exists.")
        return email


class LoginForm(AuthenticationForm):
    def __init__(self, *args, **kwargs):
        kwargs.setdefault("label_suffix", "")
        super().__init__(*args, **kwargs)

    username = forms.EmailField(label="Email", widget=forms.EmailInput(attrs={"autocomplete": "email"}))

    def clean_username(self):
        return self.cleaned_data["username"].strip().lower()


class ProjectForm(forms.ModelForm):
    def __init__(self, *args, **kwargs):
        kwargs.setdefault("label_suffix", "")
        super().__init__(*args, **kwargs)

    class Meta:
        model = Project
        fields = [
            "title",
            "requirements",
            "reference_notes",
            "song_choice",
            "song_information",
            "call_before",
            "call_after",
        ]
        labels = {
            "title": "Project name",
            "requirements": "What would you like us to edit?",
            "reference_notes": "Inspiration and reference notes",
            "song_choice": "Music preference",
            "song_information": "Song name or instructions",
            "call_before": "Talk to an editor before editing",
            "call_after": "Talk to an editor after the draft",
        }
        widgets = {
            name: forms.Textarea(attrs={"rows": 3})
            for name in ["requirements", "reference_notes", "song_information"]
        }
