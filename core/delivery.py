"""Review transitions share the allocation lock: policy → order → project.

Storage verification happens before submission; no network calls under locks.
The selected review rule is frozen in the accepted order, never inferred.
"""

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.utils import timezone

from operations.assignments import locked_policy, paid_project
from operations.models import Notification

from .models import DeliveryAcceptance, File, Order, Project, ProjectVersion, RevisionRequest
from .permissions import project_for
from .views import audit


def notify(project, recipient, key, message):
    Notification.objects.get_or_create(
        event_key=key,
        defaults={"project": project, "recipient": recipient, "message": message},
    )


def review_terms(project):
    terms = project.order.terms_snapshot
    limit = terms.get("revision_limit")
    if terms.get("review_rule") != "latest_request_v1" or type(limit) is not int or limit < 0:
        raise ValidationError("Review terms are not configured in this order's agreement. Contact the team.")
    return limit


@transaction.atomic
def transition(user, project_id, action, *, file_id=None, version_id=None, note="", final=False):
    if not user.is_active:
        raise PermissionDenied
    locked_policy()
    project_for(user, project_id)
    Order.objects.select_for_update().get(project_id=project_id)
    project = Project.objects.select_for_update().get(pk=project_id)
    if action == "accept" and project.status == "completed":
        if user.role != "client" or project.client.user_id != user.pk:
            raise PermissionDenied
        accepted = DeliveryAcceptance.objects.filter(project=project, version_id=version_id).first()
        if accepted:
            return accepted
        raise ValidationError("A different version has already been accepted.")
    project = paid_project(project_id)
    limit = review_terms(project)
    assignment = project.assignments.filter(ended_at__isnull=True).select_related("editor__user").first()
    if not assignment:
        raise ValidationError("An assigned editor is required.")
    if action in {"start", "submit"}:
        if user.role != "editor" or assignment.editor.user_id != user.pk or not assignment.editor.approved:
            raise PermissionDenied
    elif action in {"revise", "accept"}:
        if user.role != "client" or project.client.user_id != user.pk:
            raise PermissionDenied
    else:
        raise ValidationError("Unknown review action.")
    latest = project.versions.order_by("-number").first()
    if action == "start":
        states = {"editor_assigned": "editing", "revision_requested": "revision_in_progress"}
        if project.status in {"editing", "revision_in_progress"}:
            return project
        if project.status not in states:
            raise ValidationError("This project cannot start editing in its current state.")
        project.status = states[project.status]
    elif action == "submit":
        file = File.objects.filter(
            pk=file_id,
            project=project,
            uploader=user,
            state="ready",
            category__in=["draft", "final"],
            original__isnull=True,
        ).first()
        if not file or not file.storage_version:
            raise ValidationError("Choose one of your verified draft or final uploads.")
        existing = ProjectVersion.objects.filter(file=file).first()
        if existing:
            if existing.note != note.strip() or existing.is_final != final:
                raise ValidationError("This file has already been submitted with different details.")
            return existing
        if project.status not in {"editing", "revision_in_progress"}:
            raise ValidationError("Start editing or the requested revision before submitting.")
        if str(latest.pk if latest else "") != str(version_id or ""):
            raise ValidationError("The version history changed. Reload the project.")
        if len(note.strip()) > 5000:
            raise ValidationError("Notes must be 5,000 characters or fewer.")
        version = ProjectVersion.objects.create(
            project=project,
            file=file,
            number=latest.number + 1 if latest else 1,
            note=note.strip(),
            is_final=final,
            assignment=assignment,
        )
        project.revisions.filter(status="requested").update(status="addressed")
        project.status = "awaiting_review"
        notify(
            project,
            project.client.user,
            f"version:{version.pk}",
            f"Version {version.number} is ready for your review.",
        )
        audit(
            user,
            "version.submitted",
            version.pk,
            {"project": str(project.pk), "assignment": str(assignment.pk)},
        )
    else:
        if not latest or str(latest.pk) != str(version_id):
            raise ValidationError("Review the latest submitted version. Reload the project.")
        if action == "revise":
            previous = project.revisions.filter(version=latest, requested_by=user).first()
            if previous:
                if previous.instructions != note.strip():
                    raise ValidationError("A revision request already exists for this version.")
                return previous
        if project.status != "awaiting_review":
            raise ValidationError("This version is not currently awaiting review.")
        if action == "revise":
            if not note.strip() or len(note.strip()) > 5000:
                raise ValidationError("Describe the requested changes in 1–5,000 characters.")
            if project.revisions.count() >= limit:
                raise ValidationError(
                    "Your agreed revision allowance is used. Contact the team about additional changes."
                )
            revision = RevisionRequest.objects.create(
                project=project, version=latest, requested_by=user, instructions=note.strip()
            )
            project.status = "revision_requested"
            notify(
                project,
                assignment.editor.user,
                f"revision:{revision.pk}",
                f"Changes requested on version {latest.number}.",
            )
            audit(user, "revision.requested", revision.pk, {"version": str(latest.pk)})
        else:
            if not latest.assignment_id:
                raise ValidationError("Submission attribution is missing. Contact the team.")
            accepted = DeliveryAcceptance.objects.create(
                project=project,
                version=latest,
                accepted_by=user,
                assignment=latest.assignment,
                terms_snapshot=project.order.terms_snapshot,
            )
            latest.accepted_at = timezone.now()
            latest.save(update_fields=["accepted_at", "updated_at"])
            project.status = "completed"
            notify(
                project,
                latest.assignment.editor.user,
                f"acceptance:{accepted.pk}",
                f"Version {latest.number} was accepted. Earnings await configured coin policy.",
            )
            audit(
                user,
                "delivery.accepted",
                accepted.pk,
                {"version": str(latest.pk), "earning_status": "pending_policy"},
            )
    project.save(update_fields=["status", "updated_at"])
    return project
