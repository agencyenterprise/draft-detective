# Project instructions

## Use `uv` for running Python scripts

This project uses `uv` for Python dependency management and script execution. Always use `uv` instead of raw `python`, `pip`, or `pytest` commands.

```bash
# ✅ Correct - use uv run
uv run python script.py
uv run dev.py
uv run pytest tests/ -k "test_name"
uv add package-name

# ❌ Incorrect - don't use raw python or pip
python script.py
.venv/bin/python script.py
python -m pytest
pip install package-name
```

## Use `pnpm` for frontend commands

The frontend uses `pnpm` as the package manager. Run all frontend commands from the `frontend/` directory.

```bash
# ✅ Correct
cd frontend && pnpm install
cd frontend && pnpm dev
cd frontend && pnpm build

# ❌ Incorrect
npm install
yarn dev
```

## TypeScript types are generated using Hey API (@hey-api/openapi-ts)

Whenever the backend API changes (endpoints, request/response types, schemas, etc.), you **must** run `pnpm run openapi-generate` from the `frontend/` directory to update the generated types.

- **Never manually edit** files in `frontend/lib/generated-api/` - they are auto-generated
- **Always regenerate** after backend API changes to keep frontend types in sync
- The backend server must be running for generation to succeed

## Avoid useEffect in React

Avoid using `useEffect` whenever possible. Prefer alternatives that are more declarative and less error-prone:

- **Derived state**: Compute values during render instead of syncing with `useEffect`
- **Event handlers**: Handle side effects in response to user actions, not in `useEffect`
- **useMemo/useCallback**: For expensive computations or stable references
- **React Query/SWR**: For data fetching instead of `useEffect` + `useState`
- **Key prop**: Reset component state by changing the `key` instead of `useEffect`

```tsx
// ❌ Avoid - useEffect for derived state
const [fullName, setFullName] = useState("");
useEffect(() => {
  setFullName(`${firstName} ${lastName}`);
}, [firstName, lastName]);

// ✅ Correct - compute during render
const fullName = `${firstName} ${lastName}`;

// ❌ Avoid - useEffect for data fetching
useEffect(() => {
  fetchData().then(setData);
}, [id]);

// ✅ Correct - use React Query or similar
const { data } = useQuery({ queryKey: ["data", id], queryFn: fetchData });
```

## Database migrations - never run Alembic yourself

When making changes to database models in `lib/models/`:

- **Only modify the model file** - do not run migration commands
- **Remind the user** to run Alembic to generate and apply migrations
- The user will run: `uv run alembic revision --autogenerate -m "description"` and `uv run alembic upgrade head`

## Use SQLAlchemy 2.0 style expressions

Always use SQLAlchemy 2.0 style `select()` statements, not the legacy 1.x `query()` pattern.

When referencing SQLModel columns in query expressions (`.where()`, `.filter()`, `.join()`, etc.), use the `col()` helper from SQLModel to ensure proper type checking. This tells the type checker that model fields are column expressions, not plain Python types.

```python
# ✅ Correct - SQLAlchemy 2.0 style with col() for type safety
from sqlalchemy import select
from sqlalchemy.orm import Session
from sqlmodel import col

def get_files(db: Session, project_id: uuid.UUID) -> Sequence[File]:
    stmt = select(File).where(col(File.project_id) == project_id)
    return db.execute(stmt).scalars().all()

def get_files_by_ids(db: Session, file_ids: list[uuid.UUID]) -> Sequence[File]:
    stmt = select(File).where(col(File.id).in_(file_ids))
    return db.execute(stmt).scalars().all()

# ❌ Incorrect - legacy 1.x style
def get_files(db: Session, project_id: uuid.UUID):
    return db.query(File).filter(File.project_id == project_id).all()

# ❌ Incorrect - missing col() causes type errors
def get_files(db: Session, project_id: uuid.UUID):
    stmt = select(File).where(File.project_id == project_id)  # mypy error: bool
    return db.execute(stmt).scalars().all()
```

## Use Pydantic BaseModel, not dataclass

Always use Pydantic `BaseModel` for data models. Never use `@dataclass`.

```python
# ✅ Correct
from pydantic import BaseModel, Field

class DocumentMetadata(BaseModel):
    title: str = Field(description="Document title")
    page_count: int

# ❌ Incorrect
from dataclasses import dataclass

@dataclass
class DocumentMetadata:
    title: str
    page_count: int
```

## Running the development server

Start the full development environment with:

```bash
uv run dev.py
```

This starts both the FastAPI backend and the Next.js frontend.

## Running tests

```bash
# Run all Python tests
uv run pytest

# Run specific test file or pattern
uv run pytest tests/path/to/test.py -k "test_name"
```
