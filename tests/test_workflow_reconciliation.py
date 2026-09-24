from io import StringIO

from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase
from django.utils import timezone

from core.models import Client, File, Order, Payment, Project, User
from core.workflow_reconciliation import workflow_findings
from operations.models import Editor, EditorAssignment

PASSWORD = "Synthetic-Workflow-72!Leaf"


class WorkflowReconciliationTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.client_user = User.objects.create_user(
            "workflow-client@example.test", PASSWORD, name="Workflow Client"
        )
        cls.client_profile = Client.objects.create(user=cls.client_user)
        cls.editor_user = User.objects.create_user(
            "workflow-editor@example.test", PASSWORD, name="Workflow Editor", role="editor"
        )
        cls.editor = Editor.objects.create(
            user=cls.editor_user,
            phone="1234567890",
            experience="Synthetic",
            tools="Resolve",
            portfolio="https://example.test/portfolio",
            previous_work="Synthetic work",
            expertise="Editing",
        )

    def test_empty_workflow_set_reconciles_without_private_output(self):
        output = StringIO()
        call_command("reconcile_workflows", stdout=output)
        self.assertIn("Workflow reconciliation passed", output.getvalue())
        self.assertNotIn(self.client_user.email, output.getvalue())

    def test_payment_assignment_and_file_inconsistencies_are_aggregated(self):
        project = Project.objects.create(client=self.client_profile, title="Private inconsistent project")
        order = Order.objects.create(
            project=project,
            payment_status="confirmed",
            total_minor=10000,
            currency="INR",
            terms_snapshot={},
        )
        Payment.objects.create(
            order=order,
            provider="synthetic",
            provider_reference="private-reference",
            amount_minor=9000,
            currency="USD",
            status="confirmed",
        )
        EditorAssignment.objects.create(project=project, editor=self.editor)
        File.objects.create(
            project=project,
            uploader=self.client_user,
            filename="private-name.mp4",
            object_key="private/object-key.mp4",
            content_type="video/mp4",
            size_bytes=9,
            sha256="0" * 64,
            category="source",
            state="ready",
            expires_at=timezone.now(),
        )
        findings = workflow_findings()
        self.assertEqual(findings["confirmed_order_activation"], 1)
        self.assertEqual(findings["confirmed_order_terms"], 1)
        self.assertEqual(findings["confirmed_payment_metadata"], 1)
        self.assertEqual(findings["active_assignment_payment"], 1)
        self.assertEqual(findings["ready_file_metadata"], 1)
        with self.assertRaises(CommandError) as raised:
            call_command("reconcile_workflows")
        message = str(raised.exception)
        self.assertNotIn(project.title, message)
        self.assertNotIn("private-reference", message)
        self.assertNotIn("private-name", message)
