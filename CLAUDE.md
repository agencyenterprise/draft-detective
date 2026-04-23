# Project Instructions

## Project Overview

This is an AI-powered document review system with a Python backend (FastAPI + LangChain) and Next.js frontend. The system uses agent-based workflows to analyze documents for claims, citations, and references.

---

## Quick Reference

### Running Commands

```bash
# Backend (always use uv)
uv run dev.py                    # Start full dev environment
uv run pytest                    # Run tests
uv run pytest tests/ -k "test"   # Run specific tests

# Frontend (always use pnpm)
cd frontend && pnpm install
cd frontend && pnpm dev
cd frontend && pnpm run openapi-generate  # Regenerate API types
```

---

## Python Backend Rules

### Use `uv` for running Python scripts

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

### Do NOT create `__init__.py` files

This codebase uses Python 3.3+ implicit namespace packages. Do not create `__init__.py` files in new directories - they are not used anywhere in `lib/` or `api/`.

```bash
# ✅ Correct - just create the module files
lib/workflows/new_workflow/
├── state.py
├── graph.py
├── manifest.py
└── nodes/
    └── process.py

# ❌ Incorrect - don't add __init__.py
lib/workflows/new_workflow/
├── __init__.py          # Don't create this
├── state.py
└── nodes/
    ├── __init__.py      # Don't create this either
    └── process.py
```

### Never use lazy imports inside methods

Always place imports at the top of the file. Lazy imports (imports inside functions or methods) are forbidden except when required to break a circular import or when there is an absolute technical necessity. Any such exception must be explained with a comment.

```python
# ✅ Correct - imports at the top of the file
from lib.services.users import UserService
from lib.models.document import Document

def process(doc: Document) -> None:
    service = UserService()
    ...

# ❌ Incorrect - lazy import inside a function
def process(doc):
    from lib.services.users import UserService  # don't do this
    service = UserService()
    ...

# ✅ Acceptable exception - circular import that cannot be resolved otherwise
def process(doc):
    # Imported here to avoid circular import between lib.services.users and lib.services.documents
    from lib.services.users import UserService
    service = UserService()
    ...
```

### Use Pydantic BaseModel, not dataclass

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

### Use SQLAlchemy 2.0 style expressions

Always use SQLAlchemy 2.0 style `select()` statements, not the legacy 1.x `query()` pattern.

When referencing SQLModel columns in query expressions (`.where()`, `.filter()`, `.join()`, etc.), use the `col()` helper from SQLModel to ensure proper type checking.

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

### Database migrations - never run Alembic yourself

When making changes to database models in `lib/models/`:

- **Only modify the model file** - do not run migration commands
- **Remind the user** to run Alembic to generate and apply migrations
- The user will run: `uv run alembic revision --autogenerate -m "description"` and `uv run alembic upgrade head`

### Type Safety

```python
# Always use type hints
from typing import List, Optional, Union
from pydantic import BaseModel

def process_documents(files: List[File], config: Optional[ProcessingConfig] = None) -> DocumentResult:
    pass

# Use TypedDict for structured data (especially workflow state)
from typing import TypedDict
class WorkflowState(TypedDict, total=False):
    documents: List[Document]
    results: Optional[ProcessingResult]
```

### Verify with mypy before finishing any Python change

**The baseline is zero mypy errors.** Any error mypy reports is new — introduced by the current work. The `backend.yml` CI workflow runs `uv run mypy .` on every PR and will block merges on failure, so catch it locally first.

- **After any edit to a `.py` file (backend, tests, evals):** run `uv run mypy <file-or-package>` for the touched paths.
- **Before concluding a task** that made Python changes — even for what looks like a trivial fix — run `uv run mypy .` once to catch knock-on effects in untouched files (union narrowing, SQLAlchemy `Select[...]` reassignments, and structured-output agent return types are common sources).
- **Never hand back work with mypy errors.** "It works at runtime" isn't enough — if mypy is red, fix it or explain to the user why you can't before concluding.
- **Narrow `# type: ignore` comments only.** Prefer `# type: ignore[specific-code]` over bare `# type: ignore`, and add a brief inline comment when the reason isn't obvious. Reach for an ignore only after trying to express the invariant in the type system (narrowing via `isinstance`, `cast()`, or a fixed annotation).
- If mypy is slow or misbehaving, `rm -rf .mypy_cache` and retry before assuming a real error.

