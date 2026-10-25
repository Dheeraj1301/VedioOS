from django.shortcuts import redirect, render

LOGIN_PATHS = {"/login/", "/editor/signin/"}


def csrf_failure(request, reason=""):
    """Recover stale sign-in forms without weakening CSRF validation."""

    if request.path in LOGIN_PATHS:
        return redirect(f"{request.path}?form=expired")
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
