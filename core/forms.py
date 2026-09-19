from django import forms
from django.contrib.auth.forms import AuthenticationForm, UserCreationForm

from .models import Plan, Project, User


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

    username = forms.CharField(
        label="Email or editor ID",
        widget=forms.TextInput(attrs={"autocomplete": "username"}),
    )

    def clean_username(self):
        identity = self.cleaned_data["username"].strip()
        from operations.models import Editor

        editor = Editor.objects.filter(login_id__iexact=identity).select_related("user").first()
        return editor.user.email if editor else identity.lower()


class ProjectForm(forms.ModelForm):
    order_choice = forms.ChoiceField(
        choices=(), widget=forms.RadioSelect, label="Choose an editing option"
    )

    def __init__(self, *args, **kwargs):
        kwargs.setdefault("label_suffix", "")
        super().__init__(*args, **kwargs)
        self.available_plans = Plan.objects.filter(active=True).order_by("slot")
        self.fields["order_choice"].choices = [
            (f"plan:{plan.pk}", plan.name) for plan in self.available_plans
        ] + [("custom", "Customize my edit")]

    def clean(self):
        data = super().clean()
        choice = data.get("order_choice", "")
        if choice.startswith("plan:"):
            plan_id = choice.partition(":")[2]
            plan = self.available_plans.filter(pk=plan_id).first()
            if not plan:
                self.add_error("order_choice", "That plan is no longer available. Choose again.")
            data["selected_plan"] = plan
            if any(
                [
                    data.get("colour_grading"),
                    data.get("quality_enhancement"),
                    data.get("reel_duration"),
                    data.get("wants_wording"),
                    data.get("wording_direction"),
                ]
            ):
                self.add_error(
                    "order_choice", "Choose Customize my edit to add individual requirements."
                )
        elif choice == "custom":
            if not data.get("reel_duration"):
                self.add_error("reel_duration", "Choose the expected reel duration.")
            if data.get("wants_wording") and not data.get("wording_direction"):
                self.add_error("wording_direction", "Choose how the editor should handle wording.")
            if not data.get("wants_wording"):
                data["wording_direction"] = ""
        return data

    class Meta:
        model = Project
        fields = [
            "title",
            "colour_grading",
            "quality_enhancement",
            "reel_duration",
            "wants_wording",
            "wording_direction",
            "requirements",
            "reference_notes",
            "song_choice",
            "song_information",
            "call_before",
            "call_after",
        ]
        labels = {
            "title": "Project name",
            "colour_grading": "Colour grading",
            "quality_enhancement": "Quality enhancement",
            "reel_duration": "Reel duration",
            "wants_wording": "Add wording or on-screen text",
            "wording_direction": "Font direction",
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
