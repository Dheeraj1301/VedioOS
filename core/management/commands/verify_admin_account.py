from getpass import getpass
from urllib.parse import urljoin

import requests
from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.test import Client as Browser

from core.models import Client, Order, User
from operations.models import Editor, NotificationCampaign


class Command(BaseCommand):
    help = "Verify a linked Supabase Auth administrator and protected admin pages."

    def add_arguments(self, parser):
        parser.add_argument("--email", required=True)

    def handle(self, *args, **options):
        email = options["email"].strip().lower()
        password = getpass("Admin password: ")
        user = User.objects.filter(email__iexact=email).first()
        if not user or user.role != User.Role.ADMIN or not hasattr(user, "admin_profile"):
            raise CommandError("The linked application administrator was not found.")
        if not user.supabase_auth_user_id:
            raise CommandError("The administrator is not linked to Supabase Auth.")

        secret_key = settings.SUPABASE_SECRET_KEY
        headers = {
            "apikey": secret_key,
            "Authorization": f"Bearer {secret_key}",
        }
        try:
            response = requests.get(
                urljoin(
                    settings.SUPABASE_AUTH_URL.rstrip("/") + "/",
                    f"auth/v1/admin/users/{user.supabase_auth_user_id}",
                ),
                headers=headers,
                timeout=settings.SUPABASE_AUTH_TIMEOUT_SECONDS,
            )
        except requests.RequestException as exc:
            raise CommandError("Supabase Auth verification could not be reached.") from exc
        if response.status_code != 200:
            raise CommandError(f"Supabase Auth verification failed (HTTP {response.status_code}).")
        auth_user = response.json()
        if str(auth_user.get("id")) != str(user.supabase_auth_user_id):
            raise CommandError("Supabase Auth UUID does not match the application link.")
        if str(auth_user.get("email") or "").lower() != email:
            raise CommandError("Supabase Auth email does not match the application identity.")
        if not (auth_user.get("email_confirmed_at") or auth_user.get("confirmed_at")):
            raise CommandError("Supabase Auth email is not confirmed.")
        self.stdout.write("PASS: confirmed Supabase Auth enrollment and immutable UUID link")

        browser = Browser()
        login = browser.post("/login/", {"username": email, "password": password})
        if login.status_code != 302 or login.url != "/dashboard/":
            raise CommandError("Global login did not accept the administrator credentials.")
        dashboard = browser.get("/dashboard/")
        if dashboard.status_code != 302 or dashboard.url != "/admin/":
            raise CommandError("The administrator was not routed to the admin dashboard.")
        self.stdout.write("PASS: /login/ routes the admin through /dashboard/ to /admin/")

        pages = {
            "dashboard": "/admin/",
            "orders": "/admin/orders/",
            "payments": "/admin/payments/",
            "editors": "/admin/editors/",
            "clients": "/admin/clients/",
            "notifications": "/admin/notifications/",
            "new notification form": "/admin/notifications/new/",
            "plans and pricing": "/admin/pricing/",
        }
        for label, path in pages.items():
            response = browser.get(path)
            if response.status_code != 200:
                raise CommandError(f"Admin {label} failed with HTTP {response.status_code}.")
            self.stdout.write(f"PASS: admin {label}")

        detail_pages = []
        order = Order.objects.order_by("created_at").first()
        if order:
            detail_pages.append(("order detail", f"/admin/orders/{order.pk}/"))
        editor = Editor.objects.order_by("created_at").first()
        if editor:
            detail_pages.append(("editor detail", f"/admin/editors/{editor.pk}/"))
        client = Client.objects.order_by("created_at").first()
        if client:
            detail_pages.append(("client detail", f"/admin/clients/{client.pk}/"))
        campaign = NotificationCampaign.objects.order_by("created_at").first()
        if campaign:
            detail_pages.append(
                ("notification management", f"/admin/notifications/{campaign.pk}/edit/")
            )
        for label, path in detail_pages:
            response = browser.get(path)
            if response.status_code != 200:
                raise CommandError(f"Admin {label} failed with HTTP {response.status_code}.")
            self.stdout.write(f"PASS: admin {label}")

        logout = browser.post("/logout/")
        if logout.status_code != 302:
            raise CommandError("Verification logout failed.")
        user.refresh_from_db()
        if user.active_session_key:
            raise CommandError("Verification session was not cleared.")
        self.stdout.write(self.style.SUCCESS("Admin enrollment and workflow verification passed."))
