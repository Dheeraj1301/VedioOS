"""Client My Projects status-filter rendering and real-browser behavior."""

import json
import os
import secrets
import subprocess
from unittest import skipUnless

from django.contrib.staticfiles.testing import StaticLiveServerTestCase
from django.test import Client as Browser
from django.test import TestCase

from core.models import Client, Project, User


class ProjectStatusFilterTests(TestCase):
    def test_client_projects_exposes_every_status_in_the_correct_group(self):
        user = User.objects.create_user("filter@example.test", "Synthetic-72!Leaf", name="Filter")
        profile = Client.objects.create(user=user)
        expected_groups = {
            Project.Status.PENDING: "pending",
            Project.Status.PAID: "pending",
            Project.Status.WAITING: "pending",
            Project.Status.ASSIGNED: "ongoing",
            Project.Status.EDITING: "ongoing",
            Project.Status.DRAFT: "ongoing",
            Project.Status.REVIEW: "ongoing",
            Project.Status.REVISION_REQUESTED: "ongoing",
            Project.Status.REVISING: "ongoing",
            Project.Status.FINAL: "ongoing",
            Project.Status.COMPLETED: "completed",
            Project.Status.CANCELLED: "cancelled",
        }
        for status in expected_groups:
            Project.objects.create(client=profile, title=f"Project {status}", status=status)

        browser = Browser()
        browser.force_login(user)
        response = browser.get("/client/projects/")

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'id="project-status-filter"')
        for value, label in (("all", "All"), ("pending", "Pending"), ("ongoing", "Ongoing"), ("completed", "Completed"), ("cancelled", "Cancelled")):
            self.assertContains(response, f'<option value="{value}">{label}</option>', html=True)
        content = response.content.decode()
        for status, group in expected_groups.items():
            self.assertIn(f'data-status-group="{group}" data-project-status="{status}"', content)


@skipUnless(os.getenv("RUN_PROJECT_FILTER_BROWSER") == "1", "Requires Microsoft Edge")
class ProjectStatusFilterBrowserTests(StaticLiveServerTestCase):
    def test_filter_updates_without_navigation_and_shows_empty_state(self):
        password = secrets.token_urlsafe(24)
        user = User.objects.create_user(
            "project-filter-browser@example.test", password, name="Project Filter Browser"
        )
        profile = Client.objects.create(user=user)
        Project.objects.create(client=profile, title="Pending browser project")
        Project.objects.create(
            client=profile, title="Ongoing browser project", status=Project.Status.EDITING
        )
        Project.objects.create(
            client=profile, title="Completed browser project", status=Project.Status.COMPLETED
        )
        result = subprocess.run(
            ["node", "tests/project_status_filter_browser.mjs"],
            env={
                **os.environ,
                "PROJECT_FILTER_BROWSER_FIXTURE": json.dumps(
                    {"base": self.live_server_url, "email": user.email, "password": password}
                ),
            },
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=120,
        )
        self.assertEqual(result.returncode, 0, (result.stdout or "") + (result.stderr or ""))
        print(result.stdout)
