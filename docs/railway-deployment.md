# Railway Deployment Guide

This guide covers deploying Draft Detective to [Railway](https://railway.app).

## Prerequisites

- Railway account
- A Google or Microsoft Entra ID OAuth app for sign-in (`DEVELOPMENT.md` covers both)
- OpenAI API key, unless each user brings their own (see below)
- (Optional) Langfuse account for observability

## Quick Start

### 1. Create Railway Project

1. Go to [Railway Dashboard](https://railway.app/dashboard)
2. Click **New Project** → **Deploy from GitHub repo**
3. Select your Draft Detective repository

### 2. Add Required Services

Create these services in your Railway project:

| Service         | How to Add                                             |
| --------------- | ------------------------------------------------------ |
| **PostgreSQL**  | Click **+ New** → **Database** → **Add PostgreSQL**    |
| **Backend API** | Connect from GitHub (uses root `railway.toml`)         |
| **Frontend**    | Connect from GitHub, set root directory to `frontend/` |

The migrations enable the `vector` extension, which Railway's PostgreSQL image doesn't include. After adding the database, open its **Settings** and change the source image to `pgvector/pgvector:pg<major>`, where `<major>` is the PostgreSQL major version of the image Railway deployed (the tag on its source image, such as `17`). The data on the volume was initialized at that major, and an image of another major won't start on it. `docker-compose.yml` and `k8s/` run the same image, at `pg16`. The service keeps its volume and variables, `DATABASE_URL` among them. Without the change, the backend's first pre-deploy migration fails with `extension "vector" is not available`. Railway's in-place major version upgrade supports only its own image, so a later upgrade to a new major is a dump and restore.

The two `railway.toml` files set each service's build and deploy settings: the Dockerfile builder, the start command, the health check and, for the backend, the migrations. They set nothing else. Variables and the uploads volume are set on each service in the dashboard, as below.

> **Note:** Railway has deprecated `railway.toml` (Config as Code) in favour of Infrastructure as Code (`.railway/railway.ts`). Services that already use the file keep it until 2026-12-01. A service created since the deprecation ignores the file, so enter its settings under the service's **Settings** instead:
>
> - **Backend:** pre-deploy command `uv run alembic upgrade head` and health check path `/api/health`.
> - **Frontend:** root directory `frontend/` and health check path `/api/health`.
>
> Both build from their Dockerfile, whose `CMD` already starts the service. Without the backend's pre-deploy command, no migrations run and the backend starts against an empty database.

### 3. Add the Uploads Volume

Uploaded files live on disk. On the backend service, add a volume (**+ New** → **Volume**, or right-click the service) mounted at `/app/uploads`, the directory the image creates for them. Without it, every redeploy loses the uploads. Railway mounts volumes as root while the image runs as the non-root `app` user, so also set `RAILWAY_RUN_UID=0` on the backend (step 4). Without it the backend can't write to the volume and exits at startup, when it creates `uploads/logs`.

### 4. Configure Environment Variables

#### Backend API Service

Set these in Railway dashboard under **Variables**:

**Required:**

```
DATABASE_URL=${{Postgres.DATABASE_URL}}
RAILWAY_RUN_UID=0  # lets the non-root app user write to the uploads volume
AUTH_SECRET=<generate-a-secure-random-string>
FRONTEND_URL=https://<your-frontend-domain>
MCP_BASE_URL=https://<your-backend-domain>/mcp

# A sign-in provider: Google, Microsoft Entra ID, or both
AUTH_GOOGLE_ID=<client-id>
AUTH_GOOGLE_SECRET=<client-secret>
AUTH_MICROSOFT_ENTRA_ID_ID=<client-id>
AUTH_MICROSOFT_ENTRA_ID_SECRET=<client-secret>
AUTH_MICROSOFT_ENTRA_ID_ISSUER=https://login.microsoftonline.com/<tenant-id>/v2.0
```

`DATABASE_URL` is a [reference variable](https://docs.railway.com/variables#referencing-another-services-variable): `Postgres` is the database service's name, so use yours if you renamed it. The backend won't start without a sign-in provider: Google needs both of its keys, Entra ID all three.

Register the deployed URLs as redirect URIs with the provider, since the localhost ones in `DEVELOPMENT.md` don't cover them: `https://<your-frontend-domain>/api/auth/callback/<provider>` (`google` or `microsoft-entra-id`) for sign-in, and `https://<your-backend-domain>/mcp/auth/callback` (`MCP_BASE_URL` plus `/auth/callback`) for MCP clients. With Entra ID, MCP sign-in also asks for the scope `api://<client-id>/mcp-access`, so the app registration needs `api://<client-id>` as an Application ID URI and a scope named `mcp-access` under **Expose an API**.

**Optional:**

```
# Server-wide OpenAI key. Without it, each user saves their own key in the app.
OPENAI_API_KEY=<your-openai-api-key>

# Langfuse observability
LANGFUSE_HOST=https://cloud.langfuse.com
LANGFUSE_SECRET_KEY=<your-secret-key>
LANGFUSE_PUBLIC_KEY=<your-public-key>
```

`.env.template` lists the rest, with their defaults.

#### Frontend Service

Set these in Railway dashboard:

**Required:**

```
NEXT_PUBLIC_API_URL=https://${{ai-reviewer-api.RAILWAY_PUBLIC_DOMAIN}}
AUTH_SECRET=<same-value-as-backend>
AUTH_URL=https://<your-frontend-domain>

# The same sign-in provider keys as the backend
AUTH_GOOGLE_ID=<client-id>
AUTH_GOOGLE_SECRET=<client-secret>
AUTH_MICROSOFT_ENTRA_ID_ID=<client-id>
AUTH_MICROSOFT_ENTRA_ID_SECRET=<client-secret>
AUTH_MICROSOFT_ENTRA_ID_ISSUER=https://login.microsoftonline.com/<tenant-id>/v2.0
```

`ai-reviewer-api` is the backend service's name: use yours. `AUTH_URL` is the frontend's public URL, and sign-in fails with `UntrustedHost` without it. `NEXT_PUBLIC_*` values are compiled into the build, so changing one takes a redeploy.

**Optional:**

```
NEXT_PUBLIC_POSTHOG_KEY=<posthog-project-key>
NEXT_PUBLIC_POSTHOG_HOST=https://us.i.posthog.com
# Ask each user for an OpenAI key before their first run (for a backend with no OPENAI_API_KEY)
NEXT_PUBLIC_REQUIRE_OPENAI_API_KEY_CONFIG=true
```

### 5. Deploy

Railway automatically deploys when you push to your connected branch. The backend runs database migrations before each deploy, via the `preDeployCommand` in `railway.toml` or the pre-deploy command in its **Settings** (see the note in step 2).

## Custom Workflow Configuration

Assessment rules live in `skills/<skill-name>/SKILL.md` at the repo root, which
is the single source of truth for the prompt each workflow runs. To customize a
check — for example the trigger words and advocacy phrases in
`skills/advocacy-tone/SKILL.md` — edit that file in your fork and redeploy.

> **Note:** skills are resolved from the deployed source tree, so there is no
> runtime override — no environment variable and no mounted volume. Changing a
> check requires a fork and a redeploy.
>
> This replaces the `workflow_config.yaml` / `WORKFLOW_CONFIG_PATH` mechanism,
> which was removed along with the v1 Advocacy & Tone workflow it configured.

## Troubleshooting

### Database Connection Issues

Ensure the PostgreSQL service is running and the backend's `DATABASE_URL` variable references it:

1. Go to Backend service → Variables
2. Click **+ New Variable** → **Add Reference**
3. Select PostgreSQL service and `DATABASE_URL`

### Migrations Not Running

Check the deploy logs for migration output. Migrations run automatically via:

```toml
preDeployCommand = ["uv run alembic upgrade head"]
```

On a service that ignores `railway.toml` (see the note in step 2), check that the same command is the pre-deploy command in its **Settings**.

If the log says `extension "vector" is not available`, the database runs Railway's own PostgreSQL image: switch it to the `pgvector/pgvector` image of the same major version (see step 2) and redeploy the backend.

### Health Check Failures

The backend health endpoint is `/api/health`. If health checks fail:

1. Check deploy logs for startup errors
2. Verify all required environment variables are set: a missing sign-in provider stops the backend at startup
3. Ensure PostgreSQL is accessible

## Environment Variable Reference

| Variable                                      | Service  | Required | Default                     | Description                                              |
| --------------------------------------------- | -------- | -------- | --------------------------- | -------------------------------------------------------- |
| `DATABASE_URL`                                | Backend  | ✅       | -                           | PostgreSQL connection string                             |
| `AUTH_SECRET`                                 | Both     | ✅       | -                           | JWT signing secret (the same value on both)              |
| `AUTH_GOOGLE_*` / `AUTH_MICROSOFT_ENTRA_ID_*` | Both     | ✅       | -                           | Sign-in provider: at least one, the same on both         |
| `FRONTEND_URL`                                | Backend  | ✅       | `http://localhost:3000`     | Frontend URL for share links                             |
| `MCP_BASE_URL`                                | Backend  | ✅       | `http://localhost:8000/mcp` | Public URL of the MCP server, ending in `/mcp`           |
| `AUTH_URL`                                    | Frontend | ✅       | -                           | Frontend's public URL, for sign-in                       |
| `NEXT_PUBLIC_API_URL`                         | Frontend | ✅       | `http://localhost:8000`     | Backend's public URL, set at build time                  |
| `OPENAI_API_KEY`                              | Backend  | ❌       | -                           | Server-wide OpenAI key; without it users bring their own |
| `LANGFUSE_*`                                  | Backend  | ❌       | -                           | Langfuse observability config                            |
| `LANGGRAPH_MAX_CONCURRENCY`                   | Backend  | ❌       | `30`                        | Max parallel workflow nodes                              |
| `TASK_QUEUE_CONCURRENCY`                      | Backend  | ❌       | `50`                        | Jobs each API process's queue worker runs at once        |
