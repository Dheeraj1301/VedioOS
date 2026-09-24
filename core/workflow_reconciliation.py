"""Read-only consistency checks across payment, project, file and delivery records."""

from django.db.models import F, Q

from operations.models import EditorAssignment

from .models import DeliveryAcceptance, File, Order, Payment, Project, ProjectVersion, RevisionRequest


def workflow_findings():
    return {
        "confirmed_order_activation": Order.objects.filter(payment_status="confirmed")
        .filter(Q(project__payment_completed_at__isnull=True) | Q(project__status=Project.Status.PENDING))
        .count(),
        "confirmed_order_terms": Order.objects.filter(payment_status="confirmed")
        .filter(Q(total_minor__isnull=True) | Q(currency="") | Q(terms_snapshot={}))
        .count(),
        "confirmed_payment_metadata": Payment.objects.filter(status="confirmed")
        .filter(
            Q(confirmed_at__isnull=True)
            | ~Q(amount_minor=F("order__total_minor"))
            | ~Q(currency=F("order__currency"))
        )
        .count(),
        "active_assignment_payment": EditorAssignment.objects.filter(ended_at__isnull=True)
        .filter(
            Q(project__payment_completed_at__isnull=True)
            | ~Q(project__order__payment_status="confirmed")
        )
        .count(),
        "ready_file_metadata": File.objects.filter(state="ready")
        .filter(Q(storage_version="") | Q(completed_at__isnull=True))
        .count(),
        "version_file_link": ProjectVersion.objects.filter(
            ~Q(project_id=F("file__project_id")) | ~Q(file__state="ready")
        ).count(),
        "revision_version_link": RevisionRequest.objects.filter(
            ~Q(project_id=F("version__project_id"))
            | ~Q(requested_by_id=F("project__client__user_id"))
        ).count(),
        "acceptance_link": DeliveryAcceptance.objects.filter(
            ~Q(project_id=F("version__project_id"))
            | ~Q(accepted_by_id=F("project__client__user_id"))
            | Q(version__assignment__isnull=True)
            | ~Q(assignment_id=F("version__assignment_id"))
            | ~Q(project__status=Project.Status.COMPLETED)
            | Q(version__accepted_at__isnull=True)
        ).count(),
        "completed_without_acceptance": Project.objects.filter(
            status=Project.Status.COMPLETED, acceptance__isnull=True
        ).count(),
    }
