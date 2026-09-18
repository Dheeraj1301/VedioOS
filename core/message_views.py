from django.contrib import messages
from django.core.exceptions import ValidationError
from django.shortcuts import redirect
from django.views.decorators.http import require_POST

from operations.messages import post_message

from .permissions import role_required


@require_POST
@role_required("client", "editor", "admin")
def message_post(request, project_id):
    try:
        post_message(
            request.user,
            project_id,
            request.POST.get("body"),
            request.POST.get("audience"),
            request.POST.get("request_key"),
        )
    except ValidationError as exc:
        messages.error(request, " ".join(exc.messages))
    else:
        messages.success(request, "Message saved.")
    return redirect(f"{request.user.role}_project", project_id=project_id)
