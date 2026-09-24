from datetime import timedelta

from django.test import Client as Browser
from django.test import TestCase
from django.utils import timezone

from core.models import Client, Order, Project, User
from operations.models import Admin, Editor, EditorAssignment, EditorAvailability
from operations.projects import project_page

PASSWORD = "Synthetic-Projects-72!Leaf"


class ProjectRosterTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.admin = User.objects.create_user(
            "project-admin@example.test", PASSWORD, name="Admin", role="admin"
        )
        Admin.objects.create(user=cls.admin)
        cls.client_user = User.objects.create_user(
            "project-client@example.test", PASSWORD, name="Project Client"
        )
        profile = Client.objects.create(user=cls.client_user)
        cls.overdue = Project.objects.create(
            client=profile,
            title="Overdue unassigned project",
            status=Project.Status.WAITING,
            expected_delivery_at=timezone.now() - timedelta(hours=2),
        )
        Order.objects.create(project=cls.overdue, payment_status="confirmed")
        assigned = Project.objects.create(
            client=profile, title="Assigned editing project", status=Project.Status.EDITING
        )
        Order.objects.create(project=assigned, payment_status="confirmed")
        editor_user = User.objects.create_user(
            "project-editor@example.test", PASSWORD, name="Project Editor", role="editor"
        )
        editor = Editor.objects.create(
            user=editor_user,
            phone="1234567890",
            experience="Synthetic",
            tools="Resolve",
            portfolio="https://example.test/portfolio",
            previous_work="Synthetic work",
            expertise="Editing",
        )
        EditorAvailability.objects.create(editor=editor)
        EditorAssignment.objects.create(project=assigned, editor=editor, assigned_by=cls.admin)
        for number in range(2):
            pending = Project.objects.create(
                client=profile, title=f"Pending project {number}", status=Project.Status.PENDING
            )
            Order.objects.create(project=pending)

    def test_queues_search_and_assignment_annotation_reconcile(self):
        overdue, cursor, queue, search = project_page(
            self.admin, queue="overdue", search="Project Client"
        )
        self.assertIsNone(cursor)
        self.assertEqual(queue, "overdue")
        self.assertEqual(search, "Project Client")
        self.assertEqual([project.id for project in overdue], [self.overdue.id])
        unassigned = project_page(self.admin, queue="unassigned")[0]
        self.assertEqual([project.id for project in unassigned], [self.overdue.id])
        active = project_page(self.admin, queue="active")[0]
        self.assertEqual(active[0].current_editor_name, "Project Editor")

    def test_cursor_is_stable_and_invalid_cursor_is_rejected(self):
        first, cursor, _queue, _search = project_page(self.admin, size=2)
        self.assertEqual(len(first), 2)
        self.assertIsNotNone(cursor)
        older, older_cursor, _queue, _search = project_page(self.admin, before=cursor, size=2)
        self.assertEqual(len(older), 2)
        self.assertIsNone(older_cursor)
        self.assertTrue(set(row.id for row in first).isdisjoint(row.id for row in older))
        admin = Browser()
        admin.force_login(self.admin)
        self.assertEqual(admin.get("/admin/projects/", {"before": "invalid"}).status_code, 404)

    def test_admin_page_is_role_protected_and_renders_operations(self):
        self.assertEqual(Browser().get("/admin/projects/").status_code, 302)
        client = Browser()
        client.force_login(self.client_user)
        self.assertEqual(client.get("/admin/projects/").status_code, 403)
        admin = Browser()
        admin.force_login(self.admin)
        response = admin.get("/admin/projects/", {"queue": "overdue"})
        self.assertContains(response, "Project operations")
        self.assertContains(response, "Overdue unassigned project")
        self.assertContains(response, "Current editor")
        self.assertNotContains(response, "Assigned editing project")
