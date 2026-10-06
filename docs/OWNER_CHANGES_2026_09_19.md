# Owner-requested account and order changes — 2026-09-19

Status: requested interface changes are implemented. Production commercial activation still depends on the owner decisions listed below.

## Verified in the first milestone

- Passwords require at least 8 characters with uppercase, lowercase, numeric and special characters.
- Password inputs include an accessible Show/Hide control.
- Public editor application is disabled. Administrators issue an editor ID and initial password with `python manage.py create_editor`; the editor workspace has no password-change route.
- The client account page no longer links to an editor application.
- Authenticated workspaces include a Back control with a same-origin history check and dashboard fallback.
- Client copy uses “Plan a new edit” instead of “Start a project.”
- Raw/source uploads and inspiration-video uploads use distinct private controls and retain distinct file categories.
- Music preference removes the duplicate “already have a song” option and adds a combined provide-a-song plus editor-suggestions option.
- The new-edit screen warns clients to upload only content they may share and to omit passwords/unrelated personal documents.
- New client accounts remain inactive until a six digit email OTP is consumed. The original 2026-09-27 implementation stored hashed challenges in the private application schema. The 2026-10-06 owner change delegates new client OTP generation, delivery and validation to Supabase Auth while preserving the existing VedioOS user/profile, session, role and editor-ID behavior. Resend responses remain non-enumerating.
- The new-edit screen presents three administrator-configured plan slots and a fourth custom option. Unpublished slots are clearly unavailable.
- Custom briefs persist colour grading, quality enhancement, four reel-duration bands, wording yes/no and conditional font direction. Font-inspiration uploads use a separate private category and require that choice on the saved project.
- Active monthly creator packages appear in a separate section; sales remain closed until D13 terms are approved.
- Administrators can create and edit validated monthly-package drafts. The UI cannot publish them, so unfinished renewal and quota rules cannot accidentally open package sales.

## Next implementation milestones

- Configure approved custom base/service prices and publish quote terms. The server-authoritative live estimate is implemented; model pricing remains disabled until the owner supplies approved training examples, target outputs and evaluation tolerances. D03, D04 and D08 remain open.
- Monthly plan publication, purchase and usage behavior after D13 defines allowances, renewal, expiry, rollover and dedicated-editor interactions.

## Verification evidence

- The isolated suite passes 113 tests with 10 opt-in integrations skipped.
- The opt-in Edge walkthrough verifies password visibility, keyboard navigation, separate inspiration upload, retry behavior and byte-identical original download at mobile sizes.
- Additive migrations `core.0004`, `operations.0010` and `operations.0011` were applied to the selected private Supabase schema after snapshot `database-snapshot-20260919T144401311067Z.json`. Existing editors received unique IDs; all 43 tables retain RLS and browser roles retain no schema access.
- Additive migration `core.0005` was applied after snapshot `database-snapshot-20260919T145513651931Z.json`; the new verification timestamp is present and all private-schema access checks continue to pass.
- Additive migration `core.0006` was applied after snapshot `database-snapshot-20260919T152202844758Z.json`; project customization columns and the font-reference category are present. All 43 tables retain RLS and browser roles retain no schema access.
- Additive migration `core.0007` was applied after snapshot `database-snapshot-20260923T194410855257Z.json`; custom-service mapping codes are present and unique when configured. No production prices or mappings were inserted. All 43 tables retain RLS and browser roles retain no schema access.
- Additive migration `operations.0012` was applied after snapshot `database-snapshot-20260923T200315654878Z.json`; the durable email-delivery outbox and due-work index are present. Existing notices would be held rather than sent; the shared database had no notices to backfill. All 44 tables retain RLS and browser roles retain no schema access. Email delivery remains disabled.

## Creative-brief form continuity — 2026-09-27

- After **Save and Proceed**, the active unpaid draft is retained in the authenticated session and reopening **Plan a new edit** repopulates every saved field.
- **Create New** is the explicit blank-form action; it does not overwrite the prior draft.
- The project’s **Creative Brief** summary offers **Edit** to its owning client while the draft remains unpaid and no quote agreement has been accepted. Saving updates the same project and records an attributable audit event.
- Ownership is enforced by the backend. Other clients cannot open the edit route, and paid or commercially accepted orders cannot be changed through it.
- This is a code-only behavior change and requires no database migration or Supabase schema synchronization.

## Font and inspiration inputs — 2026-09-27

- The custom-order field is presented as **Font selection**. Choosing **I have my own font** requires a persisted font style/name; choosing **I will upload font inspiration** enables a separate private image upload after the draft is saved.
- Font-inspiration uploads accept one image smaller than 1 MB. Document/PDF files and non-image media are rejected by the backend as well as filtered by the browser picker.
- The free-text inspiration/reference-notes control is removed from the order form and summary. Its historical database column is retained so existing data is not destroyed.
- The separate **Add Inspiration Reel/Video** uploader accepts multiple formats and enforces a maximum of three active uploads per project. The limit is serialized on the project row to prevent concurrent requests bypassing it.
- The edit-description label is now **Describe the edit**.
- Additive migration `core.0008` stores the optional font name on project drafts. It was applied to the selected Supabase project on 2026-09-27 after recording the pre-change schema/migration/security state: two existing project rows, no pre-existing column or migration record, RLS enabled, and no browser-role schema access. Post-change checks confirm the 120-character non-null column with no database default, the matching Django migration record, unchanged RLS, and unchanged browser-role isolation.

## Creative-brief upload persistence — 2026-09-29

- **Save and Proceed** now waits for every selected original to receive its upload reservation, reach private object storage, and pass the backend completion/integrity check before navigation.
- Before leaving the form, the browser fetches the saved project and confirms every completed file ID is present in the project file metadata. A failed or unconfirmed upload keeps the client on the same saved draft and displays an error instead of silently continuing.
- After the draft is first saved, retries use that project's edit route. Files that completed successfully are removed from the pending browser queue, preventing successful originals from being submitted twice when a later file fails.
- Reopening or editing the creative brief displays its existing ready source, image, audio, inspiration, font-inspiration and other-asset uploads. The Project Files section continues to use the same project-scoped, authorization-filtered ready-file query.
- Regression coverage verifies multiple formats, files added during a later edit, project isolation and single rendering. A browser walkthrough verified MP4, PDF, MOV and WEBP originals through the real private-storage upload and completion APIs.
- This is a code-only behavior change and requires no database migration or Supabase schema synchronization.

## Fixed-plan pricing periods — 2026-09-29

- The new-order plan selector presents **Per Reel**, **Monthly** and **Yearly** as a single-select segmented control above the three fixed plan cards. Per Reel is the default for new drafts.
- Each published plan resolves its displayed amount from administrator-managed per-reel, monthly and yearly minor-unit fields. A missing amount displays **Coming soon** and disables only that plan/period combination.
- The Custom card and its customization form do not change with the selector. Custom drafts normalize to Per Reel because recurring custom-order policy was not requested or approved.
- Plan drafts persist the chosen pricing period. Reopening the brief restores it, and server-generated quotes use and snapshot the matching catalog amount instead of trusting a browser-supplied price.
- Monthly creator packages remain separate and unavailable for purchase until D13 defines their fulfillment and renewal policies. No commercial amount is seeded by the migration.
- Additive migration `core.0011` adds the two optional plan amounts and the order pricing-period choice. It passed the isolated migration/tests and is applied to the local preview. Synchronization to the selected Supabase project remains pending because this workspace currently has no server-only PostgreSQL connection configuration.
