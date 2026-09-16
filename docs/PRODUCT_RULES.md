# Product requirements and restrictions

## 1. Interpretation

**MUST/MUST NOT** indicate required behavior. **Proposed** identifies implementation guidance awaiting a policy decision, not an owner-approved business term. The [original brief](ORIGINAL_BRIEF.md) remains the complete scope reference. Items in [DECISIONS.md](DECISIONS.md) are deliberately unresolved.

## 2. Product and experience

VedioOS MUST manage human editing, not perform automatic editing. AI is limited to internal complexity classification and assignment support. Editors download files and use their own tools.

The landing page must clearly explain the service to creators, influencers, students, businesses, personal brands, and first-time editing clients. Use a modern, premium, creative visual style, strong hierarchy, thumbnails, project cards, progress, and status badges. Clients need a mobile-first experience; editor/admin dashboards remain responsive with desktop-oriented workflows.

Landing-page scope includes hero, how it works, services, plans, custom orders, influencer packages, benefits, 24-hour delivery, revision support, consultations, FAQ, CTA, and footer. Testimonials must use approved real content or visibly labeled demo content during development. Display delivery and revision claims consistently with configured terms.

## 3. Identity and permissions

| Capability | Client | Editor | Authorized admin/presenter |
| --- | --- | --- | --- |
| Project details and media | Own projects | Currently assigned projects | Within granted permissions |
| Submit requirements/order | Own orders | No | Support actions with audit trail |
| Upload edit versions | No | Assigned projects | Only under explicit operational permission |
| Request revision/accept | Own projects | No | No silent client impersonation |
| Set price/proficiency/assignment | No | No | Yes |
| Earnings | No internal editor data | Own wallet | Manage under permissions |
| AI classification/internal notes | No | Only information needed for assigned work | View and override |

Editor signup collects name, email, phone, credentials, experience, tools, portfolio, samples, expertise, and availability. Admin review determines approval and Beginner/Intermediate/Advanced proficiency. Self-declared proficiency MUST NOT grant assignment eligibility. Admins may revise proficiency with an audit trail.

All protected operations MUST enforce backend role and project authorization, including metadata, messages, notifications, previews, download links, and uploads. Role creation and elevation must be privileged. Initially support two individually authenticated managers, not a shared password.

## 4. Ordering and configuration

The client flow MUST support multiple source videos, images, audio, references, other assets, progress, and configurable type/size validation. Capture reference explanations and free-text requirements.

Selectable requirements cover color grading, quality enhancement, transitions, effects, captions, cuts, text, graphics, slow motion, speed ramps, cinematic treatment, audio enhancement, background music, and other requirements. Admins control availability and pricing.

Song choices support providing/uploading a song, specifying an existing song, or asking the editor for a suggestion. Explain that the team recommends the song; this is not automatic editing.

Support exactly three offered predefined plans with configurable names, prices, features, revision counts, delivery terms, duration limits, priority, and included services. Custom orders use **base price + selected service prices**; calculate authoritative totals on the backend and display the breakdown before payment. Define handling of unpriced “Other” requests before enabling them for checkout.

Snapshot purchased plan/service details, prices, currency, revision allowance, delivery policy, and earning-rule version on an order. Configuration changes apply prospectively unless an explicit audited adjustment is made. Missing required configuration blocks the affected commercial action with a useful explanation.

## 5. Payment and order activation

A pre-payment checkout/draft may exist to hold uploads and requirements. It is not an active editing job. Confirmed payment activates/creates exactly one uniquely identified paid order/project, records payment details and confirmation time, and makes it available for assignment.

The actual gateway is undecided. Backend verification of the provider's payment result MUST be authoritative; a browser redirect alone is insufficient. Match payment to order, amount, and currency. Handle retries, duplicate/out-of-order events, failures, and reconciliation without duplicate fulfillment. No editor assignment or editing begins before confirmation. Refund and cancellation financial effects require a recorded policy.

## 6. Project lifecycle

Persist payment state separately from project fulfillment state, while presenting the brief's labels and history clearly:

