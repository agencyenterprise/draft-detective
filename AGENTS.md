# Project Instructions

A Python backend (FastAPI + LangChain, under `lib/`) and a Next.js frontend (under `frontend/`). Rules marked **Always** or **Never** are strict. The rest are defaults to follow unless there's a reason not to.

Deeper docs, read when the task needs them: `DEVELOPMENT.md` (setup, Docker, environment variables, database), `frontend/README.md` (frontend setup and Node version) and `evals_inspectai/README.md` (the eval suites and how to choose the model they run).

## Quick Reference

```bash
# Backend (always uv)
uv run dev.py                              # Start the backend (port 8000, auto-reload)
uv run pytest tests/unit                   # Unit tests
uv run pytest tests/integration            # Integration tests (on the *_test database)
uv run pytest tests/path/to/test.py -k "name"
uv run ruff format .                       # Format (CI checks the whole repo)
uv run ruff check .                        # Lint (CI blocks on errors; --fix applies safe fixes)
uv run mypy .                              # Type check (CI blocks on errors)

# Frontend (always pnpm, from frontend/)
cd frontend && pnpm install
cd frontend && pnpm dev
cd frontend && pnpm test                   # Vitest
cd frontend && pnpm run lint
cd frontend && pnpm run openapi-generate   # Regenerate API types
```

## Before Handing Back Work

Run the same checks CI runs for the side you touched. A red check here means a red PR.

- **Python changes:** `uv run ruff format .`, `uv run ruff check .`, `uv run mypy .` and `uv run pytest tests/unit`. The tree is Ruff-clean, so run both Ruff commands on the whole repo. Also run the integration tests you touched (`uv run pytest tests/integration/...`); CI runs the whole integration suite.
- **Frontend changes:** `pnpm run lint`, `pnpm test` and `pnpm run build`, from `frontend/`.
- **Backend API changes:** regenerate the frontend types (see below), then run the frontend checks.

If a check fails and you can't fix it, tell the user which one and why. Never hand the work back as finished.

---

## Python Backend Rules

### Always use `uv`, never raw `python`, `pip` or `pytest`

Dependencies are pinned in `uv.lock`. Calling `python` or `pip` directly can pick up a different interpreter or install outside the lockfile.

```bash
# ✅ Correct
uv run python script.py
uv run pytest tests/ -k "test_name"
uv add package-name

# ❌ Incorrect
python script.py
.venv/bin/python script.py
python -m pytest
pip install package-name
```

### Never create an `__init__.py` unless it has a job

The codebase uses implicit namespace packages, and pytest runs with `--import-mode=importlib` to match. Add an `__init__.py` only when it does real work, such as re-exporting members (`lib/models/__init__.py` does this for the database models). Never add an empty or marker one.

```bash
# ✅ Correct
lib/workflows/new_workflow/
├── state.py
├── graph.py
└── nodes/
    └── process.py

# ❌ Incorrect
lib/workflows/new_workflow/
├── __init__.py          # Don't create this
└── nodes/
    ├── __init__.py      # Or this
    └── process.py
```

### Never import inside a function

Always put imports at the top of the file. A lazy import hides a module's dependencies, and a broken import then fails only when that code path runs instead of at startup. The one exception is breaking a circular import, and it must carry a comment saying so.

```python
# ✅ Correct
from lib.services.users import UserService

def process(doc: Document) -> None:
    service = UserService()

# ✅ Acceptable - a circular import, explained
def process(doc: Document) -> None:
    # Imported here to avoid a circular import between lib.services.users and lib.services.documents
    from lib.services.users import UserService  # noqa: PLC0415  circular, see above
    service = UserService()
```

Ruff enforces this (`PLC0415`). An import that must stay inside a function always carries `# noqa: PLC0415` followed by its reason, so the exception is visible where it happens.

Never use `import *` either (Ruff flags it: `F403`, `F405`).

### Always use Pydantic `BaseModel`, never `@dataclass`

One modeling tool across the codebase, and every model gets validation and serialization the same way.