```bash
# ✅ Correct
uv run mypy lib/services/projects.py         # after editing one file
uv run mypy lib/services lib/workflows       # after editing a subsystem
uv run mypy .                                # final check before handing back

# ❌ Incorrect
# Handing back Python changes without running mypy
# Adding bare `# type: ignore` to silence an error you didn't understand
```

### Async/Await Patterns

```python
# Prefer async/await for I/O operations
async def process_with_llm(content: str) -> Result:
    llm_response = await llm.ainvoke(content)
    return Result(data=llm_response)

# Use asyncio.gather for parallel operations
results = await asyncio.gather(
    process_chunk_1(chunk1),
    process_chunk_2(chunk2)
)
```

### Error Handling

```python
# Use specific exception types
class DocumentProcessingError(Exception):
    def __init__(self, message: str, document_id: str):
        self.document_id = document_id
        super().__init__(message)

# Handle errors at appropriate levels
try:
    result = await process_document(doc)
except DocumentProcessingError as e:
    logger.error(f"Failed to process document {e.document_id}: {e}")
    raise HTTPException(status_code=422, detail=str(e))
```

### Project Structure

```
lib/
├── agents/          # Individual AI agents (claim_extractor, etc.)
├── workflows/       # LangGraph workflow definitions
├── services/        # Business logic services
├── models/          # Database models
└── config/          # Configuration modules

api/                 # FastAPI application
```

---

## Frontend Rules

### Use `pnpm` for frontend commands

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

### TypeScript types are generated using Hey API (@hey-api/openapi-ts)

Whenever the backend API changes (endpoints, request/response types, schemas, etc.), you **must** run `pnpm run openapi-generate` from the `frontend/` directory to update the generated types.

- **Never manually edit** files in `frontend/lib/generated-api/` - they are auto-generated
- **Always regenerate** after backend API changes to keep frontend types in sync
- The backend server must be running for generation to succeed

### Avoid useEffect in React

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

### TypeScript Best Practices

```tsx
// Use proper TypeScript interfaces
interface WizardState {
  currentStep: number;
  mainDocument: File | null;
  supportingDocuments: File[];
  isProcessing: boolean;
  analysisResults: AnalysisResult | null;
}

// Type component props explicitly
interface FileUploadProps {
  onUpload: (files: File[]) => void;
  maxFiles?: number;
  accept?: string[];
}
```

### React Patterns

```tsx
// Use React 19 patterns - prefer function components
function DocumentViewer({ document }: { document: Document }) {
  const [isLoading, setIsLoading] = React.useState(false);
  const { analysis, error, refresh } = useDocumentAnalysis(document.id);

  if (error) return <ErrorDisplay error={error} />;
  if (isLoading) return <LoadingSpinner />;

  return <DocumentDisplay document={document} analysis={analysis} />;
}

// Use React Context for shared state
const WizardContext = React.createContext<WizardContextType | undefined>(
  undefined
);

export function useWizard() {
  const context = React.useContext(WizardContext);
  if (!context) {
    throw new Error("useWizard must be used within WizardProvider");
  }
  return context;
}
```

### UI/UX Guidelines

- Use shadcn/ui components for consistency
- Implement proper loading states and error boundaries
- Ensure accessibility (ARIA labels, keyboard navigation)
- Use Tailwind CSS utility classes, avoid custom CSS when possible

---

## Code Quality Standards

### File Organization & Size

- **Target file size: ~100-200 lines** (current codebase averages 83-104 lines)
- **Maximum file size: 300 lines** (exceptions for configuration, migrations, complex workflows)
- **Principle over rules**: Prioritize logical cohesion and single responsibility over strict line counts
- Keep functions focused and testable (max 20 lines preferred)

#### When to split files:

- Multiple classes/functions with different responsibilities
- Mixed concerns (business logic + configuration + utilities)
- Difficulty understanding the file's purpose at a glance

#### When larger files are acceptable:

- Database models with many fields (SQLModel classes)
- Configuration files with extensive settings
- Complex workflow definitions that need to stay together
- Single-purpose modules with high internal cohesion

### SOLID Principles

- **Single Responsibility**: Each class/function should have one reason to change
- **Open/Closed**: Use composition and dependency injection over inheritance
- **Liskov Substitution**: Ensure subtypes are substitutable for base types
- **Interface Segregation**: Create focused, role-based interfaces
- **Dependency Inversion**: Depend on abstractions, not concretions

---

## Testing

### Unit / Integration Tests

```bash
# Run all Python tests
uv run pytest

