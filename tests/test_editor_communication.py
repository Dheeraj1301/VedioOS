import uuid

from django.test import TestCase
from django.utils import timezone

from core.context import NAV
from core.models import Project
from operations.models import EditorAssignment, ProjectMessage
from tests.assignment_fixtures import create_people, paid_project


class EditorCommunicationTests(TestCase):
    def setUp(self):
        self.admin, self.client_profile, self.editors = create_people()
        self.editor = self.editors[0]
        self.ongoing = paid_project(self.client_profile, title="Assigned ongoing edit")
        self.ongoing.status = Project.Status.EDITING
        self.ongoing.save(update_fields=["status"])
        self.completed = paid_project(self.client_profile, title="Assigned completed edit")
        self.completed.status = Project.Status.COMPLETED
        self.completed.save(update_fields=["status"])
        self.other_editor_project = paid_project(self.client_profile, title="Another editor project")
        self.unassigned = paid_project(self.client_profile, title="Unassigned paid project")
        self.former_assignment = paid_project(self.client_profile, title="Former editor project")
        self.unpaid = paid_project(self.client_profile, title="Assigned unpaid project")
        self.unpaid.payment_completed_at = None
        self.unpaid.status = Project.Status.PENDING
        self.unpaid.save(update_fields=["payment_completed_at", "status"])
        self.unpaid.order.payment_status = "pending"
        self.unpaid.order.save(update_fields=["payment_status"])
        for project in [self.ongoing, self.completed, self.unpaid]:
            EditorAssignment.objects.create(
                project=project,
                editor=self.editor,
                assigned_by=self.admin,
            )
        EditorAssignment.objects.create(
            project=self.other_editor_project,
            editor=self.editors[1],
            assigned_by=self.admin,
        )
        ended_assignment = EditorAssignment.objects.create(
            project=self.former_assignment,
            editor=self.editor,
            assigned_by=self.admin,
        )
        ended_assignment.ended_at = timezone.now()
        ended_assignment.save(update_fields=["ended_at"])
        EditorAssignment.objects.create(
            project=self.former_assignment,
            editor=self.editors[1],
            assigned_by=self.admin,
        )
        self.client.force_login(self.editor.user)

    def test_editor_sidebar_omits_calls_and_wallet(self):
        self.assertEqual(
            NAV["editor"],
            [
                ("Assigned projects", "/editor/"),
                ("Project details", "/editor/projects/"),
                ("Revisions", "/editor/revisions/"),
                ("Project Communication", "/editor/communication/"),
                ("Availability", "/editor/availability/"),
            ],
        )
        page = self.client.get("/editor/")
        self.assertNotContains(page, '>Calls<span', html=False)
        self.assertNotContains(page, '>Wallet<span', html=False)
        self.assertContains(page, '>Project Communication<span', html=False)
        self.assertNotContains(page, "Private workspace")
        self.assertNotContains(
            page,
            "Your assignments, deadlines, and creative briefs in one place.",
        )
        self.assertNotContains(page, "✅ Available")
        self.assertEqual(self.client.get("/editor/calls/").status_code, 200)

    def test_editor_static_workspace_placeholders_are_removed(self):
        projects_page = self.client.get("/editor/projects/")
        self.assertNotContains(projects_page, "Your workspace")

        self.client.force_login(self.editors[2].user)
        communication_page = self.client.get("/editor/communication/")
        self.assertContains(communication_page, "No ongoing assigned projects")
        self.assertContains(communication_page, "No completed assigned projects")
        self.assertNotContains(
            communication_page,
            "Paid projects currently assigned to you will appear here.",
        )
        self.assertNotContains(
            communication_page,
            "Completed conversations for projects still assigned to you will remain here as read-only history.",
        )

    def test_list_contains_only_current_paid_assignments_grouped_by_status(self):
        response = self.client.get("/editor/communication/")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Ongoing")
        self.assertContains(response, "Completed")
        self.assertContains(response, self.ongoing.title)
        self.assertContains(response, self.completed.title)
        self.assertNotContains(response, self.other_editor_project.title)
        self.assertNotContains(response, self.unassigned.title)
        self.assertNotContains(response, self.unpaid.title)
        self.assertNotContains(response, self.former_assignment.title)
        content = response.content.decode()
        self.assertLess(content.index(self.ongoing.title), content.index(self.completed.title))

    def test_detail_shows_shared_conversation_with_author_role_badges(self):
        ProjectMessage.objects.create(
            project=self.ongoing,
            author=self.client_profile.user,
            audience=ProjectMessage.Audience.SHARED,
            body="Client-visible question",
            request_key=uuid.uuid4(),
        )
        ProjectMessage.objects.create(
            project=self.ongoing,
            author=self.admin,
            audience=ProjectMessage.Audience.INTERNAL,
            body="Private operational note",
            request_key=uuid.uuid4(),
        )
        response = self.client.get(f"/editor/communication/{self.ongoing.id}/")
        self.assertContains(response, "Conversation")
        self.assertContains(response, "Client-visible question")
        self.assertContains(response, self.client_profile.user.name)
        self.assertContains(response, ">Client</span>", html=False)
        self.assertNotContains(response, "Private operational note")
        self.assertContains(response, "Send a reply")
        self.assertContains(response, ">Send reply</button>", html=False)

    def test_reply_persists_and_is_immediately_visible_to_editor_and_client(self):
        detail_path = f"/editor/communication/{self.ongoing.id}/"
        detail = self.client.get(detail_path)
        sent = self.client.post(
            f"/editor/communication/{self.ongoing.id}/reply/",
            {"body": "Editor shared reply", "request_key": detail.context["message_request_key"]},
        )
        self.assertRedirects(sent, detail_path)
        message = ProjectMessage.objects.get(project=self.ongoing, body="Editor shared reply")
        self.assertEqual(message.author, self.editor.user)
        self.assertEqual(message.audience, ProjectMessage.Audience.SHARED)
        self.assertContains(self.client.get(detail_path), "Editor shared reply")

        self.client.force_login(self.client_profile.user)
        client_page = self.client.get(f"/client/communication/{self.ongoing.id}/")
        self.assertContains(client_page, "Editor shared reply")
        self.assertContains(client_page, self.editor.user.name)

    def test_editor_reply_rejects_six_consecutive_digits(self):
        detail_path = f"/editor/communication/{self.ongoing.id}/"
        detail = self.client.get(detail_path)
        self.assertContains(detail, "data-digit-restricted", html=False)
        blocked = self.client.post(
            f"/editor/communication/{self.ongoing.id}/reply/",
            {
                "body": "Do not share 123456",
                "request_key": detail.context["message_request_key"],
            },
        )
        self.assertEqual(blocked.status_code, 400)
        self.assertContains(
            blocked,
            "Phone numbers are restricted. Please do not enter more than 5 consecutive numbers.",
            status_code=400,
        )
        self.assertFalse(ProjectMessage.objects.filter(body__contains="123456").exists())

    def test_completed_is_read_only_and_other_projects_are_denied(self):
        ProjectMessage.objects.create(
            project=self.completed,
            author=self.client_profile.user,
            audience=ProjectMessage.Audience.SHARED,
            body="Completed conversation history",
            request_key=uuid.uuid4(),
        )
        path = f"/editor/communication/{self.completed.id}/"
        response = self.client.get(path)
        self.assertContains(response, "Completed conversation history")
        self.assertContains(response, "This project is completed. Messaging is disabled.")
        self.assertNotContains(response, ">Send reply</button>", html=False)
        before = ProjectMessage.objects.filter(project=self.completed).count()
        blocked = self.client.post(
            f"/editor/communication/{self.completed.id}/reply/",
            {"body": "Blocked reply", "request_key": uuid.uuid4()},
            follow=True,
        )
        self.assertContains(blocked, "This project is complete. Messaging is disabled.")
        self.assertEqual(ProjectMessage.objects.filter(project=self.completed).count(), before)
        for project in [
            self.other_editor_project,
            self.unassigned,
            self.unpaid,
            self.former_assignment,
        ]:
            with self.subTest(project=project.title):
                self.assertEqual(
                    self.client.get(f"/editor/communication/{project.id}/").status_code,
                    404,
                )
                self.assertEqual(
                    self.client.post(
                        f"/editor/communication/{project.id}/reply/",
                        {"body": "Denied", "request_key": uuid.uuid4()},
                    ).status_code,
                    404,
                )
