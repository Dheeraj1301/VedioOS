from django import forms
from django.conf import settings
from django.contrib.auth.forms import AuthenticationForm, SetPasswordForm, UserCreationForm
from django.core.exceptions import ValidationError

from .models import Plan, Project, User
from .supabase_auth import (
    SupabaseAuthRejected,
    SupabaseAuthUnavailable,
    authenticate_supabase_user,
)


class RegistrationForm(UserCreationForm):
    def __init__(self, *args, **kwargs):
        kwargs.setdefault("label_suffix", "")
        super().__init__(*args, **kwargs)
        self.fields["password1"].help_text = (
            "Use at least 8 characters with an uppercase letter, lowercase letter, "
            "number, and special character."
        )

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
        # Keep browser password managers from repeatedly replacing credentials
        # that the user is trying to enter manually.
        autofill_opt_out = {
            "autocomplete": "off",
            "data-lpignore": "true",
            "data-1p-ignore": "true",
        }
        self.fields["username"].widget.attrs.update(autofill_opt_out)
        self.fields["password"].widget.attrs.update(autofill_opt_out)

    username = forms.CharField(
        label="Email or editor ID",
        widget=forms.TextInput(),
    )

    def clean_username(self):
        identity = self.cleaned_data["username"].strip()
        from operations.models import Editor

        editor = Editor.objects.filter(login_id__iexact=identity).select_related("user").first()
        return editor.user.email if editor else identity.lower()

    def clean(self):
        email = self.cleaned_data.get("username")
        password = self.cleaned_data.get("password")
        existing = User.objects.filter(email__iexact=email).first() if email else None
        use_supabase = bool(
            settings.SUPABASE_AUTH_PASSWORD_LOGIN_ENABLED
            and email
            and "@" in email
            and password
            and (
                existing is None
                or existing.role == User.Role.CLIENT
                or existing.supabase_auth_user_id
            )
        )
        if use_supabase:
            try:
                self.user_cache = authenticate_supabase_user(email, password)
            except SupabaseAuthRejected as exc:
                if exc.reason == "email_not_confirmed":
                    message = (
                        "This Supabase user exists, but its email is not confirmed. "
                        "Confirm the user in Supabase Authentication and try again."
                    )
                else:
                    message = "Supabase has temporarily limited sign-in attempts. Try again shortly."
                raise ValidationError(message, code=exc.reason) from exc
            except SupabaseAuthUnavailable as exc:
                raise ValidationError(
                    "Sign-in is temporarily unavailable. Please try again shortly.",
                    code="supabase_auth_unavailable",
                ) from exc
            if self.user_cache is None:
                raise self.get_invalid_login_error()
            self.confirm_login_allowed(self.user_cache)
            return self.cleaned_data

        try:
            return super().clean()
        except ValidationError as local_error:
            if not email or "@" not in email or not password:
                raise local_error
            try:
                self.user_cache = authenticate_supabase_user(email, password)
            except SupabaseAuthRejected as exc:
                if exc.reason == "email_not_confirmed":
                    message = (
                        "This Supabase user exists, but its email is not confirmed. "
                        "Confirm the user in Supabase Authentication and try again."
                    )
                else:
                    message = "Supabase has temporarily limited sign-in attempts. Try again shortly."
                raise ValidationError(message, code=exc.reason) from exc
            except SupabaseAuthUnavailable as exc:
                raise ValidationError(
                    "Sign-in is temporarily unavailable. Please try again shortly.",
                    code="supabase_auth_unavailable",
                ) from exc
            if self.user_cache is None:
                raise local_error
            self.confirm_login_allowed(self.user_cache)
            return self.cleaned_data


class PasswordResetSetForm(SetPasswordForm):
    def __init__(self, *args, **kwargs):
        kwargs.setdefault("label_suffix", "")
        super().__init__(*args, **kwargs)
        self.fields["new_password1"].label = "New password"
        self.fields["new_password2"].label = "Confirm new password"
        self.fields["new_password1"].help_text = (
            "Use at least 8 characters with an uppercase letter, lowercase letter, "
            "number, and special character."
        )


