from django.apps import AppConfig
from django.db.models.signals import post_migrate


class CoreConfig(AppConfig):
    name = "core"

    def ready(self):
        from .database_security import protect_private_tables

        post_migrate.connect(
            protect_private_tables, sender=self, dispatch_uid="vedioos.private_schema_security"
        )
