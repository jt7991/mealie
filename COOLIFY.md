# Deploy this fork with Coolify

GitHub Actions builds and checks the production image, then publishes it to GHCR.
Coolify pulls the image; it must not compile this application on the 4 GB server.

Disable Auto Deploy on the old Git-based application before pushing changes.
Create a **Docker Image** application in Coolify using the settings below.
After the first publication, open the GitHub package settings for `jt7991/mealie`
and change its visibility to **Public** so Coolify can pull without credentials.
Public repository visibility does not automatically make a new GHCR package public.

| Setting | Value |
| --- | --- |
| Resource type | Docker Image |
| Docker image | `ghcr.io/jt7991/mealie` |
| Image tag | `latest` |
| Port exposed | `9000` |
| Domain | Your chosen HTTPS domain |
| Persistent storage destination | `/app/data` |
| Health check | HTTP GET `/api/app/about` on port `9000` |

The published image contains both the Nuxt frontend and Python backend, built on a
standard GitHub-hosted Ubuntu runner for `linux/amd64`. It includes a health check with
a 90-second startup grace period. Use one replica with SQLite, and avoid overlapping
deployments against the same SQLite volume. The default single worker is sufficient.

Reuse the old application's exact named volume if it contains data; a new volume
creates a new database. Stop the old app before attaching its volume or moving the
domain. Keep the old volume until the new instance and data are verified.

For automatic deployment, enable Coolify API access and create an API token with
Deploy permission. In the GitHub repository's Settings > Secrets and variables >
Actions, add `COOLIFY_WEBHOOK` (the new Docker Image app's authenticated HTTPS deploy
webhook URL) and `COOLIFY_TOKEN` (the API token). Do not use the old Git app's webhook.
The workflow requests deployment only after the image passes checks and is published.
Without both secrets configured, the first build can publish an image without
deploying; make the GHCR package public before configuring the secrets. You can then
click Deploy in Coolify for the first launch. Future code pushes deploy automatically.
Webhook acceptance means deployment was queued, not that the container is healthy.
For a fixed version or rollback, use the `sha-<full commit SHA>` image tag.

See Coolify's [Docker Image](https://coolify.io/docs/applications/deployments/docker-image) and
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

The only GitHub Actions workflow is `.github/workflows/publish-image.yml`. It builds
on pushes to `mealie-next` (except Markdown-only changes) or manual dispatch, tests
API and frontend startup, then publishes the image. It uses the built-in GitHub
token with package write permission; no Resend or Coolify credentials are needed.
Runtime credentials remain exclusively in Coolify.

For a local Docker build:

```sh
docker build -f docker/Dockerfile -t mealie:local .
docker run -d --name mealie -p 9000:9000 --env-file docker/coolify.env.example \
  -v mealie-data:/app/data mealie:local
```

Fill in the two placeholders in a private copy of the environment file before running.
