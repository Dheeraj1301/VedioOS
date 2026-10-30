# Vercel deployment

BRIO uses Vercel's Django runtime with `vedioos.wsgi:application` as the explicit entrypoint. The project dependencies and Python version are declared in `pyproject.toml`; this prevents Vercel from treating the Ruff-only configuration as an empty Python project. The runtime region is Seoul (`icn1`) to stay close to the selected Supabase project.

## Required private configuration

Configure values through Vercel Environment Variables. Never commit them or paste their values into issues, logs or chat:

- `SECRET_KEY`
- `DEBUG=false`
- `ALLOWED_HOSTS=brio.org.in,<project>.vercel.app`
- `CSRF_TRUSTED_ORIGINS=https://brio.org.in,https://<project>.vercel.app`
- the approved Supabase database/Auth variables documented in `.env.example`
- an externally reachable HTTPS private S3-compatible storage endpoint and its private credentials
- an approved production email backend and sender domain

Use `DATABASE_CONN_MAX_AGE=0` unless a deployment-safe connection pool has been explicitly sized. Do not copy the ignored development `.env` wholesale: it contains local-only URLs and test settings.

## Release gate

Run these checks against the intended Vercel environment before promoting or attaching the production domain:

```powershell
python manage.py check --deploy
python manage.py check_release
python manage.py migrate --check
```

The domain must not be promoted while `check_release` reports blockers. In particular, loopback media storage, sandbox/test payments, unapproved production prices, console email, or unresolved legal/recovery decisions are not production configurations. A Vercel preview may be used to validate the runtime while those features remain disabled and accurately labeled.

After a deployment is healthy, add `brio.org.in` to the Vercel project, apply the exact DNS records returned by Vercel at the domain registrar, then re-run the release and end-to-end security checks over HTTPS.
