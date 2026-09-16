from django.apps import apps
from django.db import connections


def protect_private_tables(sender, using, **kwargs):
    connection = connections[using]
    if connection.vendor != "postgresql":
        return
    with connection.cursor() as cursor:
        cursor.execute("SELECT current_schema()")
        schema = cursor.fetchone()[0]
        if schema != "vedioos":
            return
        cursor.execute("SELECT rolname FROM pg_roles WHERE rolname IN ('anon', 'authenticated')")
        roles = ["PUBLIC"] + [connection.ops.quote_name(row[0]) for row in cursor.fetchall()]
        tables = {model._meta.db_table for model in apps.get_models(include_auto_created=True)} | {
            "django_migrations"
        }
        cursor.execute("SELECT tablename FROM pg_tables WHERE schemaname = %s", [schema])
        existing = {row[0] for row in cursor.fetchall()}
        for table in sorted(tables & existing):
            qualified = f"{connection.ops.quote_name(schema)}.{connection.ops.quote_name(table)}"
            cursor.execute(f"ALTER TABLE {qualified} ENABLE ROW LEVEL SECURITY")
            cursor.execute(f"REVOKE ALL ON TABLE {qualified} FROM {', '.join(roles)}")