class ProjectForm(forms.ModelForm):
    order_choice = forms.ChoiceField(
        choices=(), widget=forms.RadioSelect, label="Choose an editing option"
    )
    pricing_period = forms.ChoiceField(
        choices=Plan.PricingPeriod.choices,
        initial=Plan.PricingPeriod.PER_REEL,
        label="Pricing period",
        required=False,
    )
    standard_song_preference = forms.CharField(
        required=False,
        max_length=500,
        label="Song preference / name",
        widget=forms.TextInput(attrs={"placeholder": "e.g. Shape of You by Ed Sheeran"}),
    )

    def __init__(self, *args, **kwargs):
        kwargs.setdefault("label_suffix", "")
        super().__init__(*args, **kwargs)
        # Fixed plans hide the custom brief panel, so they must not depend on
        # a hidden project-name input.
        self.fields["title"].required = False
        self.fields["song_choice"].required = False
        # The rendered select always submits a choice. Accept older clients
        # that do not know this additive field and apply the model default.
        self.fields["revisions_needed"].required = False
        self.available_plans = Plan.objects.filter(active=True).order_by("slot")
        self.fields["order_choice"].choices = [
            (f"plan:{plan.pk}", plan.name) for plan in self.available_plans
        ] + [("custom", "Customize my edit")]
        if self.instance.pk and hasattr(self.instance, "order"):
            order = self.instance.order
            self.initial["order_choice"] = f"plan:{order.plan_id}" if order.plan_id else "custom"
            self.initial["pricing_period"] = order.pricing_period
            if order.kind == "plan":
                self.initial["standard_song_preference"] = self.instance.song_information

    def clean(self):
        data = super().clean()
        choice = data.get("order_choice", "")
        pricing_period = data.get("pricing_period") or Plan.PricingPeriod.PER_REEL
        if pricing_period != Plan.PricingPeriod.PER_REEL:
            self.add_error("pricing_period", "Monthly and yearly pricing are upcoming.")
            pricing_period = Plan.PricingPeriod.PER_REEL
        data["pricing_period"] = pricing_period
        if choice.startswith("plan:"):
            plan_id = choice.partition(":")[2]
            plan = self.available_plans.filter(pk=plan_id).first()
            if not plan:
                self.add_error("order_choice", "That plan is no longer available. Choose again.")
            data["selected_plan"] = plan
            if plan and not data.get("title", "").strip():
                data["title"] = plan.name
            if plan and not plan.price_for_period(pricing_period):
                self.add_error(
                    "order_choice",
                    f"{dict(Plan.PricingPeriod.choices)[pricing_period]} pricing is coming soon for this plan.",
                )
            if any(
                [
                    data.get("colour_grading"),
                    data.get("quality_enhancement"),
                    data.get("overlays"),
                    data.get("beat_sync"),
                    data.get("reel_duration"),
                    data.get("wants_wording"),
                    data.get("wording_direction"),
                ]
            ):
                self.add_error(
                    "order_choice", "Choose Customize my edit to add individual requirements."
                )
        elif choice == "custom":
            data["pricing_period"] = Plan.PricingPeriod.PER_REEL
            if not data.get("title", "").strip():
                self.add_error("title", "Enter a project name.")
            if not data.get("reel_duration"):
                self.add_error("reel_duration", "Choose the expected reel duration.")
            if data.get("wants_wording") and not data.get("wording_direction"):
                self.add_error("wording_direction", "Choose how the editor should handle wording.")
            if not data.get("wants_wording"):
                data["wording_direction"] = ""
        if data.get("wants_wording") and data.get("wording_direction") == "own_font":
            if not data.get("font_name", "").strip():
                self.add_error("font_name", "Enter the font style or name.")
        else:
            data["font_name"] = ""
        if not data.get("song_choice"):
            data["song_choice"] = "suggest"
        if not data.get("revisions_needed"):
            data["revisions_needed"] = (
                self.initial.get("revisions_needed") or Project.RevisionsNeeded.ONE_TO_TWO
            )
        if data.get("song_choice") == "suggest":
            data["song_information"] = ""
        return data

    class Meta:
        model = Project
        fields = [
            "title",
            "colour_grading",
            "quality_enhancement",
            "overlays",
            "beat_sync",
            "reel_duration",
            "wants_wording",
            "wording_direction",
            "font_name",
            "requirements",
            "inspiration_link",
            "reference_notes",
            "song_choice",
            "revisions_needed",
            "song_information",
        ]
        labels = {
            "title": "Project name",
            "colour_grading": "Colour grading",
            "quality_enhancement": "Quality enhancement",
            "overlays": "Add overlays",
            "beat_sync": "Beat sync",
            "reel_duration": "Reel duration",
            "wants_wording": "Add wording or on-screen text",
            "wording_direction": "Font selection",
            "font_name": "Font style or name",
            "requirements": "Describe the edit",
            "inspiration_link": "Inspiration link",
            "reference_notes": "Other Instructions",
            "song_choice": "Music preference",
            "revisions_needed": "Revisions needed",
            "song_information": "Song Name or Link",
        }
        widgets = {
            name: forms.Textarea(attrs={"rows": 3})
            for name in ["requirements", "reference_notes", "song_information"]
        }
        widgets["inspiration_link"] = forms.URLInput(
            attrs={"placeholder": "https://youtube.com/…"}
        )
