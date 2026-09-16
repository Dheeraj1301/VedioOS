# Day 1 architecture

## Chosen implementation

- **Django 5.2:** one server-rendered application with built-in password hashing, database sessions, CSRF protection, forms, and migrations. A separate SPA/auth service is unnecessary for this milestone.
- **Shared identity:** `core.User`, table `users`, uses normalized, case-insensitively unique email and a client/editor/admin role. Role-specific profiles refer to this identity. Registration never trusts privileged client fields.
- **Database:** Supabase PostgreSQL in the private `vedioos` schema for the configured workspace; SQLite is retained as an explicit offline/test option. See [connection details](SUPABASE.md). Concurrent later-stage workflows and production deployment still need their own verification.
- **Storage:** Boto3 S3 adapter, tested against a real SeaweedFS 4.47 process on loopback. The application receives file metadata, not the video request body. A production S3-compatible service must support checksum verification, conditional writes, versioning, and signed access; run the integration suite against the selected provider.
- **UI:** Django templates, shared responsive CSS, small browser scripts. Locally vendored hash-wasm computes SHA-256 incrementally in 4 MiB chunks; it does not transform media or buffer the whole video.

These are implementation choices made within the authorized Day 1 work. They do not finalize pricing, commercial upload limits, delivery terms, hosting, or a production storage provider.

## Ownership and dependencies

Hamsa's `core` migration establishes users, client profiles, projects, orders, plans, services, payments, files, versions, revisions, influencer packages, and subscriptions. `subscriptions` is the canonical table name for purchased package/subscription records; `influencer_packages` is the catalog.

Dheeraj's `operations` migration depends on core and creates editors, admins, proficiency, availability, complexity, assignments, queue/pointer state, calls, notifications, wallets/ledger/redemptions, and audit logs. A second operations migration seeds the three specified proficiency groups and their durable pointer records. There is no allocation worker yet.

Additional infrastructure tables hold upload policy, login throttling, and Django sessions/auth metadata. Pending business fields are nullable or inactive rather than filled with fictitious values. Models are schema foundations; they do not by themselves implement payment, revision, package, or wallet workflows.

## Authentication and permissions

1. Passwords are validated and hashed through Django. Sessions are stored in the database and the browser receives an HTTP-only, SameSite cookie.
2. `role_required` checks the authenticated identity and role on every protected page/API.
3. `visible_projects` scopes clients to their own projects and editors to current assignments with approved profiles. Admins access the operational project set.
4. `project_for` uses that scoped query before exposing a project or allowing a file operation. Unknown/unauthorized projects return 404.
5. Public signup rejects privilege fields; only the protected admin action can approve editor proficiency. A CLI creates initial admins and refuses silent elevation of existing accounts.
6. POST mutations require CSRF. Logout deletes the database session. Private routes return `Cache-Control: no-store` and indexing restrictions.
7. Login/signup attempt counts are persisted per hashed direct client IP with a local 30-attempt / 15-minute limit. Proxy-aware distributed throttling, password recovery, MFA, and email verification remain production hardening work.

An unapproved editor may log in and change availability. This grants no project access or assignment eligibility. Manual fixture assignments exist only in tests; no unpaid-work assignment endpoint is exposed.

## File API contract

| Endpoint | Authorization | Result |
| --- | --- | --- |
| `POST /api/projects/<id>/uploads/` | Owning client or eligible assigned editor; allowed file category | Reserved file ID and scoped temporary PUT permission |
| `POST /api/files/<id>/complete/` | Same uploader with current project/upload access | Verified ready file ID, or an error |
| `POST /api/files/<id>/download/` | Owner, currently assigned approved editor, or admin | Temporary GET URL for the stored original version |
| `GET /api/projects/<id>/` | Project-scoped | Safe project/file metadata without object keys |
| `GET /api/areas/<role>/` | Matching role | Scoped project list |

Upload metadata includes filename, byte size, content type, category, and SHA-256. The backend validates configured extension/type mapping, size, checksum syntax, filename, category, and project relationship. The signed PUT binds content type, length, checksum, and `If-None-Match: *`; the storage service verifies those conditions.

Completion checks storage-reported size, content type, SHA-256, and a non-null version ID. Only then does the file become ready. Incomplete, expired, or integrity-failed reservations are not exposed as usable files. Repeated successful completion is idempotent. Every accepted original has its own random object key; replay cannot replace it. Signed downloads target the persisted storage version explicitly.

The local technical defaults are 15-minute upload permission and 60-second download permission. A previously issued download link remains usable until expiry, even if assignment changes; fresh authorization checks deny the former editor immediately. These are bearer links and must never be logged or published. Immediate revocation would require a different serving strategy.

## Storage boundaries

- The bucket has no public access policy; unsigned listing and object reads fail.
- Internal file HTTP reads/writes use signed JWT checks. Local internal RPC services bind to loopback only and belong to the trusted development machine boundary.
- The bootstrap S3 identity is a local service credential, never sent to the browser. Production needs least-privilege IAM, private networking, encryption/HTTPS, backups, and lifecycle decisions.
- The app does not expose a media/static mapping to stored client files. Downloads force attachment/octet-stream; untrusted media is not rendered inline.
- File validation checks declared type against the allowed extension and verified object metadata. Deep codec/file-signature inspection, malware scanning/quarantine, and abuse quotas are **not implemented**. They remain production work.
- Direct single-object upload and retry work. Resumable/multipart browser uploads, previews, and background scanning remain later work; the integration tests exercised files over 5 MiB, not the entire configured 512 MiB limit.
- `.runtime/` contains local secrets and synthetic development objects; do not place real client files in this development environment. Filesystem/OneDrive access is outside application authorization.

## Implemented versus deferred

Working: client/editor registration, login/logout, role-scoped dashboards and project data, admin editor review, availability changes, client project drafts, original upload/download, audit events, and empty payment history.

Schema/skeleton only: checkout/payment confirmation, plan editing/pricing, consultation scheduling, AI classification, assignment/round-robin processing, client revision/approval workflows, version publishing, packages, coin credit/redemption, operational notifications, and analytics. No payment-success or coin-credit simulation is exposed as a working business feature.

## Reference documentation

- [Django custom authentication](https://docs.djangoproject.com/en/5.2/topics/auth/customizing/)
- [S3 PutObject checksum and conditional-write API](https://docs.aws.amazon.com/boto3/latest/reference/services/s3/client/put_object.html)
- [SeaweedFS source and releases](https://github.com/seaweedfs/seaweedfs)

The tested dependency versions are recorded in `requirements.lock.txt` and `package-lock.json`.
