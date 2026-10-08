# Deploy this fork with Coolify

Connect `jt7991/mealie`, branch `mealie-next`, as a Git-based application.

| Setting | Value |
| --- | --- |
| Build pack | Dockerfile |
| Base directory / build context | `/` (repository root) |
| Dockerfile location | `/docker/Dockerfile` |
| Build stage, if requested | `production` |
| Port exposed | `9000` |
| Domain | Your chosen HTTPS domain |
| Persistent storage destination | `/app/data` |
| Health check | HTTP GET `/api/app/about` on port `9000` |

The Dockerfile builds both the Nuxt frontend and the Python backend from this checkout;
no prebuilt package or extra build context is required. It includes a health check with
a 90-second startup grace period. Use one replica with SQLite, and avoid overlapping
deployments against the same SQLite volume. The default single worker is sufficient.

See Coolify's [Dockerfile](https://coolify.io/docs/applications/builds/dockerfile) and
[persistent storage](https://coolify.io/docs/applications/configuration/persistent-storage)
documentation for the corresponding controls.

## Runtime environment

Copy the variables from [docker/coolify.env.example](docker/coolify.env.example) into
Coolify's runtime environment. Replace `BASE_URL` with the exact HTTPS address users
will visit (no trailing slash), and `SMTP_PASSWORD` with your Resend API key. Mark the
key as a secret. Keep **Build Variable** disabled for all these runtime variables;
none are needed during the image build. The key is not in this
repository or image; the local `.run/email.env` file is excluded from Git and Docker.

`MAGIC_LINK_ENABLED=true` enables email login when SMTP is configured. Resend must
authorize the sender `recipes@jakey.fyi`; its domain must be verified. These SMTP
settings also power invitations and password-reset emails.

Opening a magic link signs in immediately and remembers the session. Links expire
after 15 minutes and are single-use. `TOKEN_TIME=8760` gives sessions a one-year
lifetime; the normal session refresh flow renews them while the app is in use.

`ALLOW_SIGNUP=true` allows anyone who can reach this deployment to register.
Accounts must exist before a magic link can be requested. Keep password login enabled
for initial administrator setup; password login remains available as a fallback.

No custom start command, build command, `SECRET`, or `SESSION_SECRET` is required.
Mealie generates its signing secrets in `/app/data`, so retaining that volume also
retains them across deployments. The production mode and listening address are already
configured by the Dockerfile/application defaults.

## First deployment and existing local data

A new volume creates a fresh Mealie installation. Sign in with the initial account
`changeme@example.com` / `MyPassword`, then set your real email and change that password
in account settings before using email login. Environment variables do not copy the
existing local admin account or recipes to the server.

To retain the local installation, create and download a backup from Mealie's admin
backup page, then restore it in the Coolify instance. Keep the local instance until
the restored users and recipes are verified. Never commit a database or backup to Git.

Do not use the local Tailscale URL as `BASE_URL` on the server unless that is actually
how users will reach the new instance. Email links use `BASE_URL` exactly.

## Container verification

GitHub Actions workflows have been removed from this fork. Coolify builds the
Dockerfile directly; no GitHub Actions build is required.

For a local Docker build:

```sh
docker build -f docker/Dockerfile -t mealie:local .
docker run -d --name mealie -p 9000:9000 --env-file docker/coolify.env.example \
  -v mealie-data:/app/data mealie:local
```

Fill in the two placeholders in a private copy of the environment file before running.
