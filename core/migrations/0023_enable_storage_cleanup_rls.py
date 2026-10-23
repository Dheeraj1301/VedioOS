from django.db import migrations


def enable_rls(apps, schema_editor):
    if schema_editor.connection.vendor == "postgresql":
        schema_editor.execute("ALTER TABLE project_storage_cleanups ENABLE ROW LEVEL SECURITY")


class Migration(migrations.Migration):
    dependencies = [("core", "0022_supabase_identity_archival")]

    operations = [migrations.RunPython(enable_rls, migrations.RunPython.noop)]
