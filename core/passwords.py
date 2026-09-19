import re

from django.core.exceptions import ValidationError
from django.utils.translation import gettext as _


class PasswordCompositionValidator:
    """Require the owner-approved minimum composition without storing password details."""

    rules = (
        (r"[A-Z]", "one uppercase letter"),
        (r"[a-z]", "one lowercase letter"),
        (r"[0-9]", "one number"),
        (r"[^A-Za-z0-9]", "one special character"),
    )

    def validate(self, password, user=None):
        missing = [label for pattern, label in self.rules if not re.search(pattern, password)]
        if missing:
            raise ValidationError(
                _("Password must include %(requirements)s."),
                code="password_missing_composition",
                params={"requirements": ", ".join(missing)},
            )

    def get_help_text(self):
        return _(
            "Use at least 8 characters with an uppercase letter, lowercase letter, number, and special character."
        )
