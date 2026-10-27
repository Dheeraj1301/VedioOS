from django.shortcuts import redirect, render

from .sessions import clear_pending_login, pending_login


SIGN_IN_PATHS = {"/login/", "/editor/signin/"}
SESSION_DECISION_PATH = "/login/session/"


def csrf_failure(request, reason=""):
    """Recover expired authentication forms without weakening CSRF checks."""

    if request.path in SIGN_IN_PATHS:
        return redirect(request.path)
    if request.path == SESSION_DECISION_PATH:
        user, _ = pending_login(request)
        if user is None:
            clear_pending_login(request)
            return redirect("login")
        return render(
            request,
            "session_conflict.html",
            {"title": "Account already in use"},
            status=409,
        )
    return render(
        request,
        "error.html",
        {
            "title": "Form expired",
            "error_code": 403,
            "message": "This form is no longer current.",
            "detail": "Reload the page and submit it again. Your previous submission was not processed.",
        },
        status=403,
    )