| Label | Meaning / transition guard |
| --- | --- |
| Payment Pending | Checkout awaits verified payment; no assignment |
| Payment Completed | Payment confirmed and recorded |
| Awaiting Editor Assignment | Paid project queued for allocation |
| Editor Assigned | Eligible editor assigned and capacity reserved |
| Editing in Progress | Assigned editor starts work |
| Draft Uploaded | A complete, validated, immutable version exists |
| Awaiting Client Review | A specific version was submitted; client notified |
| Revision Requested | Client submits instructions against a reviewed version under revision policy |
| Revision in Progress | Assigned editor starts the revision |
| Final Video Uploaded | A version is designated as a final candidate; not automatic acceptance |
| Completed | Client accepted a specific deliverable; fulfillment and earning event recorded |
| Cancelled | Authorized cancellation under configured policy |

Normal flow: payment → queue → assignment → editing → upload → review. Review branches to revision → new upload → review, or acceptance → completed. A client may accept the reviewed draft and designate that existing version final; do not require a duplicate upload. An editor calling a file “final” must not complete the project or earn coins by itself.

Centralize and enforce allowed transitions on the backend. Record actor, time, previous/new state, and related version. Reject invalid/stale transitions. Completion/cancellation are terminal unless a later explicit policy defines reopening. Reassignment preserves project history and deadline.

## 7. Delivery deadlines

The target service promise is delivery within 24 hours. Persist order creation, payment confirmation, expected delivery, and status. Show countdowns and due-soon/on-time/overdue indicators to admin and editor, with useful client progress.

The clock start, timezone/calendar treatment, revision effects, consultation pauses, plan overrides, due-soon threshold, and meaning of “delivered” remain undecided. Do not silently choose them for production. Assignment delays or restarts MUST NOT silently reset the persisted deadline. Document and audit authorized deadline changes.

## 8. Complexity and assignment

AI outputs Beginner, Intermediate, or Advanced complexity from requirements, reference information, duration, clip count, effects, grading, audio, and other relevant metadata. Store classification, rule/model version, and useful internal explanation. Admins can review and override it with history. Keep sensitive internals away from clients. Do not send private raw media to AI providers by default; any such data flow requires a documented decision consistent with file privacy.

Beginner work includes basic cuts, transitions, trimming, text, music sync, and minor adjustments. Intermediate includes detailed synchronization, graphics, moderate grading, and multiple effects. Advanced includes cinematic storytelling, complex effects/motion graphics, advanced grading, and demanding combinations. Criteria are configurable.

Only approved editors meeting configured proficiency, availability, and capacity rules are eligible. Maintain availability values Available, Busy, Offline, On Leave, and Temporarily Unavailable, plus visible active-project counts and configurable capacities.

Round-robin MUST use durable, separate state per proficiency group. Selection, capacity reservation, assignment, and pointer advancement must be atomic or equivalently protected against concurrent workers. Finishing a project, logging in, or restarting the server MUST NOT reset the pointer.

Example: assignments to E1 and E2 are followed by E3 even if E1 becomes free. After a complete cycle, wrap to E1 if eligible. Configure either waiting for the next occupied editor or skipping to the next eligible available editor. Persist waiting projects. Do not silently substitute “first available.”

Admins can assign/reassign and override classification. Record actor, reason, old/new assignee, capacity consequences, and any effect on the pointer. Define cross-level fallback, manual-assignment pointer behavior, roster changes, and occupied-state semantics in the decision log before automatic assignment is enabled. AI failure should leave a visible review/queue path rather than inventing a classification.

## 9. Files: integrity and privacy

