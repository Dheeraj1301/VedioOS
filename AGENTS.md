# Contributor and coding-agent instructions

These instructions apply throughout this repository.

## Required context

Read `README.md`, `docs/PRODUCT_RULES.md`, `docs/ROADMAP.md`, and `docs/DECISIONS.md` before implementation. Consult relevant sections of `docs/ORIGINAL_BRIEF.md` for full detail. Preserve the source brief; record later decisions separately.

Read `docs/DAY_1.md` for the immediate milestone. Hamsa (Person 1) owns Client + Core Platform; Dheeraj (Person 2) owns Admin + Editor Operations. Coordinate shared schema/auth contracts and migration order. Do not implement complex assignment logic until every Day 1 mandatory check has recorded passing evidence. Operational table/layout scaffolding is allowed before that gate.

## Working process

1. Identify the requested feature, its original brief section(s), and its roadmap phase.
2. Inspect existing implementation and repository instructions before changing code.
3. Check unresolved decisions. Continue independent work; ask the owner only for choices that materially block the requested behavior. Do not silently invent production policy.
4. Implement the smallest complete slice, including backend validation, authorization, persistence, user-facing states, and meaningful verification.
5. Keep business configuration in validated, persisted admin-managed settings. Snapshot applicable commercial terms on orders so future changes do not rewrite existing agreements.
6. Run checks appropriate to the change. Test critical behavior and failure cases, not just implementation details. Explain anything unverified.
7. Update affected docs and roadmap evidence. Mark a phase complete only after its gate passes.
8. Summarize what changed, why, verification, and remaining limitations. Never describe mocks or placeholders as completed integrations.

## Restrictions

- Do not build automatic editing, AI-generated client deliverables, a public editor marketplace, or bidding workflows without an explicit scope change.
- Do not compress, transcode, resize, or overwrite stored originals. Derivatives must have distinct storage objects and metadata.
- Do not expose project files through public buckets, public asset folders, permanent public URLs, logs, or analytics payloads.
- Do not rely on hidden UI controls for authorization. Check roles and project relationships on every protected backend operation.
- Do not trust client-supplied prices, role claims, payment-success redirects, proficiency claims, wallet balances, or project ownership.
- Do not assign unpaid projects, reset allocation pointers on availability changes/restarts, or exceed capacity through races.
- Do not credit coins before acceptance or allow repeated callbacks/requests to duplicate orders, assignments, or earnings.
- Do not hard-code unresolved commercial values or enable real checkout/redemption using demo settings.
- Do not add unrelated infrastructure, providers, major features, or abstractions without a demonstrated requirement.
- Do not commit secrets or real client media. Use synthetic fixtures for tests.

## Engineering expectations

- Keep payment, storage, AI classification, and notification integrations replaceable. Select the actual stack through the decision record; no provider is mandated yet.
- Use durable state, transactional constraints, idempotency, and retry-safe jobs for money, assignment, acceptance, and notifications.
- Keep money in integer minor units with explicit currency; avoid floating-point financial calculations. Define coin precision when its policy is decided.
- Keep timestamps in UTC; display local time and compute deadlines from persisted policy.
- Keep audit events attributable and protected from ordinary-user edits; omit secrets and signed URLs.
- Provide loading, empty, error, retry, and permission-denied states. Support mobile client uploads and responsive dashboards.
- Use migrations for schema changes. Document environment requirements and recovery procedures as infrastructure is added.
- Use feature flags for unfinished integrations; disabled features must not bypass security or payment gates.

## Required verification when relevant

- Cross-client, unassigned-editor, former-editor, and unauthenticated access denial for APIs and files.
- Upload/download byte integrity; distinct previews; immutable version history.
- Payment verification, duplicate events, failed payments, and server-calculated totals.
- Persistent and concurrent round-robin assignment, unavailable editors, capacity, and overrides.
- Valid state transitions, revision limits, acceptance of an explicit version, and exactly-once coin credit.
- Wallet/redemption consistency, configuration snapshots, and notification retry behavior.

Follow explicit user authorization for Git publishing and deployment. Writing these instructions does not itself request a push, deployment, or production configuration change.

## Owner workflow updates — 2026-09-16

- The owner explicitly requests committing and pushing every completed major change to `origin` so the team can pull live development updates. Run relevant checks, inspect staged files, exclude credentials/local data, and push the working branch after each verified milestone. Do not force-push or overwrite teammates' work. Report the branch and commit; disclose push failures. This is ongoing authorization for Git publishing, not production deployment.
- Tell the owner before a paid subscription or upgrade is needed. Do not purchase subscriptions or upgrade services without explicit authorization.
- Keep the selected Supabase project `lmwvoniiykmfzuxigzqf` synchronized with every completed database-affecting change. This is explicit ongoing authorization to apply reviewed, tested, non-destructive Django migrations to the private `vedioos` schema without asking again. Inspect pending migrations and preserve a pre-change backup/export; apply migrations, verify the affected behavior and private-schema/RLS protections, and push matching migration files with the code. Report application failures and pending migrations rather than claiming synchronization. Coordinate shared migrations with teammates; do not auto-apply arbitrary branches or generate schema changes at request time. Destructive/data-rewriting migrations require a reviewed migration plan, backup and explicit owner approval. Ordinary application writes already persist directly to Supabase; code-only changes need no schema migration.
