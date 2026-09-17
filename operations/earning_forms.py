from django import forms
from django.core.exceptions import ValidationError

from .earnings import MAX_COINS, check_policy
from .models import EarningPolicy


class EarningPolicyForm(forms.ModelForm):
    class Meta:
        model = EarningPolicy
        fields = [
            "enabled",
            "rule",
            "plan_1_coins",
            "plan_2_coins",
            "plan_3_coins",
            "custom_coins",
            "release_mode",
            "redemptions_enabled",
            "redemption_minimum",
        ]
        help_texts = {
            "enabled": "Applies to new quotes only. Existing agreements keep their saved rule.",
            "redemptions_enabled": "Development sandbox only until an approved payout provider and policy exist.",
            "redemption_minimum": "Whole coins; no monetary exchange value is defined.",
        }

    def clean(self):
        values = super().clean()
        candidate = EarningPolicy(**{k: values.get(k) for k in self.Meta.fields})
        try:
            check_policy(candidate)
        except ValidationError as exc:
            self.add_error(None, exc)
        for name in ["plan_1_coins", "plan_2_coins", "plan_3_coins", "custom_coins", "redemption_minimum"]:
            amount = values.get(name)
            if amount is not None and amount > MAX_COINS:
                self.add_error(name, "Amount is too large.")
        return values


class RedemptionForm(forms.Form):
    amount = forms.IntegerField(min_value=1, max_value=MAX_COINS, label="Whole coins to redeem")