- Preserve every original source and editor upload byte-for-byte, including its original media properties. Verify integrity with a content checksum or equivalent end-to-end mechanism.
- Store previews/thumbnails as distinct derivatives linked to their originals. Browser playback limitations must not alter the original; provide authorized original downloads.
- Use private object storage or equivalent protection. Prefer direct/resumable/multipart uploads for large media; avoid routing whole videos through the app unnecessarily.
- Authorize initiation, upload completion, metadata access, previews, and downloads. Validate declared and actual object ownership, type, size, and completion. Prevent users from attaching another project's object.
- Use short-lived authorized access or an authenticated streaming mechanism. Never expose permanent public file URLs. Redact signed links from logs.
- Reassignment removes the former editor's future access. Already-issued signed links may remain valid until expiry; choose TTL/proxy/revocation behavior explicitly and never claim instant revocation without enforcing it.
- Maintain separate client files (sources/images/audio/references/assets) and editor files (drafts/revisions/final). New versions use new records/objects; never overwrite history.
- Validate and safely handle risky uploads, with scanning/quarantine where appropriate. Do not release incomplete or rejected objects as accepted project media.
- Record file access and uploads in protected audit records. Retention, deletion, backups, and link expiry require explicit policies; no automatic original deletion to reduce cost.

Quality preservation takes priority over storage/bandwidth savings. Test both client sources and editor deliverables, including a preview generated from an unchanged original.

## 10. Review, communication, and calls

Clients can preview authorized versions, submit detailed/time-referenced revision instructions, and accept a particular version. Keep each revision and deliverable separately. Enforce purchased revision terms on the backend; handling excess revisions remains a business decision. Support project-scoped communication and distinguish client-visible messages from internal notes.

Checkout supports before-editing and after-draft consultation requests. Admins see, assign, schedule, and mark calls complete. Built-in calling technology can follow later; request management is still required. Consultation blocking/deadline effects need a policy.

## 11. Coins and payouts

Acceptance triggers one earning credit under the project's earning rules. Pending earnings are separate from earned/redeemable balances. Maintain an auditable transaction ledger, not an editable balance alone. Repeated acceptance or event retries MUST NOT duplicate credits.

The editor wallet shows total earned, pending, redeemable, redeemed, redemption requests/history, and transaction history. Admins manage earning settings and payout requests. Reserve funds/coins during redemption so simultaneous requests cannot spend the same balance. Record payout outcomes and use compensating ledger entries for corrections.

Coin conversion, precision, eligibility, payout provider, reassignment earning split, and refund/cancellation effects are undecided. Disable real redemption until configured; do not imply a monetary value for demo coins.

## 12. Notifications, audit, and administration

Notify clients of payment, assignment, editing start, draft, revision submission, final availability, completion, and call updates. Notify editors of assignment, approaching deadline, revision, acceptance, and coin credit. Notify admins of new orders/payments, unassigned work, deadlines, revisions, calls, and completion. Persist notifications with authorization and retry/deduplication behavior; choose external channels later.

Admin operations cover clients/users/editors, all order queues, requirements/files/payments, assignment, deadlines, support/calls, plans/services/packages, coin settings/payouts, feature flags, and analytics. Audit uploads/downloads, payment confirmation, transitions, assignment/reassignment, revisions, acceptance, credits/redemption, configuration, proficiency, and AI overrides. Audit logs should identify actor, target, timestamp, and change without leaking sensitive content.

Analytics scope: total/active/completed/pending orders, revenue, daily/monthly orders, average delivery, revision rate, active editors/workload, pending payouts, packages, and retention. Define metric formulas, financial inclusion rules, and reporting timezone before presenting production numbers.

## 13. Recurring creator packages

Support configurable monthly packages with video/reel allowances, revisions, priority, dedicated editor, and additional services. Names/prices, renewal behavior, expiry, rollover, quota accounting, and dedicated-editor conflicts with round-robin need decisions. Do not advertise purchase availability until fulfillment and payment/accounting are implemented.

## 14. Backend data responsibilities

Design related records for users/roles, clients, approved editor profiles/proficiency/availability, admins, checkout/orders/projects, plans/services and snapshots, payments/events, files/derivatives, versions, revisions, assignments/history, complexity/overrides, durable queues/per-level pointers, calls/messages, packages/subscriptions/allowance usage, notifications, coin ledger/redemptions, configuration, and audit logs.

Use stable identifiers, ownership relationships, referential constraints, timestamps, and appropriate transactions. A restart must not lose queues, pointers, payment processing state, version history, or financial records. Technology and deployment choices are not yet prescribed.
