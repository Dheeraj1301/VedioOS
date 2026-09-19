# Owner-requested account and order changes — 2026-09-19

Status: in progress. Complete these changes before advancing the roadmap phase.

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
- New client accounts remain inactive until an expiring email-verification link is opened. Resend is rate-limited and non-enumerating; delivery uses a replaceable email backend.
- The new-edit screen presents three administrator-configured plan slots and a fourth custom option. Unpublished slots are clearly unavailable.
- Custom briefs persist colour grading, quality enhancement, four reel-duration bands, wording yes/no and conditional font direction. Font-inspiration uploads use a separate private category and require that choice on the saved project.
- Active monthly creator packages appear in a separate section; sales remain closed until D13 terms are approved.

## Next implementation milestones

- Server-authoritative custom estimates based on administrator-configured prices. A trained pricing model remains disabled until the owner supplies approved training examples, price outputs and evaluation tolerances; D03, D04 and D08 remain open.
- Monthly plan configuration and sales behavior after D13 defines allowances, renewal, expiry, rollover and dedicated-editor interactions.

## Verification evidence

- The isolated suite passes 106 tests with 10 opt-in integrations skipped.
- The opt-in Edge walkthrough verifies password visibility, keyboard navigation, separate inspiration upload, retry behavior and byte-identical original download at mobile sizes.
- Additive migrations `core.0004`, `operations.0010` and `operations.0011` were applied to the selected private Supabase schema after snapshot `database-snapshot-20260919T144401311067Z.json`. Existing editors received unique IDs; all 43 tables retain RLS and browser roles retain no schema access.
- Additive migration `core.0005` was applied after snapshot `database-snapshot-20260919T145513651931Z.json`; the new verification timestamp is present and all private-schema access checks continue to pass.
- Additive migration `core.0006` was applied after snapshot `database-snapshot-20260919T152202844758Z.json`; project customization columns and the font-reference category are present. All 43 tables retain RLS and browser roles retain no schema access.
