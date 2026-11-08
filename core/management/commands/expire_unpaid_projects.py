from django.core.management.base import BaseCommand

from core.project_storage import expire_unpaid_projects


class Command(BaseCommand):
    help = "Cancel and remove the files of projects still unpaid 36 hours after creation."

    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS(f"Expired unpaid projects: {expire_unpaid_projects()}."))
