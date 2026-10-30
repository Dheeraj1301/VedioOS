import hashlib
import json
from copy import deepcopy

from django.core.exceptions import ValidationError

from .models import CommercePolicy, PolicyAcceptance


def policy_snapshot(policy):
    if not policy:
        raise ValidationError("Terms and Conditions are temporarily unavailable. Contact support.")
    return {
        "version": policy.policy_version,
        "registration_terms": policy.registration_terms,
        "terms": policy.terms,
        "delivery_terms": policy.delivery_terms,
        "refund_terms": policy.refund_terms,
        "no_refund_policy": policy.no_refund_policy,
        "tax_terms": policy.tax_terms,
        "support_statement": policy.support_statement,
    }


def current_policy_snapshot():
    policy = CommercePolicy.objects.filter(pk=1).first()
    snapshot = policy_snapshot(policy or CommercePolicy())
    if not policy:
        snapshot["version"] = 0
    return snapshot


def validate_policy_version(snapshot, submitted_version):
    try:
        submitted = int(submitted_version)
    except (TypeError, ValueError) as exc:
        raise ValidationError("Review and accept the current Terms and Conditions.") from exc
    if submitted != snapshot.get("version"):
        raise ValidationError("The Terms and Conditions changed. Review the current version and try again.")
    return submitted


def snapshot_fingerprint(snapshot):
    canonical = json.dumps(snapshot, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def record_registration_acceptance(user, submitted_version):
    snapshot = current_policy_snapshot()
    version = validate_policy_version(snapshot, submitted_version)
    return PolicyAcceptance.objects.create(
        user=user,
        context=PolicyAcceptance.Context.REGISTRATION,
        policy_version=version,
        policy_snapshot=deepcopy(snapshot),
        snapshot_fingerprint=snapshot_fingerprint(snapshot),
    )


def payment_policy_snapshot(order):
    terms = order.terms_snapshot if isinstance(order.terms_snapshot, dict) else {}
    snapshot = terms.get("policy")
    if isinstance(snapshot, dict):
        return deepcopy(snapshot)
    policy = CommercePolicy.objects.filter(pk=1).first()
    current = policy_snapshot(policy or CommercePolicy())
    if not policy:
        current["version"] = 0
    legacy = terms.get("terms") if isinstance(terms.get("terms"), dict) else {}
    for field in ["terms", "delivery_terms", "refund_terms", "tax_terms"]:
        if legacy.get(field):
            current[field] = legacy[field]
    current["legacy_order_terms"] = True
    return current


def record_payment_acceptance(user, order, submitted_version):
    snapshot = payment_policy_snapshot(order)
    version = validate_policy_version(snapshot, submitted_version)
    fingerprint = snapshot_fingerprint(snapshot)
    acceptance, _created = PolicyAcceptance.objects.get_or_create(
        order=order,
        context=PolicyAcceptance.Context.PAYMENT,
        snapshot_fingerprint=fingerprint,
        defaults={
            "user": user,
            "policy_version": version,
            "policy_snapshot": deepcopy(snapshot),
        },
    )
    if acceptance.user_id != user.id or acceptance.policy_version != version:
        raise ValidationError("This order has a different policy acceptance record.")
    return acceptance
