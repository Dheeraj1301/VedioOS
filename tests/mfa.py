import time

from core.models import AccountMFA
from core.totp import STEP_SECONDS, code_at, new_secret


def complete_mfa(browser, user):
    """Answer the administrator or editor code step with a known authenticator secret."""
    mfa, _ = AccountMFA.objects.get_or_create(user=user, defaults={"secret": new_secret()})
    step = max(int(time.time() // STEP_SECONDS), mfa.last_used_step + 1)
    return browser.post("/login/verify/", {"code": code_at(mfa.secret, step)})
