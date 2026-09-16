from django import forms

from .models import AssignmentPolicy, Editor, EditorAvailability, EditorProficiency


class AssignmentPolicyForm(forms.ModelForm):
    class Meta:
        model = AssignmentPolicy
        fields = [
            "manual_enabled",
            "automatic_enabled",
            "matching",
            "capacity_scope",
            "manual_pointer",
            "busy_strategy",
            "roster_order",
            "queue_order",
        ]

    def clean(self):
        data = super().clean()
        required = []
        if data.get("manual_enabled") or data.get("automatic_enabled"):
            required += ["matching", "capacity_scope", "manual_pointer", "roster_order"]
        if data.get("automatic_enabled"):
            required += ["busy_strategy", "queue_order"]
        for field in required:
            if not data.get(field):
                self.add_error(field, "Choose this policy before enabling assignment.")
        return data


class EditorOperationsForm(forms.Form):
    approved = forms.BooleanField(required=False)
    proficiency = forms.ModelChoiceField(queryset=EditorProficiency.objects.all(), required=False)
    workload_capacity = forms.IntegerField(
        min_value=1,
        max_value=1000,
        required=False,
        help_text="Maximum concurrent open projects. Leave blank to prevent new assignments.",
    )
    status = forms.ChoiceField(choices=EditorAvailability.Status.choices, label="Availability")
    reason = forms.CharField(max_length=1000, widget=forms.Textarea(attrs={"rows": 2}))

    def clean(self):
        data = super().clean()
        if data.get("approved") and not data.get("proficiency"):
            self.add_error("proficiency", "Approval requires an admin-selected proficiency.")
        return data


class ComplexityForm(forms.Form):
    proficiency = forms.ModelChoiceField(queryset=EditorProficiency.objects.all())
    reason = forms.CharField(
        max_length=2000,
        widget=forms.Textarea(attrs={"rows": 3}),
        label="Internal assessment / override reason",
    )
    expected_revision = forms.IntegerField(min_value=0, widget=forms.HiddenInput)


class ManualAssignmentForm(forms.Form):
    editor = forms.ModelChoiceField(queryset=Editor.objects.none())
    reason = forms.CharField(max_length=1000, widget=forms.Textarea(attrs={"rows": 2}))
    expected_assignment = forms.UUIDField(required=False, widget=forms.HiddenInput)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["editor"].queryset = Editor.objects.filter(
            approved=True, user__is_active=True
        ).select_related("user", "proficiency")
        self.fields["editor"].label_from_instance = lambda item: f"{item.user.name} — {item.proficiency_id}"
