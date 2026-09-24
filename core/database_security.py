"""Private-schema migration protection and read-only security inspection."""

from django.apps import apps
from django.db import connection, connections


def protect_private_tables(sender, using, **kwargs):
    active_connection = connections[using]
    if active_connection.vendor != "postgresql":
        return
    with active_connection.cursor() as cursor:
        cursor.execute("SELECT current_schema()")
        schema = cursor.fetchone()[0]
        if schema != "vedioos":
            return
        cursor.execute("SELECT rolname FROM pg_roles WHERE rolname IN ('anon', 'authenticated')")
        roles = ["PUBLIC"] + [active_connection.ops.quote_name(row[0]) for row in cursor.fetchall()]
        tables = {model._meta.db_table for model in apps.get_models(include_auto_created=True)} | {
            "django_migrations"
        }
        cursor.execute("SELECT tablename FROM pg_tables WHERE schemaname = %s", [schema])
        existing = {row[0] for row in cursor.fetchall()}
        for table in sorted(tables & existing):
            qualified = (
                f"{active_connection.ops.quote_name(schema)}."
                f"{active_connection.ops.quote_name(table)}"
            )
            cursor.execute(f"ALTER TABLE {qualified} ENABLE ROW LEVEL SECURITY")
            cursor.execute(f"REVOKE ALL ON TABLE {qualified} FROM {', '.join(roles)}")


def inspect_database_security():
    if connection.vendor != "postgresql":
        return {"vendor": connection.vendor}

    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT rolsuper, rolcreaterole, rolcreatedb, rolreplication, "
            "rolbypassrls, rolconnlimit FROM pg_roles WHERE rolname = current_user"
        )
        role = cursor.fetchone()
        cursor.execute(
            "SELECT n.nspname, n.nspowner = (SELECT oid FROM pg_roles WHERE rolname = current_user), "
            "count(*) FILTER (WHERE acl.grantee = 0) "
            "FROM pg_namespace n "
            "LEFT JOIN LATERAL aclexplode(coalesce(n.nspacl, acldefault('n', n.nspowner))) acl "
            "ON true WHERE n.nspname = current_schema() GROUP BY n.nspname, n.nspowner"
        )
        schema, schema_owned, public_schema_privileges = cursor.fetchone()
        cursor.execute(
            "SELECT rolname FROM pg_roles WHERE rolname IN ('anon', 'authenticated')"
        )
        browser_roles = [row[0] for row in cursor.fetchall()]
        browser_schema_privileges = 0
        for browser_role in browser_roles:
            cursor.execute(
                "SELECT has_schema_privilege(%s, %s, 'USAGE') OR "
                "has_schema_privilege(%s, %s, 'CREATE')",
                [browser_role, schema, browser_role, schema],
            )
            browser_schema_privileges += int(cursor.fetchone()[0])
        cursor.execute(
            "SELECT count(*), count(*) FILTER (WHERE NOT rowsecurity), "
            "count(*) FILTER (WHERE tableowner <> current_user) "
            "FROM pg_tables WHERE schemaname = %s",
            [schema],
        )
        table_count, tables_without_rls, tables_not_owned = cursor.fetchone()
        cursor.execute(
            "SELECT count(*) FROM information_schema.role_table_grants "
            "WHERE table_schema = %s AND grantee IN ('PUBLIC', 'anon', 'authenticated')",
            [schema],
        )
        browser_table_grants = cursor.fetchone()[0]
        cursor.execute(
            "SELECT count(*) FROM information_schema.role_usage_grants "
            "WHERE object_schema = %s AND grantee IN ('PUBLIC', 'anon', 'authenticated')",
            [schema],
        )
        browser_sequence_grants = cursor.fetchone()[0]
        cursor.execute(
            "SELECT count(*) FROM information_schema.role_routine_grants "
            "WHERE routine_schema = %s AND grantee IN ('PUBLIC', 'anon', 'authenticated')",
            [schema],
        )
        browser_routine_grants = cursor.fetchone()[0]
        cursor.execute(
            "SELECT count(*) FROM pg_default_acl defaults "
            "JOIN pg_namespace n ON n.oid = defaults.defaclnamespace "
            "CROSS JOIN LATERAL aclexplode(defaults.defaclacl) acl "
            "LEFT JOIN pg_roles granted ON granted.oid = acl.grantee "
            "WHERE n.nspname = %s AND "
            "(acl.grantee = 0 OR granted.rolname IN ('anon', 'authenticated'))",
            [schema],
        )
        browser_default_grants = cursor.fetchone()[0]
        cursor.execute(
            "SELECT extension.extname, extension.extversion, namespace.nspname "
            "FROM pg_extension extension JOIN pg_namespace namespace "
            "ON namespace.oid = extension.extnamespace ORDER BY extension.extname"
        )
        extensions = [
            {"name": name, "version": version, "schema": extension_schema}
            for name, version, extension_schema in cursor.fetchall()
        ]
        cursor.execute("SELECT count(*) FROM pg_event_trigger WHERE evtenabled <> 'D'")
        enabled_event_triggers = cursor.fetchone()[0]

    return {
        "vendor": "postgresql",
        "schema": schema,
        "role_elevated_flags": sum(bool(value) for value in role[:5]),
        "role_connection_limit": role[5],
        "schema_owned_by_runtime_role": schema_owned,
        "public_schema_privileges": public_schema_privileges,
        "browser_roles_present": len(browser_roles),
        "browser_schema_privileges": browser_schema_privileges,
        "table_count": table_count,
        "tables_without_rls": tables_without_rls,
        "tables_not_owned_by_runtime_role": tables_not_owned,
        "browser_table_grants": browser_table_grants,
        "browser_sequence_grants": browser_sequence_grants,
        "browser_routine_grants": browser_routine_grants,
        "browser_default_grants": browser_default_grants,
        "extensions": extensions,
        "enabled_event_triggers": enabled_event_triggers,
    }


def database_security_findings(facts):
    findings = []

    def fail(code):
        findings.append(code)

    if facts.get("vendor") != "postgresql":
        fail("postgresql_required")
        return findings
    if facts.get("schema") != "vedioos":
        fail("unexpected_schema")
    if facts.get("role_elevated_flags"):
        fail("runtime_role_elevated")
    if facts.get("role_connection_limit", -1) < 1:
        fail("runtime_role_connection_limit_unbounded")
    if not facts.get("schema_owned_by_runtime_role"):
        fail("schema_owner_mismatch")
    if facts.get("public_schema_privileges"):
        fail("public_schema_privileges")
    if facts.get("browser_roles_present") != 2:
        fail("browser_roles_missing")
    if facts.get("browser_schema_privileges"):
        fail("browser_schema_privileges")
    if not facts.get("table_count"):
        fail("application_tables_missing")
    if facts.get("tables_without_rls"):
        fail("tables_without_rls")
    if facts.get("tables_not_owned_by_runtime_role"):
        fail("table_owner_mismatch")
    for key in (
        "browser_table_grants",
        "browser_sequence_grants",
        "browser_routine_grants",
        "browser_default_grants",
    ):
        if facts.get(key):
            fail(key)
    return findings


def database_security_report():
    facts = inspect_database_security()
    findings = database_security_findings(facts)
    return {
        "status": "pass" if not findings else "fail",
        "code": "protected" if not findings else "database_security_failed",
        "findings": findings,
        "facts": facts,
    }