# Run specific test file or pattern
uv run pytest tests/path/to/test.py -k "test_name"
```

```python
# Use pytest with async support
import pytest

@pytest.mark.asyncio
async def test_document_processing():
    processor = DocumentProcessor()
    result = await processor.process(mock_document)
    assert result.chunks is not None
    assert len(result.chunks) > 0

# Mock external dependencies
@pytest.fixture
def mock_llm():
    with patch('lib.agents.claim_extractor.init_chat_model') as mock:
        mock.return_value.ainvoke.return_value = MockResponse()
        yield mock
```

### Evaluations (Inspect AI)

This project uses [Inspect AI](https://inspect.ai-safety-institute.org.uk/) for LLM agent evaluations. Eval tasks live under `evals_inspectai/` in two flavors:

- **`evals_inspectai/e2e/`** — End-to-end evals that hit the running API server (backend must be running).
- **`evals_inspectai/internal/`** — Internal evals that import and invoke agents directly (no server needed).

Each workflow has its own eval directory with a dataset file (`dataset.json` or `dataset.jsonl`) and a task definition module.

```bash
# Run a full eval suite for a workflow
uv run inspect eval evals_inspectai/e2e/reference_validation/reference_validation_e2e.py

# Run a specific sample by ID (1-indexed)
uv run inspect eval evals_inspectai/e2e/figures_tables_check/figures_tables_check_e2e.py --sample-id=1

# Run a specific sample multiple times (useful for testing determinism)
uv run inspect eval evals_inspectai/e2e/figures_tables_check/figures_tables_check_e2e.py --sample-id=1 --epochs=3

# Run a range of samples
uv run inspect eval evals_inspectai/e2e/reference_validation/reference_validation_e2e.py --limit=5-10

# View eval results in the Inspect AI dashboard
uv run inspect view
```

**Important:** E2E evals require the backend server to be running (`uv run dev.py`).

---

## Common Anti-patterns to Avoid

### Python

- Don't use `import *`
- Don't use lazy imports inside methods — place all imports at the top of the file; exceptions (circular imports) must be explained in a comment
- Avoid deeply nested callback functions
- Don't mix sync/async code patterns
- Avoid large functions (>20 lines)
- Don't use mutable default arguments
- Don't use `@dataclass` - always use Pydantic `BaseModel` instead
- Don't create `__init__.py` files - use implicit namespace packages

### Frontend

- Don't mutate props directly
- Avoid using index as key in lists
- Don't use nested ternary operators
- Avoid large useEffect dependencies arrays
- Don't bypass TypeScript with `any` type

---

## Git Conventions

### Commits and Pull Requests

Never create commits or open pull requests unless the user explicitly asks. Finish the implementation, confirm it works, then wait for instruction before touching git.

### Commit Messages

Use [Conventional Commits](https://www.conventionalcommits.org/) for all commit messages. The format is:

```
<type>(<scope>): <description>
```

Common types: `feat`, `fix`, `chore`, `refactor`, `test`, `docs`, `style`, `perf`, `ci`, `build`.

```bash
# ✅ Correct
feat(revisions): add revision system for main document replacement
fix(upload): validate single main file per revision
test(revisions): add unit tests for create_new_revision
chore(deps): update langchain to 0.3.x
refactor(workflow-runs): make revision parameter required

# ❌ Incorrect
update files
fix bug
WIP
```

---

## Pull Request Descriptions

When creating pull requests, **always target the `dev` branch** unless the user explicitly specifies a different base branch.

When creating pull request descriptions, create the sections of "Summary," "Motivation," "What's Changed," and "Risks and Mitigations." Separate "What's Changed" into backend and frontend changes and list all the files that have changed and why these changes were made. Keep the PR description fairly short at no more than 1000 words.
