# Team development workflow

Hamsa owns Client + Core Platform; Dheeraj owns Admin + Editor Operations. See [Day 1 responsibilities](DAY_1.md) and [the current roadmap](ROADMAP.md).

## Get the current milestone

```powershell
git clone --branch codex/foundation-and-commerce https://github.com/Dheeraj1301/VedioOS.git
cd VedioOS
```

Follow [README setup](../README.md). Each developer generates their own local `.env`, database and S3 credentials using `scripts/setup_local.py`. The app works with local SQLite when no cloud database URL is configured. Supabase credentials must be shared separately through an approved private channel, never committed or pasted into issues.

The shared Supabase project is already migrated through `core.0003` and `operations.0008`. Routine tests use an isolated test database. Prefer your own local database for development fixtures, pricing experiments and migrations; never flush the shared cloud database. Media in another developer's local SeaweedFS instance is not available on your machine. Cloud media deployment remains pending. The full clone-to-preview and test commands are in the [README](../README.md).

## Work without overwriting each other

1. Fetch the current milestone and inspect status before starting: `git fetch origin`, `git status`.
2. Start a feature branch from the agreed integration branch. Coordinate changes to shared models and migrations before generating overlapping migrations.
3. Run the checks appropriate to the change. Commerce checks and browser test commands are in [Phase 3](PHASE_3.md).
4. Commit each completed major change and push its branch. Share the branch/commit with the team. Use PRs for integration once a review target is established.
5. Pull with `git pull --ff-only` on a clean integration branch. If it cannot fast-forward, inspect and resolve the divergence; never force-push over teammates' work.

The owner explicitly requested immediate GitHub publication of verified major milestones. Push source, migrations, dependency locks and documentation together. Exclude `.env*` (except `.env.example`), `.runtime`, media, database dumps, tokens, local credentials, virtual environments and `node_modules`.

## Keep Supabase synchronized

The owner explicitly requests that the connected Supabase database and tables stay current with development changes. For each completed database-affecting milestone:

1. Review model changes and pending Django migrations; coordinate migration dependencies with the team.
2. Test migrations and behavior in an isolated database, and preserve a pre-change backup/export of affected shared data.
3. Apply reviewed non-destructive migrations to project `lmwvoniiykmfzuxigzqf`, private schema `vedioos`, using `manage.py migrate` with the existing server-only configuration.
4. Verify `manage.py migrate --check`, `manage.py makemigrations --check --dry-run`, `manage.py check_database`, and the affected behavior. Review Supabase security advisors for schema/security changes.
5. Push the matching code and migration files, and report both GitHub and database status. If either update fails, identify the mismatch and resolve it before calling the milestone synchronized.

Routine non-destructive migrations are already authorized; do not ask for permission again. Destructive/data-rewriting migrations require an explicit review and approval with a backup. Do not flush shared data, automatically deploy every teammate's branch, or mutate schemas on application requests. Normal application data changes already save directly to Supabase. Changes that do not affect models/data require no new migration.

## Current boundary

Catalog/quote screens and sandbox verification are available. [Allocation workflows](PHASE_4.md) are implemented but require explicit policy configuration before activation. Use application operations for live payment/assignment changes so their transaction and audit guards apply. Real payments, AI classification, production storage and deployment remain pending. No subscription was purchased for these milestones. Tell the owner before a paid subscription or upgrade is needed.
