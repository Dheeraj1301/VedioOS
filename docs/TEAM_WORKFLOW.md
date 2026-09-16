# Team development workflow

Hamsa owns Client + Core Platform; Dheeraj owns Admin + Editor Operations. See [Day 1 responsibilities](DAY_1.md) and [the current roadmap](ROADMAP.md).

## Get the current milestone

```powershell
git clone https://github.com/Dheeraj1301/VedioOS.git
cd VedioOS
git switch codex/foundation-and-commerce
```

Follow [README setup](../README.md). Each developer generates their own local `.env`, database and S3 credentials using `scripts/setup_local.py`. The app works with local SQLite when no cloud database URL is configured. Supabase credentials must be shared separately through an approved private channel, never committed or pasted into issues.

The shared Supabase project is already migrated through `core.0002`. Routine tests use an isolated test database. Prefer your own local database for development fixtures, pricing experiments and migrations; never flush the shared cloud database. Media in another developer's local SeaweedFS instance is not available on your machine. Cloud media deployment remains pending.

## Work without overwriting each other

1. Fetch the current milestone and inspect status before starting: `git fetch origin`, `git status`.
2. Start a feature branch from the agreed integration branch. Coordinate changes to shared models and migrations before generating overlapping migrations.
3. Run the checks appropriate to the change. Commerce checks and browser test commands are in [Phase 3](PHASE_3.md).
4. Commit each completed major change and push its branch. Share the branch/commit with the team. Use PRs for integration once a review target is established.
5. Pull with `git pull --ff-only` on a clean integration branch. If it cannot fast-forward, inspect and resolve the divergence; never force-push over teammates' work.

The owner explicitly requested immediate GitHub publication of verified major milestones. Push source, migrations, dependency locks and documentation together. Exclude `.env*` (except `.env.example`), `.runtime`, media, database dumps, tokens, local credentials, virtual environments and `node_modules`.

## Current boundary

Catalog/quote screens and sandbox verification are available. Real payments, automatic assignment, production storage and deployment remain disabled or pending. No subscription was purchased for this milestone. Tell the owner before a paid subscription or upgrade is needed.
