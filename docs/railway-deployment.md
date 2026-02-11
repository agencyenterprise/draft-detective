# Railway Deployment Guide

This guide covers deploying AI Reviewer to [Railway](https://railway.app).

## Prerequisites

- Railway account
- OpenAI API key
- (Optional) Langfuse account for observability

## Quick Start

### 1. Create Railway Project

1. Go to [Railway Dashboard](https://railway.app/dashboard)
2. Click **New Project** → **Deploy from GitHub repo**
3. Select your AI Reviewer repository

### 2. Add Required Services

Create these services in your Railway project:

| Service | How to Add |
|---------|------------|
| **PostgreSQL** | Click **+ New** → **Database** → **Add PostgreSQL** |
| **Backend API** | Connect from GitHub (uses root `railway.toml`) |
| **Frontend** | Connect from GitHub, set root directory to `frontend/` |

### 3. Configure Environment Variables

#### Backend API Service

Set these in Railway dashboard under **Variables**:

**Required:**
```
AUTH_SECRET=<generate-a-secure-random-string>
OPENAI_API_KEY=<your-openai-api-key>
FRONTEND_URL=https://<your-frontend-domain>.railway.app
```

**Auto-configured** (via `railway.toml`):
- `DATABASE_URL`, `POSTGRES_*` - Linked from PostgreSQL service

**Optional:**
```
# Langfuse observability
LANGFUSE_HOST=https://cloud.langfuse.com
LANGFUSE_SECRET_KEY=<your-secret-key>
LANGFUSE_PUBLIC_KEY=<your-public-key>

# Custom workflow configuration (see below)
WORKFLOW_CONFIG_PATH=/app/config/workflow_config.yaml

# File converters (defaults shown)
MAIN_FILE_CONVERTER=markitdown
SUPPORTING_FILE_CONVERTER=markitdown

# If using Docling for better PDF parsing
DOCLING_SERVE_API_URL=<docling-service-url>
DOCLING_SERVE_API_KEY=<docling-api-key>
```

#### Frontend Service

Set these in Railway dashboard:

**Required:**
```
AUTH_SECRET=<same-value-as-backend>
```

**Auto-configured** (via `frontend/railway.toml`):
- `NEXT_PUBLIC_API_URL` - References backend service

**Optional:**
```
NEXT_PUBLIC_POSTHOG_KEY=<posthog-project-key>
NEXT_PUBLIC_POSTHOG_HOST=https://us.i.posthog.com
NEXT_PUBLIC_SHOW_EXPERIMENTAL_FEATURES=true
```

### 4. Deploy

Railway automatically deploys when you push to your connected branch. The backend runs database migrations automatically via the `preDeployCommand` in `railway.toml`.

## Custom Workflow Configuration

The default workflow configuration (`lib/config/workflow_config.yaml`) is self-documented and works out of the box. To customize:

### Add Config Volume

1. Add a volume to your backend service in Railway dashboard
2. Set mount path to `/app/config`
3. Upload your custom `workflow_config.yaml` to the volume
4. Set environment variable: `WORKFLOW_CONFIG_PATH=/app/config/workflow_config.yaml`

> Railway doesn't allow scp or have a text editor, so use pbcopy with pipe to send changes through ssh.

## Troubleshooting

### Database Connection Issues

Ensure the PostgreSQL service is running and the `DATABASE_URL` variable is correctly linked:
1. Go to Backend service → Variables
2. Click **+ New Variable** → **Add Reference**
3. Select PostgreSQL service and `DATABASE_URL`

### Migrations Not Running

Check the deploy logs for migration output. Migrations run automatically via:
```toml
preDeployCommand = ["uv run alembic upgrade head"]
```

### Health Check Failures

The backend health endpoint is `/api/health`. If health checks fail:
1. Check deploy logs for startup errors
2. Verify all required environment variables are set
3. Ensure PostgreSQL is accessible

## Environment Variable Reference

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `AUTH_SECRET` | ✅ | - | JWT signing secret (must match frontend) |
| `OPENAI_API_KEY` | ✅ | - | OpenAI API key for LLM operations |
| `DATABASE_URL` | ✅ | - | PostgreSQL connection string |
| `FRONTEND_URL` | ✅ | `http://localhost:3000` | Frontend URL for share links |
| `WORKFLOW_CONFIG_PATH` | ❌ | Built-in config | Path to custom workflow YAML |
| `MAIN_FILE_CONVERTER` | ❌ | `docling` | Converter for main documents |
| `SUPPORTING_FILE_CONVERTER` | ❌ | `markitdown` | Converter for supporting docs |
| `LANGFUSE_*` | ❌ | - | Langfuse observability config |
| `LANGGRAPH_MAX_CONCURRENCY` | ❌ | `30` | Max parallel workflow nodes |

