from django.apps import AppConfig
from django.db import transaction
from django.db.models.signals import post_migrate, post_save


class CoreConfig(AppConfig):
    name = "core"

    def ready(self):
        from .database_security import protect_private_tables

        post_migrate.connect(
            protect_private_tables, sender=self, dispatch_uid="vedioos.private_schema_security"
        )
        post_save.connect(_new_project_alarms, sender="core.Project", dispatch_uid="vedioos.unpaid_project_alarms")


def _new_project_alarms(sender, instance, created, **kwargs):
    """A new project starts its 36-hour payment timer: alarms for the 30-hour reminder and the expiry."""
    if created:
        from .project_storage import schedule_unpaid_alarms

        transaction.on_commit(lambda: schedule_unpaid_alarms(instance))
