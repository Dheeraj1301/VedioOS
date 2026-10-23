import hashlib
import uuid

from django.conf import settings
from django.contrib import messages
from django.db import transaction
from django.shortcuts import redirect, render
from django.views.decorators.http import require_GET

from .landing_content import landing_content, landing_faqs
from .landing_forms import FAQFormSet, LandingPageForm
from .models import LandingPageSettings
from .permissions import role_required
from .storage import landing_video_permission, storage_client
from .views import audit


def _upload_video(upload):
    digest = hashlib.sha256()
    for chunk in upload.chunks():
        digest.update(chunk)
    upload.seek(0)
    object_key = f"landing/hero/{uuid.uuid4()}.mp4"
    result = storage_client().put_object(
        Bucket=settings.S3_BUCKET,
        Key=object_key,
        Body=upload,
        ContentType="video/mp4",
        Metadata={"sha256": digest.hexdigest()},
    )
    return object_key, result.get("VersionId", ""), digest.hexdigest()


@role_required("admin")
def landing_page_control(request):
    config = LandingPageSettings.objects.filter(pk=1).first()
    current = landing_content(config.content if config else None)
    form = LandingPageForm(request.POST or None, request.FILES or None, content=current)
    faq_formset = FAQFormSet(
        request.POST or None, initial=landing_faqs(config.content if config else None), prefix="faqs"
    )
    if request.method == "POST" and form.is_valid() and faq_formset.is_valid():
        upload = form.cleaned_data.get("hero_video")
        uploaded = _upload_video(upload) if upload else None
        old_key = config.hero_video_object_key if config else ""
        old_version = config.hero_video_storage_version if config else ""
        try:
            with transaction.atomic():
                config, _ = LandingPageSettings.objects.select_for_update().get_or_create(pk=1)
                faq_items = []
                for faq_form in faq_formset.ordered_forms:
                    if faq_form.cleaned_data.get("DELETE"):
                        continue
                    faq_items.append(
                        {
                            "id": faq_form.cleaned_data.get("id") or uuid.uuid4().hex,
                            "title": faq_form.cleaned_data["title"],
                            "content": faq_form.cleaned_data["content"],
                            "published": faq_form.cleaned_data["published"],
                        }
                    )
                config.content = {**form.content(), "faqs": faq_items}
                config.updated_by = request.user
                if form.cleaned_data.get("remove_hero_video"):
                    config.hero_video_object_key = ""
                    config.hero_video_storage_version = ""
                    config.hero_video_filename = ""
                    config.hero_video_content_type = ""
                    config.hero_video_size_bytes = None
                    config.hero_video_sha256 = ""
                if uploaded:
                    (
                        config.hero_video_object_key,
                        config.hero_video_storage_version,
                        config.hero_video_sha256,
                    ) = uploaded
                    config.hero_video_filename = upload.name[:240]
                    config.hero_video_content_type = "video/mp4"
                    config.hero_video_size_bytes = upload.size
                config.save()
                audit(
                    request.user,
                    "landing_page.updated",
                    config.pk,
                    {
                        "video_replaced": bool(uploaded),
                        "video_removed": bool(form.cleaned_data.get("remove_hero_video")),
                    },
                )
        except Exception:
            if uploaded:
                storage_client().delete_object(
                    Bucket=settings.S3_BUCKET, Key=uploaded[0], VersionId=uploaded[1]
                )
            raise
        if old_key and (uploaded or form.cleaned_data.get("remove_hero_video")):
            try:
                params = {"Bucket": settings.S3_BUCKET, "Key": old_key}
                if old_version:
                    params["VersionId"] = old_version
                storage_client().delete_object(**params)
            except Exception:
                messages.warning(request, "The page was saved, but the previous video needs storage cleanup.")
        messages.success(request, "Landing page saved.")
        return redirect("landing_page_control")
    return render(
        request,
        "operations/landing_page.html",
        {"title": "Landing page", "form": form, "faq_formset": faq_formset, "config": config},
    )


@require_GET
def landing_hero_video(request):
    config = LandingPageSettings.objects.filter(pk=1).first()
    if not config or not config.hero_video_object_key:
        from django.http import Http404

        raise Http404
    return redirect(landing_video_permission(config))
