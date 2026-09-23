from django import forms

from .models import CommercePolicy, CustomService, InfluencerPackage, Plan, Project

CURRENCIES = [
    ("", "Choose currency"),
    ("INR", "INR"),
    ("USD", "USD"),
    ("EUR", "EUR"),
    ("GBP", "GBP"),
    ("JPY", "JPY"),
    ("KRW", "KRW"),
]
MAX_PRICE = 999999999999


class CatalogForm(forms.ModelForm):
    currency = forms.ChoiceField(choices=CURRENCIES, required=False)

    def clean(self):
        data = super().clean()
        price = data.get("price_minor")
        if price is not None and price > MAX_PRICE:
            self.add_error("price_minor", "Amount is too large.")
        if data.get("active"):
            if price is None or price <= 0:
                self.add_error("price_minor", "An active item requires a positive price in minor units.")
            if not data.get("currency"):
                self.add_error("currency", "Choose a currency before publishing.")
        return data


class PlanForm(CatalogForm):
    features = forms.CharField(
        widget=forms.Textarea(attrs={"rows": 4}),
        required=False,
        help_text="One feature or included service per line.",
    )

    class Meta:
        model = Plan
        fields = [
            "name",
            "price_minor",
            "currency",
            "features",
            "revision_limit",
            "delivery_hours",
            "duration_limit_seconds",
            "priority",
            "active",
        ]
        help_texts = {
            "price_minor": "Integer minor units: 10000 means INR 100.00; 100 means JPY 100.",
            "active": "Publish only approved prices and terms. This does not enable real payment.",
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance.pk:
            self.initial["features"] = "\n".join(self.instance.features)

    def clean_features(self):
        return [line.strip() for line in self.cleaned_data["features"].splitlines() if line.strip()]

    def clean(self):
        data = super().clean()
        if data.get("active"):
            for field in ["revision_limit", "delivery_hours", "duration_limit_seconds", "priority"]:
                if data.get(field) is None:
                    self.add_error(field, "Required before publishing this plan.")
            for field in ["delivery_hours", "duration_limit_seconds"]:
                if data.get(field) == 0:
                    self.add_error(field, "Must be greater than zero.")
            if not data.get("features"):
                self.add_error("features", "List the included features/services.")
        return data


class ServiceForm(CatalogForm):
    class Meta:
        model = CustomService
        fields = ["name", "code", "price_minor", "currency", "active"]
        help_texts = {
            "code": "Optional stable mapping used by the live custom estimate. Each mapping can be used once.",
            "price_minor": "Integer minor units; never enter decimal prices here.",
        }


class PackageForm(forms.ModelForm):
    currency = forms.ChoiceField(choices=CURRENCIES, required=False)
    services = forms.CharField(
        widget=forms.Textarea(attrs={"rows": 4}),
        required=False,
        help_text="One included service per line.",
    )

    class Meta:
        model = InfluencerPackage
        fields = [
            "name",
            "price_minor",
            "currency",
            "video_allowance",
            "revision_limit",
            "priority",
            "dedicated_editor",
            "services",
        ]
        help_texts = {
            "price_minor": "Draft amount in integer minor units. Publishing and sales remain disabled.",
            "dedicated_editor": "Draft intent only; allocation behavior requires an approved policy.",
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance.pk:
            self.initial["services"] = "\n".join(self.instance.services)

    def clean_services(self):
        return [line.strip() for line in self.cleaned_data["services"].splitlines() if line.strip()]

    def clean(self):
        data = super().clean()
        price = data.get("price_minor")
        if price is not None and not 0 < price <= MAX_PRICE:
            self.add_error("price_minor", "Enter a positive amount within the supported range.")
        if price is not None and not data.get("currency"):
            self.add_error("currency", "Choose a currency when entering a draft price.")
        if data.get("currency") and price is None:
            self.add_error("price_minor", "Enter a draft price or clear the currency.")
        return data


class PolicyForm(forms.ModelForm):
    currency = forms.ChoiceField(choices=CURRENCIES, required=False)

    class Meta:
        model = CommercePolicy
        fields = [
            "currency",
            "custom_base_minor",
            "custom_revision_limit",
            "custom_delivery_hours",
            "custom_duration_limit_seconds",
            "custom_priority",
            "terms",
            "delivery_terms",
            "refund_terms",
            "tax_terms",
            "quotes_enabled",
            "review_rule",
        ]
        widgets = {
            field: forms.Textarea(attrs={"rows": 3})
            for field in ["terms", "delivery_terms", "refund_terms", "tax_terms"]
        }
        help_texts = {
            "quotes_enabled": "Allow clients to request quotes. Real checkout requires a separate provider integration.",
            "tax_terms": "Describe applicable taxes and whether the displayed total includes them.",
            "delivery_terms": "Specify clock start, milestone, working/calendar hours and pause rules.",
            "custom_base_minor": "Leave blank to disable custom quotes. Integer minor units.",
        }

    def clean(self):
        data = super().clean()
        if data.get("quotes_enabled"):
            for field in ["currency", "terms", "delivery_terms", "refund_terms", "tax_terms"]:
                if not data.get(field):
                    self.add_error(field, "Required before enabling quotes.")
        base = data.get("custom_base_minor")
        if base is not None:
            if not 0 < base <= MAX_PRICE:
                self.add_error("custom_base_minor", "Enter a positive amount within the supported range.")
            for field in [
                "custom_revision_limit",
                "custom_delivery_hours",
                "custom_duration_limit_seconds",
                "custom_priority",
            ]:
                if data.get(field) is None:
                    self.add_error(field, "Required when custom pricing is configured.")
            for field in ["custom_delivery_hours", "custom_duration_limit_seconds"]:
                if data.get(field) == 0:
                    self.add_error(field, "Must be greater than zero.")
        return data


class QuoteSelectionForm(forms.Form):
    kind = forms.ChoiceField(choices=[("plan", "Choose a plan"), ("custom", "Customize your video")])
    plan = forms.ModelChoiceField(queryset=Plan.objects.none(), required=False, empty_label="Select a plan")
    services = forms.ModelMultipleChoiceField(
        queryset=CustomService.objects.none(), required=False, widget=forms.CheckboxSelectMultiple
    )
    scope_confirmed = forms.BooleanField(
        label="My brief fits the selected plan/services. Extra or unpriced requests need team review before payment."
    )

    def __init__(self, *args, currency="", **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["plan"].queryset = Plan.objects.filter(active=True, currency=currency).order_by("slot")
        self.fields["services"].queryset = CustomService.objects.filter(
            active=True, currency=currency
        ).order_by("name")
        self.fields["plan"].label_from_instance = lambda item: item.name
        self.fields["services"].label_from_instance = lambda item: item.name

    def clean(self):
        data = super().clean()
        if data.get("kind") == "plan":
            if not data.get("plan"):
                self.add_error("plan", "Select an available plan.")
            if data.get("services"):
                self.add_error("services", "Choose custom editing to select individual services.")
        elif data.get("plan"):
            self.add_error("plan", "Clear the plan when selecting custom editing.")
        return data


class CustomEstimateForm(forms.Form):
    colour_grading = forms.BooleanField(required=False)
    quality_enhancement = forms.BooleanField(required=False)
    reel_duration = forms.ChoiceField(choices=Project.ReelDuration.choices)
    wants_wording = forms.BooleanField(required=False)
    wording_direction = forms.ChoiceField(
        choices=[("", "Choose direction"), *Project.WordingDirection.choices], required=False
    )

    def clean(self):
        data = super().clean()
        if data.get("wants_wording") and not data.get("wording_direction"):
            self.add_error("wording_direction", "Choose how the editor should handle wording.")
        if not data.get("wants_wording"):
            data["wording_direction"] = ""
        return data
