from django.test import TestCase
from django.utils import timezone

from core.models import File, UploadPolicy
from tests.assignment_fixtures import create_people, paid_project


class AccessibilitySemanticsTests(TestCase):
    def test_project_actions_have_distinct_names_and_live_feedback(self):
        _, client_profile, _ = create_people()
        project = paid_project(client_profile)
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
        self.assertContains(
            response,
            'id="upload-status" class="upload-status" role="status" aria-live="polite"',
        )
        self.assertContains(response, 'id="download-status" role="status" aria-live="polite"')
        self.assertContains(
            response,
            'aria-label="Download private source.mp4 in original quality"',
        )
        self.assertContains(response, "Upload source files")
        self.assertContains(response, "Upload inspiration")
        self.assertContains(response, 'data-fixed-category="reference"')