```python
# ✅ Correct
from pydantic import BaseModel, Field

class DocumentMetadata(BaseModel):
    title: str = Field(description="Document title")
    page_count: int
```

### Always use SQLAlchemy 2.0 `select()` with `col()`

Never use the legacy `db.query()` style. Wrap SQLModel columns in `col()` inside `.where()`, `.join()` and similar calls: without it mypy reads `File.project_id == x` as a plain `bool` and reports an error.

```python
# ✅ Correct
from sqlalchemy import select
from sqlmodel import col

stmt = select(File).where(col(File.project_id) == project_id)
stmt = select(File).where(col(File.id).in_(file_ids))

# ❌ Incorrect
db.query(File).filter(File.project_id == project_id).all()   # legacy 1.x
select(File).where(File.project_id == project_id)            # mypy error: bool
```

### Never run Alembic

When you change a model in `lib/models/`, change only the model file, then remind the user to generate and apply the migration. The user reviews migrations and applies them to their own database:

```bash
uv run alembic revision --autogenerate -m "description"
uv run alembic upgrade head
```

The one exception is the test database: the integration tests migrate it themselves, and `uv run python -m tests.integration_db --reset` rebuilds it. Both only ever touch a database whose name ends in `_test`.

### Type hints

Always annotate function signatures. Always use built-in generics and `|` unions (we're on Python 3.13); Ruff's `UP` rules flag `typing.List`, `Optional` and `Union`.

```python
# ✅ Correct
def process_documents(files: list[File], config: ProcessingConfig | None = None) -> DocumentResult: ...

# ❌ Incorrect
from typing import List, Optional
def process_documents(files: List[File], config: Optional[ProcessingConfig] = None) -> DocumentResult: ...
```

Use `TypedDict` for workflow state.

### Always keep mypy at zero errors

The baseline is zero, so any error mypy reports came from the current work. The `backend.yml` CI workflow runs `uv run mypy .` and blocks the merge on failure.

- After editing a `.py` file (backend, tests or evals), run `uv run mypy <touched paths>`.
- Before finishing, run `uv run mypy .` once. Changes often break untouched files: union narrowing, SQLAlchemy `Select[...]` reassignments and structured-output agent return types are common sources.
- Never use a bare `# type: ignore`. When nothing else works (narrowing with `isinstance`, `cast()`, a better annotation), use `# type: ignore[specific-code]` with a short comment if the reason isn't obvious.
- If mypy misbehaves, `rm -rf .mypy_cache` and retry before assuming a real error.

---

## Frontend Rules

### Check Next.js APIs against the installed docs

We're on Next.js 16, which renamed and removed APIs your training data may still describe (`middleware.ts` is now `proxy.ts`, for one). Before using a Next.js API, config option or file convention you aren't sure of, read its guide in `frontend/node_modules/next/dist/docs/`, which matches the installed version. Heed its deprecation notices.

### Always use `pnpm`, from `frontend/`

Dependencies are pinned in `pnpm-lock.yaml`. `npm` and `yarn` ignore it.

### Never edit `frontend/lib/generated-api/`

The files are generated by Hey API (`@hey-api/openapi-ts`) from the backend's OpenAPI schema and are overwritten on every regeneration. Always run `pnpm run openapi-generate` from `frontend/` after any backend API change (endpoints, request or response types, schemas). It reads the schema from the backend on port 8000, so the backend must be running.

When port 8000 belongs to another checkout's server, generate from a file instead. Importing the app builds the schema without a database or a port:

```bash
uv run python -c "import json; from lib.api.main import app; json.dump(app.openapi(), open('/tmp/openapi.json','w'))"
cd frontend
pnpm exec openapi-ts -i /tmp/openapi.json
git checkout lib/generated-api/client.gen.ts
```

A file input also rewrites the `baseUrl: 'http://localhost:8000' | (string & {});` line in `types.gen.ts`: restore that one line by hand, so `git diff` shows only your real changes.

Never give a new response model the same name as an existing schema. Hey API then renames both to fully qualified names and breaks existing imports, so prefix the new one instead.

### Always convert generated `Date` fields with `new Date()`

Fields the generated types declare as `Date` arrive as ISO strings at runtime: the SDK never applies the generated response transformers. Calling `.toISOString()` or `.getUTCMonth()` on one throws at render time, and TypeScript can't catch it. Always wrap the value in `new Date(...)` before using it as a date (see `components/admin/dashboard/format.ts`).

### Never use `useEffect` for derived state or data fetching

Effects that sync state cause extra renders and stale-value bugs. Use `useEffect` only to sync with something outside React (DOM APIs, subscriptions, timers). Instead:

- **Derived state:** compute it during render (`useMemo` if it's expensive).
- **Side effects of user actions:** do them in the event handler.
- **Data fetching:** use React Query.
- **Resetting state:** change the component's `key`.

```tsx
// ❌ Incorrect
const [fullName, setFullName] = useState("");
useEffect(() => setFullName(`${firstName} ${lastName}`), [firstName, lastName]);
useEffect(() => { fetchData().then(setData); }, [id]);

// ✅ Correct
const fullName = `${firstName} ${lastName}`;
const { data } = useQuery({ queryKey: ["data", id], queryFn: fetchData });
```

### Components and types

- Always build UI from the shadcn/ui components in `frontend/components/ui/` and Tailwind utility classes. Write custom CSS only when Tailwind can't express it.
- Never use `any`. Type component props explicitly.

---

## Code Size

- Keep files around 100–200 lines, 300 at most. Database models, configuration and workflow definitions that need to stay together can run longer.
- Split a file when it mixes responsibilities, not just because it's long.
- Keep functions to about 20 lines. Split longer ones unless splitting would make the code harder to follow.

---

## Skill Files

Skill files under `skills/` must be **environment-agnostic**. Users install them standalone in Claude apps and other agent runtimes, not just in this repo's workflow agents.

- Never reference runtime-specific tool names (e.g. a workflow agent's `view_image`), internal URL schemes or file layouts specific to one runtime.
- Phrase capabilities conditionally: "when you have a way to view images…", "if you can search the document…".
- Runtime-specific wiring (which tool to call, what a `draftdetective://` src means) belongs in the agent's system prompt, next to where the tool is bound.

---

## Testing

### Backend Tests (pytest)

```bash
uv run pytest tests/unit                          # Unit tests
uv run pytest tests/integration                   # Integration tests
uv run pytest tests/path/to/test.py -k "name"     # One file or pattern
```

- `tests/unit/` has no external dependencies.
- `tests/integration/` writes to and deletes from a real Postgres (start it with `docker compose up -d db`). The suite always runs against a separate database: the `.env` database's name with `_test` appended (`ai_reviewer_test` locally), or `TEST_DATABASE_URL` when set. The first integration test creates and migrates it, and rebuilds it when it holds a migration from another branch. The tests refuse any database whose name doesn't end in `_test`, so they never touch the dev data. CI runs the whole suite after the unit tests, in the same job, against a Postgres service.
- Integration tests share that database and run in parallel, so never assume an empty table: create rows with fresh `uuid4` ids and delete them in the fixture's teardown.
- Shared fixtures and helpers (`data_path`, `create_test_file_document_from_path`) are in `tests/conftest.py`. Reuse them before writing new ones.
- Never call a real LLM in a test. Use LangChain's `GenericFakeChatModel` (see `tests/unit/services/chat/test_thread_state.py`) or patch the call.
- Mark async tests with `@pytest.mark.asyncio`.

### Frontend Tests (Vitest)

Vitest runs in jsdom and needs Node 22.22.2 or newer (`frontend/.nvmrc`). CI runs it on every PR.

```bash
cd frontend && pnpm test                              # All tests
cd frontend && pnpm test lib/workflow-state.test.ts   # One file
cd frontend && pnpm test -t "name of the test"        # Tests matching a name
```

- Tests live next to the module they cover, as `*.test.ts`, or `*.test.tsx` when the test renders. `lib/test-render.tsx` has the helpers for mounting a component (`renderInto`, `testQueryClient`, `withQueryClient`).
- Import `describe`/`it`/`expect`/`vi` from `vitest` explicitly; globals are off.
- The `@/` path alias resolves as it does in the app.

#### Test behaviour, not presentation

Frontend tests protect **logic and business rules**: derivation and transformation, state transitions, validation, filtering and sorting, API response mapping, and the decisions a hook, store or component makes.

- **Never test a component that has no logic.** A component that only turns props into markup needs no test. Never write one just to raise coverage.
- **Prefer a plain function or hook when the logic already lives in one,** or when moving it out is small and makes the code clearer. Test that instead of rendering.
- **Render when that's the honest way to reach the behaviour:** a flow driven by user events, effects, queries or a hook. Never restructure a component only to avoid rendering it.
- **Assert on outcomes, never on looks.** A rendered test checks what the logic produced: the arguments a callback received, the requests made, the state reached, whether an action is allowed. Visible text or an attribute may serve as the handle for that outcome, but never assert on styling, layout, icons or wording for its own sake, and never use snapshots.

```tsx
// ✅ Rendered, asserting on behaviour: what the dialog asks to download
await click('Link comments to Draft Detective');
await click('Download');
expect(onDownload).toHaveBeenCalledWith('comments-with-links', { includeEdits: true });

// ❌ Rendered, asserting on presentation
expect(container.querySelector('button')?.className).toContain('bg-muted');
expect(container.textContent).toContain('A long sentence about what the assessment does.');
```

### Evaluations (Inspect AI)

[Inspect AI](https://inspect.ai-safety-institute.org.uk/) evals live under `evals_inspectai/e2e/`, one directory per workflow with a `dataset.yaml` and a task module. They run each workflow end to end against the API, the same way a user triggers it, so **the backend must be running** (`uv run dev.py`).

```bash
uv run inspect eval evals_inspectai/e2e/figures_tables_check/figures_tables_check_e2e.py                 # Full suite
uv run inspect eval evals_inspectai/e2e/figures_tables_check/figures_tables_check_e2e.py --sample-id=1   # One sample (1-indexed)
uv run inspect view                                                                                      # Results dashboard
```

Add `--epochs=3` to repeat a sample (to check determinism) or `--limit=5-10` to run a range. `evals_inspectai/README.md` lists the suites and how to choose the workflow model.

- **Always drive the API through the endpoints the frontend uses.** Never add an eval-only endpoint or shortcut: an eval on its own path stays green while the user's path is broken. Before adding or changing a helper in `evals_inspectai/common/api_client.py`, check what the frontend does for the same action and copy that sequence.
- **Always keep fixtures as inspectable text.** Dataset inputs are markdown, with figures as PNG references (`![](files/figures/<name>.png)`) that `inline_local_images` in `evals_inspectai/common/loaders.py` inlines at upload. Never commit DOCX fixtures: nobody can review a binary in a diff. Draw new figures with `evals_inspectai/files/figures/charts.py`. Use a DOCX only when a sample needs Word-only behaviour, such as declared crops.

---

## Git Conventions

### Never commit or open a PR unless asked

Finish the work, confirm it passes the checks above, then wait. The user reviews changes before they go into git.

### Commit messages

Always use [Conventional Commits](https://www.conventionalcommits.org/): `<type>(<scope>): <description>`. Common types: `feat`, `fix`, `chore`, `refactor`, `test`, `docs`, `style`, `perf`, `ci`, `build`.

```bash
# ✅ Correct
feat(revisions): add revision system for main document replacement
fix(upload): validate single main file per revision
test(revisions): add unit tests for create_new_revision

# ❌ Incorrect
update files
fix bug
WIP
```

### Pull requests

Always target `dev` unless the user names another base branch. Always fill in `.github/pull_request_template.md` for the description.

Every pull request carries exactly one release label, and a required check enforces it. New pull requests default to `release:patch`. Use `release:minor` for a new feature, `release:major` for a breaking change and `norelease` for work that changes nothing a user or deployer sees (CI, tests, docs). Never edit the version in `pyproject.toml`, `uv.lock` or `frontend/package.json`: the release workflow sets all three. `CONTRIBUTING.md` explains the release flow.
