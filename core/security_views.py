import hmac

from django.conf import settings
from django.http import JsonResponse
from django.views.decorators.http import require_GET

from .security_monitor import run_security_monitor


@require_GET
def scheduled_security_monitor(request):
    configured = settings.CRON_SECRET
    supplied = request.headers.get("Authorization", "")
    expected = f"Bearer {configured}" if configured else ""
    if not expected or not hmac.compare_digest(supplied, expected):
        return JsonResponse({"error": "unauthorized"}, status=401)
    if not settings.SECURITY_MONITOR_ENABLED:
        return JsonResponse({"error": "monitor_disabled"}, status=503)
    result = run_security_monitor()
    return JsonResponse({
        "status": result["status"],
        "critical_count": result["critical_count"],
        "warning_count": result["warning_count"],
    })
