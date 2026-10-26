# Development Guide

This guide covers everything you need to know to set up, run, and develop the Draft Detective project locally.

## Prerequisites

- **uv**: Fast Python package/dependency manager. Official installer:

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

- **Node.js 22.22.2+**: For the frontend development (see `frontend/.nvmrc`)
- **pnpm**: Fast, disk space efficient package manager for Node.js. Install via npm:

```bash
npm install -g pnpm
```

- **Docker & Docker Compose**: For containerized development

- **libmagic**: Required for file type detection. Install via:

```bash
# macOS
brew install libmagic

# Ubuntu/Debian
sudo apt-get install libmagic1

# Fedora/RHEL
sudo dnf install file-libs
```

- **LibreOffice**: Converts legacy `.doc` uploads and rasterizes charts and vector drawings in DOCX files. The backend looks for `soffice` or `libreoffice` on your `PATH`:

```bash
# macOS
brew install --cask libreoffice

# Ubuntu/Debian
sudo apt-get install libreoffice-writer-nogui
```

Verify installations:

```bash
uv --version
node --version
pnpm --version
docker --version
docker compose version
```

## Python Version

This project requires **Python 3.13**. The version is pinned in:

- `pyproject.toml` (`requires-python = ">=3.13"`)

uv will automatically install Python 3.13 if it's not present on your system.

## Setup

### Backend Setup

From the project root:

```bash
# Install Python 3.13 if not present
uv python install 3.13

# Create virtual environment and install dependencies from lockfile (reproducible)
uv sync --frozen

# Alternative: Install without enforcing lockfile
# uv sync
```

This creates a local virtual environment at `.venv/` and installs all dependencies from `pyproject.toml` and `uv.lock`. Run every Python command through `uv run` (for example `uv run python --version`), so it uses that environment without activating it.

### Frontend Setup

```bash
# Navigate to frontend directory
cd frontend

# Install dependencies (always pnpm: the versions are pinned in pnpm-lock.yaml)
pnpm install

# Create the frontend's environment file (see Environment Variables)
cp .env.template .env
```

## Running the Application

### Backend (FastAPI)

#### Development Mode

```bash
# From the project root: serves on port 8000 (or $PORT) with auto-reload
uv run dev.py

# Alternative: using uvicorn directly
uv run uvicorn lib.api.main:app --reload --host 0.0.0.0 --port 8000
```

#### Production Mode

```bash
uv run uvicorn lib.api.main:app --host 0.0.0.0 --port 8000
```

### Frontend (Next.js)

#### Development Mode

```bash
# From frontend directory
cd frontend
pnpm dev
```

#### Production Mode

```bash
# Build the application
pnpm build

# Start production server (needs AUTH_URL in frontend/.env, see Environment Variables)
pnpm start
```

## Docker Setup (Recommended)

The project includes comprehensive Docker support with three services:

### Services Overview

- **PostgreSQL Database** (`db`): Port 5432
- **FastAPI Backend** (`api`): Port 8000
- **Next.js Frontend** (`app`): Port 3000

### Docker Files

- **`Dockerfile`**: Backend container (Python 3.13 + FastAPI)
- **`frontend/Dockerfile`**: Frontend container (Node.js 22 + Next.js)
- **`docker-compose.yml`**: Orchestrates all services

### Quick Start

```bash
# Start all services in detached mode
docker compose up -d

# View logs
docker compose logs -f

# Stop all services
docker compose down
```

Both containers take their settings from the root `.env` (see Environment Variables): the API reads all of it, and the frontend reads only `AUTH_SECRET` and the sign-in provider keys. The frontend image is built with the default API URL, `http://localhost:8000`.

### Database Migrations

After starting the services, run database migrations:

```bash
# With local Python environment
uv run alembic upgrade head

# Or using the containerized backend
docker compose exec api uv run alembic upgrade head
```

## Environment Variables

The backend and the frontend each read their own `.env`, and each has a template next to it. Copy both and fill in the required variables:

```bash
# Backend (also read by docker compose)
cp .env.template .env

# Frontend, for pnpm dev and pnpm start
cp frontend/.env.template frontend/.env
```

