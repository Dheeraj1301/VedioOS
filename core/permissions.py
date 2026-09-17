from functools import wraps

from django.contrib.auth.views import redirect_to_login
from django.core.exceptions import PermissionDenied
from django.db.models import Q
from django.http import JsonResponse
from django.shortcuts import get_object_or_404

from .models import Project


def role_required(*roles):
    def decorate(view):
        @wraps(view)
        def wrapped(request, *args, **kwargs):
            if not request.user.is_authenticated:
                if request.path.startswith("/api/"):
                    return JsonResponse({"error": "Authentication required."}, status=401)
                return redirect_to_login(request.get_full_path())
            if request.user.role not in roles:
                raise PermissionDenied("This area is not available for your account.")
            return view(request, *args, **kwargs)

        return wrapped

    return decorate


def visible_projects(user):
    if user.role == "admin":
        return Project.objects.all()
    if user.role == "client":
        return Project.objects.filter(client__user=user)
    if user.role == "editor":
        return Project.objects.filter(
            assignments__editor__user=user,
            assignments__ended_at__isnull=True,
            assignments__editor__approved=True,
        ).distinct()
    return Project.objects.none()


def project_for(user, project_id):
    return get_object_or_404(visible_projects(user), pk=project_id)


def visible_files(user, project):
    files = project.files.filter(state="ready")
    if user.role == "client":
        files = files.filter(~Q(category__in=["draft", "final"]) | Q(projectversion__isnull=False))
    return files


def can_upload(user, project, category):
    if user.role == "client":
        return (
            project.client.user_id == user.id
            and category in ["source", "image", "audio", "reference", "asset"]
            and project.status not in ["completed", "cancelled"]
        )
    if user.role == "editor":
        return (
            category in ["draft", "final"]
            and project.payment_completed_at is not None
            and project.status not in ["payment_pending", "completed", "cancelled"]
            and visible_projects(user).filter(pk=project.pk).exists()
        )
    return False
