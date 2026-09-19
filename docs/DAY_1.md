# Day 1 — Foundation, database, authentication, and basic UI

> Scope update (2026-09-19): the owner replaced public editor self-registration with administrator-issued editor IDs and initial passwords. The original Day 1 responsibilities below are preserved as historical milestone context; current behavior is recorded in [DECISIONS.md](DECISIONS.md) and the [README](../README.md).

**Status: implemented and verified locally on 2026-09-15. See [Day 1 verification](DAY_1_VERIFICATION.md) for evidence and production limitations.**

This is the immediate delivery milestone. It covers foundation work across roadmap Phases 1–2 and creates schema/UI foundations for later phases. Creating a table or navigation skeleton does not complete its future business workflow.

## Ownership

| Person | Owner | Responsibility |
| --- | --- | --- |
| Person 1 | Hamsa | Client experience, core schema, shared authentication, private file foundation |
| Person 2 | Dheeraj | Operational schema, editor registration/profile, protected admin/editor layouts |
| Both | Hamsa + Dheeraj | Shared contracts, migration integration, permissions, end-of-day proof |

## Hamsa — Client and core platform

### H1. Core database

Create migrations/models for:

- `users`
- `clients`
- `projects`
- `orders`
- `plans`
- `custom_services`
- `payments`
- `files`
- `project_versions`
- `revision_requests`
- `influencer_packages`
- subscriptions/package purchases (agree on the physical table naming before migration)

Use `users` as the common authentication identity. Client/editor/admin records reference that identity; do not create three independent credential systems. Roles determine access. Link client-owned projects/orders and project-owned files/versions/revisions with enforced relationships.

Pre-payment project/order drafts may hold client uploads. They must remain unpaid and ineligible for editing/assignment. Plan/payment/package schemas are foundations only; do not invent commercial terms or implement payment success as a mock production action.

### H2. Shared authentication

Implement registration, login, logout, authenticated sessions/tokens, role checking, and server-side route protection. Supply the shared auth interface used by Dheeraj's editor registration and layouts.

- Public registration may create a client or an editor applicant through the appropriate flow, never an admin.
- Store credentials using the selected auth system securely; do not duplicate passwords in profiles.
- Reject unauthorized backend requests even when made directly without the UI.
- Protect project operations by ownership/current assignment in addition to role.
- Provide a controlled admin provisioning process and prove admin login without publishing credentials.
- Logout must invalidate the session according to the chosen auth mechanism.

### H3. Private storage foundation

Upload flow:

1. Authenticate the user and authorize upload to the specific project/draft.
2. Validate upload type, size, category, and ownership; issue narrowly scoped temporary upload permission.
3. Upload directly/stream to private storage, avoiding application-server transit unless necessary.
4. Verify completion and actual stored object metadata/integrity on the backend.
5. Save finalized file metadata and return the file ID. An upload reservation is not a completed file.

Download flow:

1. Receive a file-ID request.
2. Verify authentication, role, and access to the file's project.
3. Issue temporary/signed access to the authorized object.

Keep storage private. No permanent public URLs, original compression, original replacement, or unnecessary media processing. Use separate derivative objects if previews are introduced. Record private object identifiers, byte size, content type, owner/uploader, project, completion status, and integrity information; do not use a permanent public URL as the file record.

### H4. Client-facing base UI

Create Landing Page, Register, Login, Client Dashboard, New Order, My Projects, Project Details, and Payment History.

Use honest empty states for unimplemented transactions/features. Protect client data on the backend. New Order should support the draft and private-upload foundation needed for the Day 1 proof.

The landing page may contain only the requested sections: Hero, How It Works, Editing Services, Plans, Custom Editing, Influencer Packages, Why Choose Us, 24-hour Delivery, Revision Support, Editor Consultation, Testimonials, FAQ, CTA, and Footer. Do not add unrelated marketing pages or fabricate testimonials/prices.

## Dheeraj — Admin and editor operations

### D1. Operational database

Create migrations/models for:

- `editors`
- `admins`
- `editor_proficiency`
- `editor_availability`
- `project_complexity`
- `editor_assignments`
- `assignment_queue`
- `round_robin_state`
- `call_requests`
- `notifications`
- `editor_coins`
- `coin_transactions`
- `redemption_requests`
- `audit_logs`

Reference the shared `users` and Hamsa's project identities. Ensure operational records have appropriate ownership, foreign keys, and access boundaries. Prepare persistent per-proficiency round-robin state, but do not implement complex allocation before the Day 1 gate passes. Wallet and payout schemas must not imply approved earning or conversion rules.

### D2. Editor registration

Build the editor registration form and profile persistence using shared authentication. Collect:

