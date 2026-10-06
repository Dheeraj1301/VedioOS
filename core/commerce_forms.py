from django import forms
from django.utils.html import format_html

from .models import CommercePolicy, CustomService, InfluencerPackage, Plan, Project
from .money import (
    CURRENCY_CHOICES,
    currency_exponent,
    currency_symbol,
    major_to_minor,
    minor_to_major,
)

CURRENCIES = CURRENCY_CHOICES
MAX_PRICE = 999999999999


class MoneyInput(forms.NumberInput):
    def __init__(self, attrs=None):
        super().__init__(attrs)
        self.currency_symbol = ""

    def render(self, name, value, attrs=None, renderer=None):
        input_html = super().render(name, value, attrs, renderer)
        return format_html(
            '<span class="money-input-shell"><span class="money-input-symbol" '
            'data-currency-symbol aria-hidden="true">{}</span>{}</span>',
            self.currency_symbol,
            input_html,
        )


def major_unit_field(label):
    return forms.DecimalField(
        label=label,
        required=False,
        max_digits=18,
        decimal_places=None,
        error_messages={"invalid": "Enter a valid amount."},
        widget=MoneyInput(attrs={"inputmode": "decimal"}),
    )


class MajorUnitPriceFormMixin:
    money_field_labels = {}

    def __init__(self, *args, **kwargs):
        self.values_are_minor = kwargs.pop("values_are_minor", False)
        super().__init__(*args, **kwargs)
        currency = ""
        if self.is_bound:
            currency = self.data.get(self.add_prefix("currency"), "")
        if not currency:
            currency = self.initial.get("currency") or getattr(self.instance, "currency", "")
        symbol = currency_symbol(currency)
        exponent = currency_exponent(currency)
        for field_name, base_label in self.money_field_labels.items():
            field = self.fields[field_name]
            field.label = f"{base_label} ({symbol})" if symbol else base_label
            field.widget.currency_symbol = symbol
            field.widget.attrs.update(
                {
                    "data-money-input": "",
                    "data-base-label": base_label,
                    "step": "1" if exponent == 0 else "0.01",
                    "min": "0",
                }
            )
            if not self.is_bound:
                stored_value = getattr(self.instance, field_name, None)
                if stored_value is not None:
                    self.initial[field_name] = minor_to_major(stored_value, currency)

    def clean(self):
        data = super().clean()
        currency = data.get("currency")
        entered_fields = [
            field_name
            for field_name in self.money_field_labels
            if data.get(field_name) is not None
        ]
        if entered_fields and not currency:
            self.add_error("currency", "Choose a currency before entering a price.")
            for field_name in entered_fields:
                data.pop(field_name, None)
            return data
        for field_name in entered_fields:
            amount = data.get(field_name)
            if amount < 0:
                self.add_error(field_name, "Enter zero or a positive amount.")
                continue
            if self.values_are_minor:
                if amount != amount.to_integral_value():
                    self.add_error(field_name, "Stored prices must use whole minor units.")
                    continue
                amount_minor = int(amount)
                if amount_minor > MAX_PRICE:
                    self.add_error(field_name, "Amount is too large.")
                    continue
                data[field_name] = amount_minor
                continue
            try:
                amount_minor = major_to_minor(amount, currency)
            except ValueError as exc:
                self.add_error(field_name, str(exc))
                continue
            if amount_minor > MAX_PRICE:
                self.add_error(field_name, "Amount is too large.")
                continue
            data[field_name] = amount_minor
        return data


class CatalogForm(MajorUnitPriceFormMixin, forms.ModelForm):
    currency = forms.ChoiceField(choices=CURRENCIES, required=False)
    money_field_labels = {"price_minor": "Price"}

    def clean(self):
        data = super().clean()
        price = data.get("price_minor")
        if data.get("active"):
            if price is None or price <= 0:
                self.add_error("price_minor", "An active item requires a positive price.")
            if not data.get("currency"):
                self.add_error("currency", "Choose a currency before publishing.")
        return data


class PlanForm(CatalogForm):
    price_minor = major_unit_field("Plan price")
    monthly_price_minor = major_unit_field("Monthly price")
    yearly_price_minor = major_unit_field("Yearly price")
    money_field_labels = {
        "price_minor": "Plan price",
        "monthly_price_minor": "Monthly price",
        "yearly_price_minor": "Yearly price",
    }
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
            "monthly_price_minor",
            "yearly_price_minor",
            "currency",
            "features",
            "revision_limit",
            "delivery_hours",
            "duration_limit_seconds",
            "priority",
            "active",
        ]
        help_texts = {
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
        for field in ["monthly_price_minor", "yearly_price_minor"]:
            amount = data.get(field)
            if amount is not None and not 0 < amount <= MAX_PRICE:
                self.add_error(field, "Enter a positive amount within the supported range.")
        if any(data.get(field) is not None for field in ["monthly_price_minor", "yearly_price_minor"]):
            if not data.get("currency"):
                self.add_error("currency", "Choose a currency when configuring period pricing.")
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
    price_minor = major_unit_field("Service price")
    money_field_labels = {"price_minor": "Service price"}

    class Meta:
        model = CustomService
        fields = ["name", "code", "price_minor", "currency", "active"]
        help_texts = {
            "code": "Optional stable mapping used by the live custom estimate. Each mapping can be used once.",
        }


class PackageForm(MajorUnitPriceFormMixin, forms.ModelForm):
    price_minor = major_unit_field("Package price")
    money_field_labels = {"price_minor": "Package price"}
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


class PolicyForm(MajorUnitPriceFormMixin, forms.ModelForm):
    custom_base_minor = major_unit_field("Custom base price")
    money_field_labels = {"custom_base_minor": "Custom base price"}
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
    pricing_period = forms.ChoiceField(
        choices=Plan.PricingPeriod.choices,
        initial=Plan.PricingPeriod.PER_REEL,
        label="Pricing period",
        required=False,
    )
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
        data["pricing_period"] = (
            data.get("pricing_period") or Plan.PricingPeriod.PER_REEL
        )
        if data.get("kind") == "plan":
            if not data.get("plan"):
                self.add_error("plan", "Select an available plan.")
            elif not data["plan"].price_for_period(data.get("pricing_period")):
                self.add_error("plan", "That plan is not configured for the selected pricing period.")
            if data.get("services"):
                self.add_error("services", "Choose custom editing to select individual services.")
        elif data.get("plan"):
            self.add_error("plan", "Clear the plan when selecting custom editing.")
        else:
            data["pricing_period"] = Plan.PricingPeriod.PER_REEL
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
