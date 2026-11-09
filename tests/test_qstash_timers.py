import base64
import hashlib
import hmac
import json
import time
from datetime import timedelta
from unittest.mock import patch

from django.core import mail
from django.test import TestCase, override_settings
from django.utils import timezone

from core.models import Project
from core.project_storage import expire_unpaid_projects
from operations.assignments import classify, manual_assign
from operations.models import AuditLog
from tests.assignment_fixtures import create_people, enable_test_policy, paid_project

KEY = "sig_synthetic_current"
QSTASH = dict(QSTASH_TOKEN="synthetic-token", QSTASH_URL="https://qstash.example", QSTASH_CURRENT_SIGNING_KEY=KEY,
              QSTASH_NEXT_SIGNING_KEY="sig_synthetic_next", PUBLIC_SITE_URL="https://brio.example")


def b64(data):
    return base64.urlsafe_b64encode(data).decode().rstrip("=")


def signature(body=b"{}", key=KEY, sub="https://brio.example/internal/timer/", exp_offset=300):
    now = int(time.time())
    header = b64(json.dumps({"alg": "HS256", "typ": "JWT"}).encode())
    claims = {"iss": "Upstash", "sub": sub, "nbf": now, "exp": now + exp_offset,
              "body": b64(hashlib.sha256(body).digest())}
    payload = b64(json.dumps(claims).encode())
    sig = b64(hmac.new(key.encode(), f"{header}.{payload}".encode(), hashlib.sha256).digest())
    return f"{header}.{payload}.{sig}"


@override_settings(**QSTASH, DEBUG=True)
class QStashAlarmTests(TestCase):
    def setUp(self):
        self.admin, self.client_profile, self.editors = create_people()
        enable_test_policy()

    @patch("core.qstash.requests.post")
    def test_a_new_project_sets_alarms_for_the_reminder_and_the_expiry(self, post):
        with self.captureOnCommitCallbacks(execute=True):
            project = Project.objects.create(client=self.client_profile, title="Unpaid draft")
        times = sorted(int(c.kwargs["headers"]["Upstash-Not-Before"]) for c in post.call_args_list)
        created = int(project.created_at.timestamp())
        self.assertEqual(times, [created + 30 * 3600 + 60, created + 36 * 3600 + 300])
        self.assertTrue(all(c.args[0] == "https://qstash.example/v2/publish/https://brio.example/internal/timer/"
                            for c in post.call_args_list))

    @patch("core.qstash.requests.post")
    def test_an_assignment_sets_alarms_at_12_and_6_hours_left(self, post):
        project = paid_project(self.client_profile)
        classify(self.admin, project.id, "beginner", "Synthetic assessment", 0)
        post.reset_mock()
        with self.captureOnCommitCallbacks(execute=True):
            assignment = manual_assign(self.admin, project.id, self.editors[0].pk, "")
        times = sorted(int(c.kwargs["headers"]["Upstash-Not-Before"]) for c in post.call_args_list)
        start = int(assignment.created_at.timestamp())
        self.assertEqual(times, [start + 12 * 3600 + 60, start + 18 * 3600 + 60])

    def test_timer_endpoint_accepts_only_genuine_qstash_calls(self):
        url = "/internal/timer/"
        self.assertEqual(self.client.post(url, b"{}", content_type="application/json").status_code, 401)
        for bad in (signature(key="wrong"), signature(sub="https://evil.example/internal/timer/"),
                    signature(body=b"other"), signature(exp_offset=-600)):
            response = self.client.post(url, b"{}", content_type="application/json", HTTP_UPSTASH_SIGNATURE=bad)
            self.assertEqual(response.status_code, 401)
        ok = self.client.post(url, b"{}", content_type="application/json", HTTP_UPSTASH_SIGNATURE=signature())
        self.assertEqual(ok.status_code, 200)
        nxt = self.client.post(url, b"{}", content_type="application/json",
                               HTTP_UPSTASH_SIGNATURE=signature(key="sig_synthetic_next"))
        self.assertEqual(nxt.status_code, 200)
        self.assertEqual(self.client.get(url).status_code, 405)

    @override_settings(NOTIFICATION_EMAIL_ENABLED=True, EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
    @patch("core.project_storage.delete_private_object_versions")
    def test_the_client_is_told_when_an_unpaid_project_is_removed(self, _delete):
        project = paid_project(self.client_profile, title="Never paid", paid=False)
        Project.objects.filter(pk=project.pk).update(created_at=timezone.now() - timedelta(hours=37))
        AuditLog.objects.create(action="project.expiry_reminder_sent", target_id=str(project.pk), detail={})
        AuditLog.objects.filter(target_id=str(project.pk)).update(created_at=timezone.now() - timedelta(hours=7))
        self.assertEqual(expire_unpaid_projects(), 1)
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn("has expired", mail.outbox[0].subject)
        self.assertIn("Never paid", mail.outbox[0].body)


class NoTokenTests(TestCase):
    @patch("core.qstash.requests.post")
    def test_without_a_token_no_alarm_is_sent(self, post):
        _admin, client_profile, _editors = create_people()
        with self.captureOnCommitCallbacks(execute=True):
            Project.objects.create(client=client_profile, title="Draft")
        post.assert_not_called()
