# Storage and AWS credit strategy

Owner decision (Dheeraj, 2026-11-01): each project's files live in their own folder, a project's working life is about 3 days after completion, and an administrator then deletes the project from the admin dashboard, which permanently removes its files from S3. Goal: lowest possible S3 cost so the AWS credits last.

## How the money is actually spent

S3 charges for four things. Prices below are the defaults the dashboard uses (S3 Standard, Sydney `ap-southeast-2`, USD); check them on the AWS pricing page and override them in settings if they change.

| What | Default rate | What it means for one project with 2 GB of footage |
|---|---|---|
| Storage | $0.025 per GB-month | 2 GB kept 7 days ≈ $0.012 |
| Data out (downloads to the internet) | $0.114 per GB, first 100 GB a month free account-wide | the editor downloads 2 GB once ≈ $0.23 |
| Uploads (PUT requests) | $0.0055 per 1,000 | a handful of uploads ≈ $0.00003 |
| Downloads (GET requests) | $0.00044 per 1,000 | negligible |

**Conclusion: downloads cost about 20× more than keeping the same file for a week.** Deleting projects quickly helps, but the biggest lever is how many times large files are downloaded.

## The lifecycle

1. **Separate folder per project.** Every upload is stored at `edits/projects/<project-id>/<file-id>`, so one project's files never mix with another's and can be removed together. (Already how the app works.)
2. **Work and review.** Client uploads, editor downloads, editor uploads versions, client reviews and accepts.
3. **Completion.** Accepting a version completes the project; the dashboard starts counting "days since completion".
4. **Delete after about 3 days.** In **Admin → Storage costs**, a completed (or cancelled) project shows **Delete project files**. It requires a confirmation tick, then:
   - hides the project from client, editor and admin lists (the existing archive rule, so payments, messages and audit history stay intact and attributable),
   - permanently deletes **every stored version** of every file in that project's folder (with versioning on, a plain delete would leave a hidden copy that still costs money),
   - records who deleted it and when, and keeps the estimated cost for reporting.
   Projects that are still in progress cannot be deleted from this screen.
5. **Retry safety.** If S3 is unreachable, the project is still hidden and a retry is queued; `manage.py cleanup_archived_project_storage` finishes it.

Deletion stays manual, as decided: nothing is removed automatically.

## Settings to apply once in the AWS console (bucket `briodata` → Management → Lifecycle rules)

These are safety nets that cost nothing:

- [ ] **Abort incomplete multipart uploads after 1 day.** Interrupted uploads otherwise keep billing invisibly.
- [ ] **Permanently delete noncurrent versions after 1 day** and **delete expired object delete markers.** The app already removes all versions; this catches anything left by a failed or manual delete.
- [ ] **AWS Budgets → Create budget**: a monthly cost budget of, for example, $5 with an email alert at 80%, plus a credits-usage alert, so you hear about surprises before the credits are gone.

## Further savings, in order of impact

1. **Ask clients to upload only the clips they need**, and editors to deliver one final export rather than many drafts. Bytes downloaded are what cost money.
2. **Serve downloads through CloudFront later.** CloudFront's always-free tier includes 1 TB of data out a month, compared with 100 GB for S3 direct. That is a separate setup (a distribution in front of `briodata` with signed URLs); worth it once monthly downloads pass about 100 GB.
3. **Keep the landing hero video small** (H.264, about 1080p, under 40 MB). It is downloaded by every visitor, so it is the one file whose cost grows with traffic rather than with projects. It is not counted per project in the dashboard.
4. **Region.** The bucket is in Sydney. If most clients and editors are in India, a Mumbai (`ap-south-1`) bucket would be faster for them and has slightly cheaper data out. Moving means creating a new bucket and pointing the app at it; only worth doing before real client data arrives.

## The dashboard (Admin → Storage costs)

Per project: client, status, days since completion, files, data currently stored, number and volume of downloads, and an **estimated** cost to date (storage time + downloads + requests). Totals at the top, and estimated credits remaining when `AWS_CREDITS_USD` is set.

It is an estimate from the app's own records (file sizes, upload and deletion times, authorised downloads), not an AWS invoice: AWS does not bill per folder. Treat a download link as a full download (the upper bound). The real figure is in **AWS Billing → Bills** and **Credits**; the estimate should stay close to it for project files.

Rates are settings, overridable through environment variables: `AWS_S3_STORAGE_USD_PER_GB_MONTH`, `AWS_S3_EGRESS_USD_PER_GB`, `AWS_S3_PUT_USD_PER_1000`, `AWS_S3_GET_USD_PER_1000`, `AWS_CREDITS_USD`.
