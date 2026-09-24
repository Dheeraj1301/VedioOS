"""Generic deployment probes that never expose dependency details."""

from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.http import JsonResponse
from django.views.decorators.http import require_GET


def _response(status, http_status=200):
    response = JsonResponse({"status": status}, status=http_status)
    response["Cache-Control"] = "no-store"
    return response


@require_GET
def liveness(request):
    """The Django process can accept requests; no dependency check is performed."""

    return _response("ok")


def database_ready():
    with connection.cursor() as cursor:
        cursor.execute("SELECT 1")
        if cursor.fetchone() != (1,):
            return False
    executor = MigrationExecutor(connection)
    targets = executor.loader.graph.leaf_nodes()
    return not executor.migration_plan(targets)


@require_GET
def readiness(request):
    """The database responds and the application schema is at the code's migration head."""

    try:
        ready = database_ready()
    except Exception:
        ready = False
    return _response("ok" if ready else "unavailable", 200 if ready else 503)