- Name, email, phone, and password through the auth flow.
- Editing experience and software/tools.
- Portfolio and previous work samples.
- Areas of expertise and availability.
- Other relevant information.

Editors may submit experience but cannot approve themselves or set an authoritative proficiency. Admin determines Beginner, Intermediate, or Advanced. New applicants can log in to a limited editor dashboard; they remain unapproved and ineligible for assignments. Reject forged approval/proficiency updates on the backend.

### D3. Protected layouts and navigation

| Admin navigation | Editor navigation |
| --- | --- |
| Overview | Assigned Projects |
| Orders | Project Details |
| Projects | Revisions |
| Editors | Wallet |
| Clients | Availability |
| Assignments | |
| Plans/Pricing | |
| Calls | |
| Payouts | |
| Analytics | |

Skeletons are sufficient for these operational screens. All layouts/routes and their data endpoints must enforce roles on the server. An editor project detail view must enforce current assignment. Skeletons must show empty/not-yet-available states rather than fabricated operational records.

## Shared integration contract

Agree before overlapping implementation:

- Stack/auth provider and private storage configuration: record D01 and relevant D02 choices in [DECISIONS.md](DECISIONS.md).
- Canonical user ID, role representation, profile references, and editor approval state.
- Project ownership and assignment relationship used by the common authorization check.
- Shared session lookup, role guard, and project-access functions; avoid separate conflicting checks in each dashboard.
- File permission/completion/download request and response shapes, validation errors, and link-expiry behavior.
- One migration history with non-conflicting migration names. Merge core identity/project migrations before dependent operational migrations; resolve cycles explicitly.
- Admin bootstrap and synthetic client/editor/project fixtures for verification.

Hamsa owns changes to shared auth and core schema; Dheeraj coordinates any required changes to those interfaces. Each owner keeps their schema/UI changes focused. Review integration changes together before claiming the combined milestone works.

## Suggested execution order

1. **Together:** agree on shared contracts, stack, migrations, and environment setup.
2. **Hamsa:** identity/core schema and auth. **Dheeraj:** operational schema against those agreed identities and editor form/layout structure.
3. **Hamsa:** project drafts, private media flow, client screens. **Dheeraj:** connect editor registration and operational route guards to shared auth.
4. **Together:** apply the combined migrations to an empty database; provision an admin; verify all role and file flows.
5. Fix failures and record evidence. Only then proceed to complex assignment logic.

## End-of-Day 1 mandatory gate

All mandatory checks below **passed locally**. The [verification report](DAY_1_VERIFICATION.md) records the test suites, browser walkthrough, and practical limits. Screenshots alone do not prove backend security.

| Check | Expected proof | Owner | Result |
| --- | --- | --- | --- |
| Client registration/login | New client identity/profile persists and authenticated dashboard loads | Hamsa | Pass — local |
| Editor registration/login | Applicant profile persists and editor dashboard loads without self-approval | Dheeraj | Pass — local |
| Admin login | Privileged provisioned account signs in; no public admin signup | Both | Pass — local |
| Logout/session protection | Logged-out or missing-session protected requests fail | Hamsa | Pass — local |
| Client role isolation | Direct editor/admin route and API requests are rejected | Both | Pass — local |
| Editor role isolation | Client/admin areas and unassigned project requests are rejected | Both | Pass — local |
| Cross-client isolation | Client A cannot read/write Client B's project or file metadata | Hamsa | Pass — local |
| No editor self-approval | Forged role/proficiency/approval requests are rejected | Dheeraj | Pass — local |
| Migrations | Complete migration chain applies to an empty database with relationships intact | Both | Pass — local |
| Private upload | Authorized direct upload completes; metadata/file ID persists; object is private | Hamsa | Pass — local |
| Original integrity | Authorized original download matches the upload's checksum/bytes | Hamsa | Pass — local |
| Unauthorized download | Anonymous, other-client, and unassigned-editor file requests fail; bucket is not public | Both | Pass — local |
| Temporary access | Authorized download works and temporary permission expires as configured | Hamsa | Pass — local |
| Three dashboards | Client, editor, and admin layouts load for correct roles | Both | Pass — local |

**STOP GATE: Do not continue to complex assignment logic until every mandatory check passes.** Table creation alone does not authorize AI assignment, queue workers, payouts, or real payment processing. Existing payment-before-editing and privacy rules remain in force.

## Evidence and handoff

For each completed task, record implementation files/commit, migration name, verified commands/steps, results, and remaining limitations. Never mark the gate passed with missing credentials, mocked storage, or unexecuted security checks.

```text
Task ID / owner:
Status:
Implementation files / commit:
Migration(s):
Checks and actual results:
Environment used (no credentials):
Known limitations / next handoff:
```
