"""Read-only platform security and AWS posture checks for the scheduled monitor."""

import hashlib
from datetime import date, timedelta
from decimal import Decimal, InvalidOperation

import boto3
from botocore.config import Config
from botocore.exceptions import BotoCoreError, ClientError
from django.conf import settings
from django.db import transaction

from operations.models import AuditLog, Notification

from .models import User


def _aws_config():
    return Config(
        connect_timeout=4,
        read_timeout=8,
        retries={"mode": "standard", "max_attempts": 2},
    )


def _aws_client(service, *, region=None):
    return boto3.client(
        service,
        region_name=region or settings.S3_REGION,
        aws_access_key_id=settings.S3_ACCESS_KEY,
        aws_secret_access_key=settings.S3_SECRET_KEY,
        config=_aws_config(),
    )


def _check_s3():
    client = _aws_client("s3")
    checks = []
    try:
        public_access = client.get_public_access_block(Bucket=settings.S3_BUCKET)[
            "PublicAccessBlockConfiguration"
        ]
        protected = all(public_access.get(key) is True for key in (
            "BlockPublicAcls",
            "IgnorePublicAcls",
            "BlockPublicPolicy",
            "RestrictPublicBuckets",
        ))
        checks.append({"code": "s3_public_access", "level": "ok" if protected else "critical"})
    except client.exceptions.NoSuchPublicAccessBlockConfiguration:
        checks.append({"code": "s3_public_access", "level": "critical"})

    try:
        policy = client.get_bucket_policy_status(Bucket=settings.S3_BUCKET).get("PolicyStatus", {})
    except ClientError as exc:
        if exc.response.get("Error", {}).get("Code") != "NoSuchBucketPolicy":
            raise
        policy = {}
    checks.append({
        "code": "s3_policy",
        "level": "critical" if policy.get("IsPublic") else "ok",
    })

    try:
        encryption = client.get_bucket_encryption(Bucket=settings.S3_BUCKET)
        encrypted = bool(encryption.get("ServerSideEncryptionConfiguration", {}).get("Rules"))
    except ClientError as exc:
        if exc.response.get("Error", {}).get("Code") not in {
            "ServerSideEncryptionConfigurationNotFoundError",
            "NoSuchBucket",
        }:
            raise
        encrypted = False
    checks.append({"code": "s3_encryption", "level": "ok" if encrypted else "critical"})

    versioning = client.get_bucket_versioning(Bucket=settings.S3_BUCKET).get("Status")
    checks.append({"code": "s3_versioning", "level": "ok" if versioning == "Enabled" else "warning"})
    return checks


def _check_guardduty():
    if not settings.AWS_GUARDDUTY_MONITOR_ENABLED:
        return [{"code": "guardduty", "level": "not_configured"}]
    client = _aws_client("guardduty")
    detectors = client.list_detectors(MaxResults=50).get("DetectorIds", [])
    if not detectors:
        return [{"code": "guardduty", "level": "critical", "finding_ids": []}]
    finding_ids = []
    for detector_id in detectors:
        page = client.list_findings(
            DetectorId=detector_id,
            FindingCriteria={"Criterion": {"service.archived": {"Eq": ["false"]}}},
            MaxResults=50,
        )
        ids = page.get("FindingIds", [])
        if not ids:
            continue
        findings = client.get_findings(DetectorId=detector_id, FindingIds=ids).get("Findings", [])
        finding_ids.extend(
            str(finding.get("Id"))
            for finding in findings
            if Decimal(str(finding.get("Severity", 0))) >= Decimal("7") and finding.get("Id")
        )
    return [{
        "code": "guardduty",
        "level": "critical" if finding_ids else "ok",
        "finding_ids": finding_ids,
    }]


def _check_cost():
    threshold = settings.AWS_SECURITY_MONTHLY_BUDGET_USD
    if threshold <= 0:
        return [{"code": "aws_cost", "level": "not_configured"}]
    today = date.today()
    start = today.replace(day=1).isoformat()
    end = (today + timedelta(days=1)).isoformat()
    response = _aws_client("ce", region="us-east-1").get_cost_and_usage(
        TimePeriod={"Start": start, "End": end},
        Granularity="MONTHLY",
        Metrics=["UnblendedCost"],
    )
    try:
        amount = Decimal(response["ResultsByTime"][0]["Total"]["UnblendedCost"]["Amount"])
    except (IndexError, KeyError, InvalidOperation):
        return [{"code": "aws_cost", "level": "warning"}]
    return [{
        "code": "aws_cost",
        "level": "critical" if amount >= threshold else "ok",
        "amount_usd": str(amount.quantize(Decimal("0.01"))),
        "threshold_usd": str(threshold.quantize(Decimal("0.01"))),
    }]


def _notify_admins(checks):
    finding_ids = [
        finding_id
        for check in checks
        for finding_id in check.get("finding_ids", [])
    ]
    tokens = finding_ids or [check["code"] for check in checks if check["level"] == "critical"]
    for token in tokens:
        digest = hashlib.sha256(token.encode()).hexdigest()[:32]
        for admin_id in User.objects.filter(role=User.Role.ADMIN, is_active=True).values_list("id", flat=True):
            Notification.objects.get_or_create(
                event_key=f"security:{digest}:{admin_id}",
                defaults={
                    "recipient_id": admin_id,
                    "message": "Security monitoring needs attention. Review the latest platform audit.",
                },
            )


@transaction.atomic
def run_security_monitor():
    if not settings.SECURITY_MONITOR_ENABLED:
        raise RuntimeError("Security monitoring is disabled.")
    checks = []
    try:
        checks.extend(_check_s3())
        checks.extend(_check_guardduty())
        checks.extend(_check_cost())
    except (BotoCoreError, ClientError, KeyError, ValueError):
        checks.append({"code": "aws_monitor_unavailable", "level": "critical"})
    critical = sum(check["level"] == "critical" for check in checks)
    warning = sum(check["level"] == "warning" for check in checks)
    status = "attention" if critical else "warning" if warning else "healthy"
    detail = {
        "status": status,
        "critical_count": critical,
        "warning_count": warning,
        "checks": [
            {key: value for key, value in check.items() if key != "finding_ids"}
            for check in checks
        ],
    }
    AuditLog.objects.create(
        actor=None,
        action="security.monitor.completed",
        target_id="platform",
        detail=detail,
    )
    if critical:
        _notify_admins(checks)
    return detail
