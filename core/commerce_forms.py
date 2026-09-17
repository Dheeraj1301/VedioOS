from django import forms

from .models import CommercePolicy, CustomService, Plan

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
        fields = ["name", "price_minor", "currency", "active"]
        help_texts = {"price_minor": "Integer minor units; never enter decimal prices here."}


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
