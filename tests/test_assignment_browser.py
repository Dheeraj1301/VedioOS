import json
import os
import secrets
import subprocess
from unittest import skipUnless

from django.contrib.staticfiles.testing import StaticLiveServerTestCase
from django.test import override_settings

from operations.models import AssignmentPolicy, EditorAssignment, EditorProficiency
from tests.assignment_fixtures import create_people, paid_project


@skipUnless(os.getenv("RUN_ASSIGNMENT_BROWSER") == "1", "Opt-in browser test")
@override_settings(DEBUG=True)
class AssignmentBrowserTests(StaticLiveServerTestCase):
    def test_classification_allocation_and_reassignment(self):
        for level in ["beginner", "intermediate", "advanced"]:
            EditorProficiency.objects.get_or_create(level=level)
        AssignmentPolicy.objects.get_or_create(pk=1)
        password = secrets.token_urlsafe(24)
        admin, client, editors = create_people(password=password)
        project = paid_project(client, title="Synthetic assignment browser project")
        fixture = {
            "base": self.live_server_url,
            "password": password,
            "admin": admin.email,
            "editors": [{"email": editor.user.email, "id": str(editor.id)} for editor in editors],
            "project": str(project.id),
        }
        result = subprocess.run(
            ["node", "tests/assignment_browser.mjs"],
            env={**os.environ, "ASSIGNMENT_BROWSER_FIXTURE": json.dumps(fixture)},
            capture_output=True,
            text=True,
            timeout=150,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(
            EditorAssignment.objects.filter(project=project, ended_at__isnull=True).get().editor_id,
            editors[1].id,
        )
        self.assertEqual(EditorAssignment.objects.filter(project=project).count(), 2)
        print(result.stdout)
