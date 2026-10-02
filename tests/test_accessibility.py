from django.test import TestCase
from django.utils import timezone

from core.models import File, UploadPolicy
from operations.models import EditorAssignment
from tests.assignment_fixtures import create_people, paid_project


class AccessibilitySemanticsTests(TestCase):
    def test_project_actions_have_distinct_names_and_live_feedback(self):
        admin, client_profile, editors = create_people()
        project = paid_project(client_profile)
        EditorAssignment.objects.create(project=project, editor=editors[0], assigned_by=admin)
        UploadPolicy.objects.update_or_create(
            pk=1,
            defaults={"max_bytes": 1024, "allowed_types": {".mp4": ["video/mp4"]}},
        )
        File.objects.create(
            project=project,
            uploader=client_profile.user,
            filename="private source.mp4",
            object_key="synthetic/private-source",
            storage_version="synthetic-version",
            content_type="video/mp4",
            size_bytes=12,
            sha256="a" * 64,
            category="source",
            state="ready",
            expires_at=timezone.now(),
        )
        self.client.force_login(client_profile.user)
        response = self.client.get(f"/client/projects/{project.pk}/")
        self.assertContains(response, 'main id="main" class="workspace-main" tabindex="-1"')
        self.assertContains(response, 'id="download-status" role="status" aria-live="polite"')
        self.assertContains(
            response,
            'aria-label="Download private source.mp4 in original quality"',
        )
        self.assertNotContains(response, "Upload source files")
        self.assertNotContains(response, "Add Inspiration Reel/Video")
        self.assertNotContains(response, "Assigned editor")
        self.assertNotContains(response, "Delivery date")
        self.assertNotContains(response, "What's next?")
        self.assertContains(response, 'class="project-columns project-columns-single"')

        self.client.force_login(editors[0].user)
        editor_response = self.client.get(f"/editor/projects/{project.pk}/")
        self.assertContains(editor_response, "Upload edited files")
        self.assertContains(editor_response, "Assigned editor")
        self.assertNotContains(editor_response, "project-columns-single")