Sign-in needs the same `AUTH_SECRET` in both files, and at least one provider configured in both: Google (`AUTH_GOOGLE_ID` and `AUTH_GOOGLE_SECRET`) or Microsoft Entra ID (`AUTH_MICROSOFT_ENTRA_ID_ID`, `AUTH_MICROSOFT_ENTRA_ID_SECRET`, and `AUTH_MICROSOFT_ENTRA_ID_ISSUER`, which is `https://login.microsoftonline.com/<tenant id>/v2.0`): the frontend signs users in and mints the API's tokens with that secret, and the backend verifies them with it. The backend also won't start without a provider, which its MCP server signs in with. Register `http://localhost:3000/api/auth/callback/<provider>` (`google` or `microsoft-entra-id`) as a redirect URI with the provider. To connect MCP clients too, also register `http://localhost:8000/mcp/auth/callback` (`MCP_BASE_URL` plus `/auth/callback`).

`pnpm dev` trusts the host it runs on, but a production build (`pnpm start`) doesn't: add `AUTH_URL=http://localhost:3000` to `frontend/.env` before running it, or every sign-in request fails with `UntrustedHost`.

For production deployment, see [docs/railway-deployment.md](docs/railway-deployment.md).


## Development Workflow

### Dependency Management

- **Add a dependency**:

```bash
uv add <package>
```

- **Remove a dependency**:

```bash
uv remove <package>
```

- **Upgrade dependencies**:

```bash
uv lock --upgrade && uv sync --frozen
```

- **Reinstall if environment becomes inconsistent**:

```bash
uv sync --reinstall
```

### Database Management

```bash
# Create a new migration
uv run alembic revision --autogenerate -m "description"

# Apply migrations
uv run alembic upgrade head

# Rollback migration
uv run alembic downgrade -1
```

### Testing

```bash
# Run all Python tests (unit + integration)
uv run pytest

# Run a specific test file or pattern
uv run pytest tests/integration/test_workflow_progress_service.py
uv run pytest tests/ -k "test_name"
```

**Test Organization**: Standard tests live under `tests/unit/` and `tests/integration/`. Shared fixtures and helpers (e.g. `data_path`, `create_test_file_document_from_path`) are in `tests/conftest.py`.

**Test database**: the suite never uses the `.env` database. `tests/integration_db.py` points it at the same database name with `_test` appended (`ai_reviewer_test` with the default `.env`), in the same Postgres; set `TEST_DATABASE_URL` to use another. The integration tests create and migrate it on their own, so Postgres only has to be running. It persists between runs (each test deletes its own rows); `uv run python -m tests.integration_db --reset` rebuilds it from empty.

### Evaluations (Inspect AI)

LLM agent evaluations use [Inspect AI](https://inspect.ai-safety-institute.org.uk/) and live under `evals_inspectai/e2e/`. These are end-to-end evals that trigger each workflow through the running API server (backend must be running), mirroring the full pipeline that real users trigger.

Each workflow has its own eval directory with a `dataset.yaml` and a task definition module.

```bash
# Run a full eval suite for a workflow
uv run inspect eval evals_inspectai/e2e/reference_validation_v2/reference_validation_v2_e2e.py

# Run a specific sample by ID (1-indexed)
uv run inspect eval evals_inspectai/e2e/figures_tables_check/figures_tables_check_e2e.py --sample-id=1

# Run a specific sample multiple times (useful for testing determinism)
uv run inspect eval evals_inspectai/e2e/figures_tables_check/figures_tables_check_e2e.py --sample-id=1 --epochs=3

# Run a range of samples
uv run inspect eval evals_inspectai/e2e/reference_validation_v2/reference_validation_v2_e2e.py --limit=5-10

# View eval results in the Inspect AI dashboard
uv run inspect view
```

**Important:** E2E evals require the backend server to be running (`uv run dev.py`).

### Code Quality

```bash
# Format, lint and type check Python code
uv run ruff format .
uv run ruff check .
uv run mypy .

# Lint, test and build the frontend (the build also type checks)
cd frontend
pnpm lint
pnpm test
pnpm build
```

CI blocks a PR on any of these. `AGENTS.md` lists which ones to run before handing back a change.

## Security Scanning

Security scans run automatically on every PR using [Trivy](https://trivy.dev/) via the official [trivy-action](https://github.com/aquasecurity/trivy-action).

> **Why Trivy?** While Docker Scout is excellent and integrates natively with Docker, we use Trivy for compliance and auditing purposes. Trivy is open-source, vendor-neutral, and widely accepted in enterprise security workflows.
