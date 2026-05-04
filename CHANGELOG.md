# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).


## [v0.5.34] - 2026-05-04

### Added
- Added `reference_validation_v2` with red/yellow/green severity tiers and refined field-match rules, defaulting the v2 agent to `gpt-5.5`.
- Added a dark mode option with a profile-dropdown toggle that follows OS preference by default and persists user overrides via `next-themes`.
- Added MCP support for human-approval workflows via an `approve_human_steps` argument to the `run_workflow` tool.
- Added Inspect AI evals (internal and e2e) for `claim_reference_validation_v2`, sharing a single dataset file.
- Added a canonical optional `suggested_action` (markdown) field to every issue emitted by analysis workflows and surfaced it in the issue card UI.
- Added tabbed MCP install instructions for Claude Code, Codex, and Opencode, plus a "How to use" section with sample prompts.

### Changed
- Made identifiers always optional in reference validation, broadened author acceptance to include institutional names, and accepted any published edition year for books/book chapters within existing tolerance.
- Upgraded most agents to `gpt-5.4`, bumped `SimpleDeepAgent` to `gpt-5.5`, switched `DocumentChunker` to `gpt-5.4-mini`, and removed unused legacy model entries from the registry.
- Made the `reference_downloader` workflow’s `references` input optional and defaulted it to all extracted references without a matched supporting file when omitted.
- Moved the "View on GitHub" link into a combined bottom-right version + GitHub badge and linked the version label to the changelog.
- Marked the Reproducibility Check workflow as beta so the UI shows the Beta badge and tooltip.
- Removed the user-facing list of available MCP tool names from the `/mcp` page.

### Fixed
- Fixed e2e eval solver timeouts so they are recorded as sample errors instead of crashing the eval, and allowed e2e evals to continue when up to 20% of samples fail.
- Fixed CI permissions by granting the `claude-review` workflow write access to pull requests and issues.

### Removed
- Removed the orphan `inference_validation` v1 enum value and its frontend icon mapping.
- Removed the legacy `tests/evals/llm/` eval test suite and its supporting backend instrumentation and frontend `/evals` viewer.


## [v0.5.33] - 2026-04-27

### Added
- Added 3 new eval cases to the reference validation dataset to improve coverage of real-world reference types.
- Added nullable `start_line` / `end_line` columns for issues and included `start_line` / `end_line` in `DocumentIssue` (including in the hash ID).
- Added a `find_line_range_by_chunks` helper to `lib/services/chunk_line_matcher.py`.
- Added a new `DocumentMarkdownRenderer` for rendering full markdown and highlighting blocks by `[start_line, end_line]` overlap.
- Added a new `lib/services/docx/paragraph_line_mapper.py` and new tests including `test_issue_persistence_resolve_location.py` and `test_paragraph_line_mapper.py`.
- Added a backend CI `typecheck` job that runs `uv run mypy .` on PRs.

### Changed
- Stopped auto-triggering chunk splitting on project creation and main-document replacement in the frontend.
- Migrated document rendering, issue location, and Word export from chunk indices to line ranges.
- Updated issue persistence to resolve and persist both line ranges and chunk indices for every issue.
- Updated project and issues APIs to expose `start_line` / `end_line` and to serve the main-document markdown for the explorer.
- Updated multiple workflows to emit line ranges where natively available and drop redundant in-workflow conversion to chunk indices.
- Migrated docx export to locate issues by paragraph-marker-derived line ranges and updated the MCP `export_project_docx` tool to the new generator.
- Dropped the docx export cache layer and collapsed docx generation to a single `generate_docx` that always regenerates with a unique UUID filename.
- Renamed `lib/workflows/simple_deep_agent/types.py` to `agent_types.py` and updated 5 import sites.
- Bumped `uuid` from 13.0.0 to 14.0.0 in `/frontend`.
- Bumped `lxml` from 6.0.2 to 6.1.0.
- Bumped `python-dotenv` from 1.2.1 to 1.2.2.
- Updated mypy configuration and dev dependencies, and ignored `.mypy_cache/` in `.gitignore`.

### Fixed
- Completed incremental mypy cleanup from 273 errors in 78 files to `Success: no issues found in 342 source files`.
- Switched required secret loading in `lib/config/env.py` from `os.getenv()` to `os.environ[...]` so it fails earlier with a clearer error.
- Fixed agents calling a non-existent `PromptValue.text` attribute by switching to `PromptValue.to_string()` in 6 agents.
- Fixed `ValidatedDocument` in `lib/agents/models.py` by replacing an impossible `Field(default_factory=DocumentMetadata)` and simplifying `__init__` branching.
- Fixed a `File` name collision in `lib/api/mcp.py` exposed by adding a type-annotated revision map.
- Split several SQLAlchemy `stmt` variables into named-per-query variables to avoid reassignment across different `Select[tuple[...]]` types.

### Security
- Updated `lxml` to 6.1.0, which fixes a possible external entity injection (XXE) vulnerability in `iterparse()` and `ETCompatXMLParser`.
- Updated `uuid` to 14.0.0, which fixes GHSA-w5hq-g745-h8pq involving out-of-bounds writes when an invalid offset is provided.

### Removed
- Removed the now-unused `useResultsCalculations` hook from the frontend.
- Removed the chunk-based `DocumentReconstructor` and deleted now-unused chunk-based frontend components and the docx export cache layer.
- Removed `lib/services/docx/chunk_mapper.py`.
- Deleted dead or broken backend code including `lib/workflows/chunk_iterator.py`, `lib/services/llm_text_splitter.py`, `lib/database_utils.py`, `lib/agents/reference_matcher.py`, `lib/agents/claim_needs_substantiation_checker.py` (and its eval + dataset), and `lib/agents/section_classifier.py`.


## [v0.5.32] - 2026-04-21

### Added
- Added a Claim Reference Validation V2 workflow that uses a single tool-equipped agent per document section to validate citations.
- Added caching for `HUMAN_APPROVAL` so projects with a prior approved run on any revision auto-complete subsequent runs.
- Added a Postgres-backed, Fernet-encrypted OAuth `client_storage` for MCP Google and Azure providers to support multi-pod deployments.
- Added a helper to detect whether a workflow run has completed on any revision.
- Added cleanup orchestration for project file deletion that also unlinks reference matches and clears related ReferenceDownloader fetch results.

### Changed
- Changed the workflow-type selector to honor the category ordering defined in `categories.py` regardless of experimental status.
- Changed the References tab fetch-results visibility rule to show whenever a fetch was attempted except for manual uploads.
- Changed assessment naming and descriptions to use plain language, including renaming the “Technical Compliance” category to “Editorial and Style Review” and renaming several assessments.
- Changed frontend user-facing terminology from “analysis/analyses” to “assessment/assessments” and from “experimental” to “beta,” and updated the homepage title and intro copy.
- Bumped `langsmith` from 0.6.6 to 0.7.31.
- Bumped `langchain-text-splitters` from 1.1.1 to 1.1.2.
- Bumped `langchain-openai` from 1.1.12 to 1.1.14.
- Bumped `mako` from 1.3.10 to 1.3.11.
- Bumped `authlib` from 1.6.9 to 1.6.11.

### Fixed
- Fixed ReferenceDownloader subset fetch runs wiping prior fetch results so previously stored outcomes are preserved.
- Fixed failed fetch-from-web outcomes being hidden in the References tab due to fetch-results visibility rules.
- Fixed stale ReferenceDownloader “Source Found” indicators after an auto-fetched file is manually removed.
- Fixed MCP re-auth hanging on repeat use in multi-pod deployments by persisting OAuth state in Postgres.
- Fixed doc explorer sidebar loading UI by replacing empty skeleton cards with a spinner and tooltip next to the issue count.

### Security
- Updated `authlib` to 1.6.11, including a fix for a CSRF vulnerability in the Starlette OAuth client when a cache is configured.
- Updated `mako` to 1.3.11, including a fix for a directory traversal bypass in `TemplateLookup` with double-slash URI prefixes.


## [v0.5.31] - 2026-04-17

### Added
- Added `MODEL_API_KEYS` env var (JSON dict) to assign a specific API key per model name, with per-model key fallback when no user-provided key exists.
- Added `get_model_api_key()` helper and 7 unit tests for per-model API key resolution.
- Added `.claude/launch.json` to configure backend and frontend dev server launch with auto port assignment.
- Added `.worktreeinclude` to specify env files copied into Claude worktrees.
- Added 17 new test cases to the reference validation eval dataset and introduced an optional `note` field for some cases.

### Changed
- Rewrote the reference validator agent’s system prompt as a clear six-step procedure with targeted rules for common failure modes.
- Updated `dev.py` to read `PORT` from an environment variable.
- Updated `.gitignore` to exclude Claude worktree/project artifacts and use `settings.local.json` instead of `settings.json`.
- Bumped default `RATE_LIMITER_CHECK_EVERY_N_SECONDS` from `0.2` to `0.25`.
- Bumped `python-multipart` from `0.0.22` to `0.0.26`.
- Experimental analysis types are now shown automatically for users who have opted into experimental features via profile settings.

### Fixed
- Capped DB pool pressure in the Postgres rate limiter by adding a per-`bucket_key` in-process `asyncio.Lock` around `PostgresRateLimiter._aconsume`.

### Removed
- Removed the "Show experimental" checkbox toggle from the analysis type selection UI.
- Removed the `AGENTS.md` symlink that pointed to `CLAUDE.md`.


## [v0.5.30] - 2026-04-15

### Added
- Added a `WorkflowCompletionError` and a `check_workflow_errors()` utility to surface workflow completion errors as sample errors in Inspect AI evals.
- Added tests covering Azure Entra ID upstream claims scenarios for MCP email/name resolution.
- Added tests to ensure `VectorStoreService` uses a shared SQLAlchemy async engine and that multiple instances share one engine.
- Added tests for the checkpointer pool behavior, including concurrency and reopen/close scenarios.

### Changed
- Updated LangChain ecosystem packages and Langfuse to newer versions.
- Bumped pytest from 9.0.2 to 9.0.3.
- Bumped pillow from 12.1.1 to 12.2.0.
- Updated `VectorStoreService` to reuse the shared SQLAlchemy `async_engine` and changed its constructor to take only `openai_api_key`.
- Changed the langgraph checkpointer to use a bounded module-level psycopg pool and added explicit SQLAlchemy engine pool caps (`pool_size=8`, `max_overflow=3`).
- Updated FastAPI lifespan shutdown to close the checkpointer pool.

### Fixed
- Fixed MCP auth crashes for Azure Entra ID users by falling back to `upstream_claims` for email/name resolution and validating email format.
- Fixed incorrect entries in the `reference_validation` eval dataset (including expected values) and corrected the internal eval dataset file path (`.jsonl` to `.json`).
- Fixed eval behavior so workflow completion errors (e.g., rate limits/timeouts) are recorded as errors instead of being scored as incorrect. 

### Security
- Updated dependencies including LangChain ecosystem packages and Langfuse for security-related upgrades.
- Updated pytest to 9.0.3, which includes a fix for use of an insecure temporary directory (CVE-2025-71176).


## [v0.5.29] - 2026-04-13

### Added
- Added a multi-worker-safe Postgres-backed token bucket rate limiter for LangChain and the Jina API, with tuning knobs exposed via environment variables.
- Added a new `rate_limiter_buckets` table and migration to support the Postgres-backed rate limiter.
- Added grep-friendly logging for failed chat-model and embedding calls including model, provider, endpoint, workflow stage, and workflow/project IDs, with a distinct `LLM_RATE_LIMIT` prefix for HTTP 429 errors.
- Added unit tests for the LLM error logger and an eval test case for reference validation of a non-existent URL.

### Changed
- Removed `revision` as a client-facing input parameter on workflow start endpoints so workflows always run against `project.current_revision`, while read endpoints that accept a revision remain unchanged.
- Reordered analysis categories to: Citation Check → Substantive Review → Technical Compliance → Language, with Research & Writing Assistant kept at the end.
- Updated the reference validator procedure to require fetching/verifying URLs before trusting them and to search for exact title/authors when a URL is dead.
- Replaced the Jina API limiter from `aiolimiter.AsyncLimiter` to the new `PostgresRateLimiter`.

### Fixed
- Fixed `POST /api/workflows/start` to override `config.revision` with `project.current_revision` so workflow context targets the correct revision.
- Fixed reference validator false negatives where non-existent URLs were marked valid based on URL pattern alone.

### Removed
- Removed the `aiolimiter` dependency.
- Removed `revision` from workflow config OpenAPI schema and generated frontend workflow config types.


## [v0.5.28] - 2026-04-10

### Added
- Stored LLM conversation messages for each reference validation in the workflow state.
- Added a reusable AgentMessagesDialog component to view agent messages in a dialog.
- Added a “Messages” button on completed reference validation results to open the agent messages dialog.
- Added the `MCP_CIMD_ENABLED` environment variable to control whether CIMD is enabled for MCP OAuth providers.

### Changed
- Made CIMD enablement for Google and Azure MCP auth providers configurable via `MCP_CIMD_ENABLED` (default `false`).
- Updated the `.env.template` to include a documented `MCP_CIMD_ENABLED` entry.
- Updated MCP auth unit tests to include `MCP_CIMD_ENABLED` in mock configs and added tests verifying `enable_cimd=True` is forwarded to Google and Azure providers.

### Fixed
- Fixed issues from old revisions not showing up in the UI when using the revision switcher.
- Removed unnecessary archival of issues during new revision creation.

### Security
- Bumped `next` from 15.5.14 to 15.5.15 in `/frontend`.


## [v0.5.27] - 2026-04-10

### Added
- Introduced a revision system that allows replacing the main document and re-running analyses while preserving and archiving prior results.
- Added API endpoints to create and list project revisions.
- Added an inline “Replace main document” dialog and related UI updates, including a revision badge on project cards.
- Added MCP tools `export_project_docx` and `list_projects`.
- Added MCP tools `list_project_files`, `remove_reference_file`, and `get_tus_upload_credentials`.

### Changed
- Moved reference review and human approval out of the new-project wizard into the project results experience (References tab), removing `step=3` URL support and always routing to the project after starting analysis.
- Updated workflow type selection UI to load types via `useWorkflowTypes`, render by category, and add a “Show experimental” control.
- Promoted the Figures & Tables Check, Document Structure, Advocacy & Tone, and About This (GER) workflows to stable by removing the experimental flag.
- Added exclusion logic so abbreviation/acronym tables in dedicated sections are not flagged by the figures & tables check.
- Added 6 new figures & tables check e2e eval cases.
- Added a regression eval case for reference validation and documented Inspect AI eval usage in AGENTS.md.
- Bumped dependencies: cryptography (46.0.4→46.0.6 and 46.0.6→46.0.7), langchain-core (1.2.19→1.2.22 and 1.2.22→1.2.28), lodash (4.17.21→4.18.1), next (15.5.9→15.5.14), pyjwt (2.10.1→2.12.0), pygments (2.19.2→2.20.0), pyasn1 (0.6.2→0.6.3), pillow (12.1.0→12.1.1), requests (2.32.5→2.33.0), deepdiff (8.6.1→8.6.2), and aiohttp (3.13.3→3.13.4).

### Fixed
- Sanitized C0/C1 control characters before sending text to the OpenAI API to prevent intermittent 400 errors in the Chunk Splitting workflow, and consolidated stripping logic into a shared utility.
- Reduced non-deterministic reference validator title suggestions by instructing the agent to prefer the on-page content headline over metadata titles.
- Suppressed the workflow progress toast while a run is waiting on human approval.
- Updated tests to include new MCP tool names and adjusted mocks and added tests for the revision system.

### Security
- Restricted Claude GitHub Actions workflows to run only for repo contributors with `OWNER`, `MEMBER`, or `COLLABORATOR` association.
- Updated cryptography to 46.0.7, including a security fix for non-contiguous buffers that could lead to buffer overflow (CVE-2026-39892).
- Updated cryptography to 46.0.6, including a security fix related to name constraints verification with wildcard DNS SANs (CVE-2026-34073).
- Updated pyasn1 to 0.6.3, including a nesting depth limit to prevent stack overflow from deeply nested structures (CVE-2026-30922).
- Updated requests to 2.33.0, including a security change for `requests.utils.extract_zipped_paths` (CVE-2026-25645).
- Updated deepdiff to 8.6.2 to address CVE-2025-58367.
- Updated next to 15.5.14, including a security fix to prevent request smuggling in rewrites (CVE-2026-29057).

### Removed
- Removed the experimental tag (`is_experimental`) from four workflows that were promoted to stable.
- Removed the wizard reference review step (`StepReferences`) and obsolete deep links to `step=3`.


## [v0.5.26] - 2026-04-07

### Added
- Added category grouping for workflow/analysis type selection in the UI and API.
- Added a new `lib/workflows/categories.py` as a single source of truth defining five workflow categories, their display order, and workflow membership.
- Added `WorkflowCategoryOrder` and `WorkflowTypesResponse` models, and updated `get_workflow_types_for_user` to return workflow descriptions with category slugs plus ordered category configuration.
- Added category headers, an inline “show experimental” toggle, and a live `(selected/total)` counter to the workflow type selector UI.

### Changed
- Changed the `/api/workflow-types` endpoint to return the new `WorkflowTypesResponse` shape.
- Changed workflow ordering to be controlled by `categories.py` instead of an `order` field in workflow manifests.
- Changed MCP server code and unit tests to reflect the new workflow types response structure.
- Changed frontend generated API types and the `use-workflow-types` hook to match and expose the new categories data.
- Changed multiple frontend components to pass a `categories` prop down to `WorkflowTypeSelector`.
- Changed `workflow-type-checkbox` styling with minor visual tweaks to icon/container sizing and description text.

### Removed
- Removed the `order: int` field from `WorkflowManifest`.
- Removed the `order` field from all individual workflow manifests.


## [v0.5.25] - 2026-04-03

Changed
- Merged dev to main (#448).


## [v0.5.24] - 2026-04-03

### Added
- Added an MCP (Model Context Protocol) server mounted at `/mcp` with OAuth authentication and tools to list workflow types, create projects, run workflows, and get project details.
- Added the ability for users to cancel running or pending workflow runs with cascade cancellation through dependent workflows, in-flight interruption, and live duration tracking in the UI.
- Added an About page that renders configurable markdown content fetched from the app config system.
- Added a new public `GET /api/app-configs/{key}` endpoint returning `{ value: string }`.
- Added support for users to store a personal OpenAI API key encrypted at rest for automatic use in analyses, including from MCP clients.
- Added new user API endpoints to manage the stored OpenAI API key (`PUT /api/users/me/api-key` and `DELETE /api/users/me/api-key`).
- Added a new `/account` settings page for saving, replacing, and removing the stored OpenAI API key.
- Added `has_openai_api_key` to `UserResponse`.
- Added per-key rate limiting to embedding calls in `VectorStoreService`.

### Changed
- Replaced per-request OpenAI API key entry in analysis forms, dialogs, and workflow triggers with account-level API key configuration used automatically by the server.
- Added a new analysis wizard step (`StepApiKeyConfig`) when `NEXT_PUBLIC_REQUIRE_OPENAI_API_KEY_CONFIG=true` to prompt users to save their OpenAI API key to their account.
- Renamed `NEXT_PUBLIC_HIDE_CUSTOM_OPENAI_API_KEY_INPUT` to `NEXT_PUBLIC_REQUIRE_OPENAI_API_KEY_CONFIG` and changed its semantics to require key setup as a wizard step.
- Simplified the preflight service by removing client-side API key validation.
- Updated workflow runner key resolution order to: per-request key, then user's stored key, then server environment variable.
- Updated the MCP `run_workflow` tool to require a stored API key.
- Refactored `@register_node` to accept only a name and removed the description argument from all workflow node registrations.
- Broadened workflow cancellation progress cleanup to clear incomplete progress entries across all runs for the same project and workflow type.
- Consolidated the top-level `api/` package under `lib/` to unify the codebase into a single package namespace, with corresponding updates to configuration, deployment references, and tests.
- Updated navigation by moving "Start new project" into a standalone button and adding an "About" nav link pointing to `/about`.
- Updated profile dropdown labels by adding a user-facing "Settings" link and renaming admin "Settings" to "App Settings".
- Updated MCP instructions text from "Draft Detective / AI Reviewer" to "Draft Detective AI Reviewer".

### Fixed
- Fixed workflow cancellation progress cleanup so stale `pending`/`in_progress` entries from prior runs are also resolved.

### Security
- Encrypted stored user OpenAI API keys at rest and ensured the key is never returned in API responses.

### Removed
- Removed OpenAI API key fields from frontend request payloads and from all analysis forms, dialogs, and workflow triggers.
- Removed inline `get_rate_limiter` and `hash_api_key` definitions from `lib/models/agent.py` in favor of a shared config module.
- Removed the standalone top-level `api/` package and removed `api` from the wheel build targets in `pyproject.toml`.


## [v0.5.23] - 2026-03-27

### Added
- Added an admin logs viewer in the UI with support for downloading application log files.
- Added admin-only API endpoints to list log file metadata and download log files.
- Added a timed rotating file logger that writes to a log file, rotates daily at midnight, and retains 90 days of history.
- Added a `MatchSource` enum to track how reference-to-file matches were created (`manual_upload`, `auto_matched`, `auto_fetched`).
- Added end-to-end Inspect AI evals for the `document_structure` and `figures_tables_check` workflows.
- Added end-to-end Inspect AI eval for the `reference_downloader` workflow and a new dataset covering diverse reference types.
- Added shared Pydantic mirror types for evals targeting `SimpleDeepAgent`-based workflows.
- Added full-text search to the admin feedback and users views, backed by PostgreSQL trigram indexes for efficient `ILIKE` queries.
- Added a searchable user combobox component and updated admin lists to use server-side search and pagination.
- Added a skills injection mechanism for deep agents and introduced a skills file defining the canonical issue output format.
- Added Rule 5 to the figures/tables check workflow to validate callout proximity to referenced figures/tables.
- Added a CI step to log in to Docker Hub during Trivy scans.

### Changed
- Replaced `ReferenceFileMatch.is_manual` with `ReferenceFileMatch.source` using the new `MatchSource` enum, including migration of legacy persisted state.
- Updated reference linking to require a `source` parameter and to pass appropriate `MatchSource` values for uploads, auto-fetching, and auto-matching.
- Regenerated frontend types and updated reference composition and UI to propagate and display match source badges.
- Updated queries to hide fetch results for manually uploaded files.
- Migrated the `reference_validation` eval dataset from JSONL to JSON and expanded it from 25 to 52 entries.
- Updated `reference_validation_e2e.py` to load from the new JSON dataset file.
- Upgraded `ReferenceFetcherAgent` and `ReferenceValidatorAgent` from `gpt_5_2_model` to `gpt_5_4_model`.
- Changed `ReferenceFetcherAgent.ainvoke` to return `(result, messages)` and updated call sites accordingly.
- Standardized issue output format across workflows via skills injection and made `system_prompt` optional for deep agents.
- Updated `IssueItem` to include an optional `long_description` field and passed it through to `DocumentIssue`.
- Removed per-workflow system prompts and output requirement sections from the `document_structure` and `figures_tables_check` manifests.
- Increased readonly thread max-width and updated user message rendering to use Markdown styling.
- Bumped `inspect-ai` from `0.3.191` to `0.3.200`.
- Added `cmdk@1.1.1` to the frontend.
- Removed the `project_id` filter from admin feedback retrieval and endpoints.
- Added `search`, `role`, `limit`, and `offset` parameters to user listing for server-side filtering and pagination.
- Scoped `/logs/` ignore in `.gitignore` to the repo root.

### Fixed
- Fixed a crash in `format_cited_references` when `citations` is `None` by returning a safe fallback string.

### Removed
- Deleted the legacy pytest-based `test_reference_fetcher.py` and its `reference_fetcher.yaml` dataset in favor of the new Inspect AI end-to-end eval.


## [v0.5.22] - 2026-03-20

### Added
- Added role-based access levels for project permissions with a unified `get_project_access` gate that returns an `AccessLevel`.
- Added a feedback visibility system and an admin feedback dashboard with filtering, pagination, and CSV export.
- Added two new deep-agent workflows (`document_structure` and `figures_tables_check`) and a reusable `SimpleDeepAgentManifest` base for single-node deep-agent workflows.
- Added a new frontend chat thread UI for deep-agent workflows powered by `@assistant-ui/react`.
- Added an end-to-end eval framework and reorganized evals into an `internal/e2e` structure.
- Added documentation guidance for uploading partial documents and removed the OpenAI mention from the web search tooltip.

### Changed
- Updated backend routers and `api/services/workflow_runner.py` to use `get_project_access` for project access checks.
- Updated the frontend project page to handle `403` and `404` errors with dedicated UI states and to disable write actions when access is read-only.
- Refactored `about_this_ger` to reuse shared types and helpers from the new `simple_deep_agent` module.
- Simplified `config_factory.py` by removing per-workflow branching in favor of a generic validation approach and ensuring `type` is included in common fields.
- Regenerated frontend generated API types/SDK to include feedback visibility and new admin feedback endpoints.

### Fixed
- Fixed markitdown conversion output to strip backslash-escaped underscores inside URLs while leaving non-URL escaped underscores unchanged.
- Fixed `_get_project_by_id` to handle invalid UUIDs gracefully.

### Removed
- Removed the original `inference_validation` v1 workflow and related backend and frontend code, including its registration, union types, and associated eval test and dataset.
- Removed `lib/services/authorization.py` after consolidating project access logic.


## [v0.5.21] - 2026-03-13

### Added
- Added the About This (GER) workflow for validating preface/introduction and author biography sections against GER publication rules.
- Added a runtime application config system that allows admins to override agent system prompts without code changes.
- Added a new `AppConfig` model and an Alembic migration creating the `app_configs` table with a unique index on `key`.
- Added a config service with `get_config`, `upsert_config`, `delete_config`, and `seed_all_defaults` to insert default values on startup without overwriting admin customizations.
- Added an admin-only Config API with CRUD endpoints (`GET`, `PUT /{key}`, `DELETE /{key}`) for managing configs, where delete resets to code defaults by re-seeding.
- Added a lifespan hook that seeds default configs on startup.
- Added new deep agents `AuthorsValidatorAgent` and `PrefaceValidatorAgent` that accept an optional `system_prompt_override`.
- Added a new admin Settings page with inline editing for config values and a reset-to-default action with a confirmation dialog.
- Added a GER results component with a tabbed Preface/Authors view showing issues or success states with markdown reports.

### Changed
- Updated navigation to include a settings link in the profile dropdown.
- Updated the workflow type checkbox with the new workflow icon.
- Regenerated generated API types to include new endpoints and schemas.

### Security
- Restricted config management to admin-only access via a `require_admin` dependency.


## [v0.5.20] - 2026-03-12

### Changed
- Merged dev to main (#416).


## [v0.5.19] - 2026-03-12

### Changed
- Renamed all TASP references to CAST and generalized program-specific identifiers to be less coupled to a single program name.
- Renamed workflow config keys `tasp_boilerplate` to `boilerplate` and `tasp_url` to `program_url`.
- Renamed `rule_3_tasp_statement` to `rule_3_program_statement` in workflow config, state models, and validation nodes.
- Renamed YAML keys `tasp_fellow_prompt` / `tasp_statement_prompt` to `fellow_prompt` / `program_statement_prompt`.
- Renamed `source_tasp` requirement to `source_boilerplate` across the preface checker agent, state, constants, and validation config.
- Updated `AuthorRuleType` enum values from `TASP_FELLOW`/`TASP_STATEMENT` to `PROGRAM_FELLOW`/`PROGRAM_STATEMENT`.
- Updated `PrefaceRequirementType` enum value from `SOURCE_TASP` to `SOURCE_BOILERPLATE`.
- Renamed prompt template `_paragraph_tasp_check_prompt` to `_paragraph_boilerplate_check_prompt` and updated CAST references in the prompt text.
- Updated internal variable names including `is_tasp_fellow` to `is_program_fellow` and `tasp_check_raw` to `fellow_check_raw`.
- Updated frontend rule and requirement config fields and labels from TASP to CAST, including `source_tasp` to `source_boilerplate`.
- Regenerated API types (`types.gen.ts`) to reflect renamed fields.


## [v0.5.18] - 2026-03-10

### Added
- Added an `init_embeddings()` factory function and an `EMBEDDING_MODEL_LARGE` constant to centralize OpenAI embedding initialization.
- Added a `SentenceTokenizerAgent` class (new module renamed from the previous LLM sentence tokenizer service) with its prompt and output schema co-located.

### Changed
- Refactored the document chunking pipeline to replace the `DocumentChunkerAgent` class and standalone LLM sentence tokenizer service with more composable abstractions.
- Converted `DocumentChunkerAgent` into a plain async function `chunk_document_nltk()` that accepts a `SentenceTokenizerAgent` dependency and moved the `FRAGMENT_DETECTION_METHOD` constant from the deleted service module.
- Updated chunk splitting workflow code to use `chunk_document_nltk()` and explicitly instantiate `SentenceTokenizerAgent`.
- Updated embedding initialization in `vector_store`, `reference_embedding_matcher`, and `fragment_detection` to use `init_embeddings()` instead of inline `OpenAIEmbeddings` construction.
- Upgraded `fragment_detection` to use `text-embedding-3-large` instead of `text-embedding-3-small`.

### Removed
- Removed duplicated local embedding model constants and direct `OpenAIEmbeddings` imports in modules now using `init_embeddings()`.
- Removed the `try/except ImportError` guard for embedding initialization in `fragment_detection`.
- Removed the now-unused `SecretStr` import from `vector_store`.


## [v0.5.17] - 2026-03-10

### Added
- Added a new “Reviewer 2” workflow that generates a structured peer review and a devil’s-advocate rebuttal for uploaded research documents.
- Added a new `Reviewer2Results` UI with tabbed peer review/rebuttal display and download options for DOCX and PDF.
- Added `gpt-5.4` to the LLM model registry.
- Added the `@mohtasham/md-to-docx` dependency for markdown-to-DOCX conversion.

### Changed
- Updated the workflow results renderer to route the new workflow type to the new results component.
- Improved the markdown component factory to accept React components (not just HTML tag names) to support shadcn `Table` components for markdown table rendering.
- Regenerated API types to include `Reviewer2Config`, `Reviewer2State`, and the new workflow run type.
- Regenerated API types so `project_id` fields are required across all workflow configs and removed `chunk_indices` from `ExtractedReference`.
- Updated documentation to reference “OpenAI, Anthropic, Google” instead of “OpenAI, Azure, Bedrock,” with minor markdown formatting fixes.

### Removed
- Removed Azure OpenAI as a supported LLM provider and simplified to OpenAI-only for OpenAI models.
- Removed Azure OpenAI environment variables from configuration and templates (`AZURE_OPENAI_API_KEY`, `AZURE_OPENAI_ENDPOINT`, `OPENAI_API_VERSION`).
- Removed the legacy v1 reference text extraction pipeline and consolidated entirely on the v2 implementation.
- Removed v1 reference extraction code and related tests, and renamed remaining v2 tests to drop version suffixes.


## [v0.5.16] - 2026-03-04

### Added
- Added a dedicated `lib/services/project_zip.py` module for project ZIP creation with smart per-file compression and async thread offloading.
- Added a shared `lib/services/uuid_utils.py` utility module containing the `ensure_uuid` helper.
- Added `tests/unit/test_project_zip.py` with unit tests covering compression selection, archive building behaviors, and the async ZIP creation orchestrator.
- Added an `is_manual` boolean field to `ReferenceFileMatch` to distinguish manual matches from automatic ones.
- Added tests in `test_match_supporting_docs.py` to verify already-matched references are skipped and the matcher is not invoked when all references are matched.

### Changed
- Updated `lib/services/files.py` to remove ZIP creation code and accept an optional `roles` filter in `get_files_by_project_id` to push role filtering to the DB query.
- Updated `api/routers/projects.py` imports to use the new `project_zip` module.
- Updated `manifest.py` so `create_initial_state` loads and carries forward existing matches from a prior `REFERENCE_FILE_MATCHING` state.
- Updated `match_supporting_docs.py` to preserve existing matches by skipping already-matched references and appending new matches, tagging automatic matches as `is_manual=False`.
- Updated `references.py` so `add_file_to_reference` sets `is_manual=True` for user-created matches.
- Changed the `MAIN_FILE_CONVERTER` default from `"docling"` to `"markitdown"`.

### Removed
- Removed all docling-serve integration code, configuration, and infrastructure from the codebase.
- Deleted `lib/services/converters/docling.py` and `lib/services/converters/docling_zip_processor.py`.
- Removed the `elif converter == "docling"` branch from `lib/services/converters/base.py`.
- Removed `DOCLING_SERVE_API_URL` and `DOCLING_SERVE_API_KEY` fields and the `validate_docling_serve_api` validator from `lib/config/env.py`.
- Removed the `docling-serve` service from `docker-compose.yml` and deleted `k8s/docling.yaml`.
- Removed docling entries from `k8s/configmap.yaml` and `k8s/network-policy.yaml`, and removed docling environment variables from `.env.template`.
- Updated `docs/index.md`, `docs/railway-deployment.md`, and `k8s/README.md` to remove docling references, and cleaned up a comment in `.github/workflows/backend.yml`.


## [v0.5.15] - 2026-03-04

### Added
- Propagated `user_id` to Langfuse tracing context during workflow execution.

### Changed
- Made `project_id` a required field across the workflow system and updated related API response typing.
- Renamed ambiguous backend `types.py` modules for clarity and updated imports accordingly.
- Renamed the "About Authors" analysis type display name to "About the Authors" in both backend and frontend UI strings.
- Simplified frontend `ProjectsList` and `ProjectCard` components by removing tool-specific UI logic and unnecessary wrapper nesting.

### Fixed
- Fixed a runtime crash in the About the Authors workflow by syncing the default `workflow_config.yaml` rules with the `AuthorValidationResult` model.

### Removed
- Removed the standalone Tools section from the application and consolidated access around the project-based workflow.
- Removed `/tools` pages and supporting frontend modules related to tool definitions, URL-based project syncing, tool-specific workflow polling, and project type filtering.
- Removed the backend auto-project-creation workaround for Reference Downloader workflows that ran outside a project context.
- Removed the Reference Downloader link from the analysis form’s supporting documents section.


## [v0.5.14] - 2026-03-03

### Added
- Added an `include_passing` filter to DOCX export to exclude passing issues (severity=none) by default with an opt-in to include them.
- Added an `include_passing` query parameter (default `false`) to the `/api/projects/{project_id}/docx/download` endpoint.
- Added `get_deepagent_backend_files()` to the file artifacts service type, implementation, and mock for DeepAgent backend file formatting.
- Added `deepagents>=0.4.4` as a dependency.
- Added "MIT" and "ChatGPT" to the static ignored abbreviations list.

### Changed
- Updated DOCX export generation and caching behavior to propagate `include_passing`, include it in cache key generation, and disable caching on the download endpoint (`use_cache=False`).
- Renamed the `NONE` severity label in the DOCX manipulator from "📝 Note" / "NT" to "✅ Passing" / "PA".
- Updated frontend DOCX download flow to accept and forward `includePassing`, treat it as an active filter, and show a "Passing checks included" badge when active.
- Migrated the abbreviation checker agent from LangChain `create_agent` to `deepagents` `create_deep_agent`, removing tool dependencies and switching the response format to `AutoStrategy`.
- Rewrote the abbreviation checker system prompt to focus on cataloguing occurrences and added guidance for multi-abbreviation lines.
- Refined abbreviation checker evals by removing a helper, switching DeepDiff comparison to `ignore_order=True`, and updating dataset target answers for precise occurrence counts, line numbers, and consistent formatting.
- Suppressed Pydantic serialization warnings for stale workflow_type enum values in the DB.


## [v0.5.13] - 2026-03-03

### Added
- Added an agent-based abbreviation scan v2 workflow that uses an AI agent to read the full document with search/read tools and produce structured per-occurrence output.
- Added a new InspectAI eval for the abbreviation checker with a dataset and a custom structural similarity scorer.
- Added a "show passing" toggle to the document explorer and consolidated filter state into a single `DocumentExplorerFilter` interface.

### Changed
- Updated the abbreviation scan workflow to emit issues for all detected abbreviations, including `NONE`-severity informational issues for defined abbreviations.
- Marked the old abbreviation scan v1 workflow as internal and hidden from users.
- Improved `chunk_line_matcher` fuzzy matching to accept an `end_line` parameter to restrict search to overlapping chunks.
- Refactored `reference_validation` eval to use a reusable `structured_output_scorer`.
- Changed document explorer visible issue sorting to sort by chunk index and then by severity.

### Fixed
- Reduced abbreviation scan false positives by filtering Roman numerals, expanding non-issue abbreviations (including `NOTE`), and ignoring additional sections such as "About the Authors".
- Updated the abbreviation checker to support plural abbreviations, fix eval key matching, and reorder workflows.


## [v0.5.12] - 2026-02-23

### Added
- Added `LLMModel.from_inspectai_name()` and support for provider-less model names in the `model_name` property.
- Added new InspectAI evaluation utilities: `apply_inspectai_config_to_agent`, `get_runnable_config`, and `messages_from_langchain`.

### Changed
- Migrated five agents (`CitationSuggesterAgent`, `EvidenceWeighterAgent`, `LiteratureReviewAgent`, `LiveLiteratureReviewAgent`, `MethodologyComparisonAgent`) from `DirectOpenAIAgent` to `LangChainAgent` using the LangChain `create_agent` pattern.
- Refactored InspectAI reference validation evals to invoke the `ReferenceValidatorAgent` via a custom `@agent` instead of the `generate()` solver pipeline.
- Changed `ReferenceValidatorAgent.ainvoke` to return a tuple of `BibliographyItemValidation` and full message history, and moved the system prompt into the messages list.
- Updated the reference validation workflow node to handle the new `ainvoke` tuple return.
- Updated the reference validation dataset entries with revised targets.
- Upgraded the model for `LiteratureReviewAgent` and `MethodologyComparisonAgent` from `gpt_5_model` to `gpt_5_2_model` with reasoning config (`effort: low`).
- Regenerated frontend API types in `types.gen.ts` to reflect updated field descriptions.
- Bumped `inspect-ai` from 0.3.179 to 0.3.180.

### Fixed
- Renamed `EvidenceWeighterRecommendedAction.NO_CHANGE` to `NO_UPDATE_NEEDED` to match its value.
- Improved Pydantic field descriptions so enum-typed fields dynamically include possible values to improve structured output reliability.

### Removed
- Removed the `DirectOpenAIAgent` base class and its usage in the agent factory.
- Removed OpenAI helper utilities `wait_for_response` and `ensure_structured_output_response` from `lib/services/openai.py`.
- Removed inline test scripts (`if __name__ == "__main__"` blocks) from `citation_suggester.py`, `literature_review.py`, `live_literature_review.py`, and `methodology_comparator.py`.


## [v0.5.11] - 2026-02-20

### Added
- Introduced an LLM evaluation framework using Inspect AI to measure the reference validation agent’s accuracy.
- Added a new `evals_inspectai/` package with a reference validation eval task, a 22-sample labeled dataset, and usage documentation.
- Added a `get_model_name_for_inspectai()` helper to format model names for Inspect AI configuration.
- Added `inspect-ai` and `openai` dependencies, added a `[build-system]` with hatchling, and configured wheel packaging to include `evals_inspectai`.
- Added `logs/` to `.gitignore`.

### Changed
- Routed single-file reference uploads through the TUS upload path with `reference_id` passed as metadata and linked on TUS completion.
- Extracted the reference validator system prompt into a module-level `SYSTEM_PROMPT` constant and refined the prompt to ignore page ranges and clarify validation categories.
- Added `referenceId` support to `FileUploadDialog` and `UseUploadOptions`, and updated `ReferenceCard` to pass its reference ID to the upload dialog.
- When `referenceId` is set, updated `FileUploadDialog` to skip the batch workflow trigger on completion and invalidate the project query cache.
- Regenerated API types (`sdk.gen.ts`, `types.gen.ts`, `transformers.gen.ts`) to remove deleted endpoints.

### Fixed
- Fixed a bug where uploading a single file from a reference card incorrectly triggered the batch reference-matching workflow.

### Removed
- Removed the `POST /api/project/{project_id}/files` and `POST /api/project/{project_id}/file` REST upload endpoints so all file uploads go through TUS exclusively.


## [v0.5.10] - 2026-02-19

### Added
- Introduced persisted issues stored in the database, enabling users to mark issues as resolved/unresolved and improving retrieval performance.
- Added REST endpoints to get an issue and to resolve/unresolve issues.
- Added batch feedback fetching for a project and linked feedback directly to issues via a foreign key.
- Added a new Health Monitor dashboard on the Summary tab to provide an at-a-glance view of project health across workflow analyses.
- Added an optional `inaccessibility_reason` field to reference fetch results to explain why a source could not be downloaded.
- Added the same document explorer issue filters to the Word add-in, along with an issues counter and a jump-to-paragraph feature.
- Added a Zustand-based centralized store for document explorer filter and chunk selection state.
- Converted the claim verifier to an agentic tool-using architecture with parallel paragraph verification.

### Changed
- Improved reference validation by replacing binary valid/invalid with a tri-state `final_result` (`valid`, `found_with_inconsistencies`, `not_found`) and updated issue severity/title generation accordingly.
- Updated the reference validation UI to render and filter results using the new tri-state categories with distinct colors, icons, labels, and a "Not Found" filter badge.
- Removed the deprecated `chunk_index` field and consolidated chunk references to `chunk_indices` across the system.
- Updated evidence source matching to use `file_id` instead of `reference_file_name`.
- Updated the website with new features.
- Updated the summary page (RANDZ-420).
- Added the option to remove the chunk index on the "Jump to" feature.

### Fixed
- Fixed the resolved/unresolved issue filter so it correctly applies to both the document explorer view and the sidebar, with resolved issues hidden by default.

### Removed
- Removed all Docling document viewer support and the document render mode toggle, switching to markdown-only document rendering.
- Removed the separate URL redirect checking service and related parallel URL check logic from reference validation.
- Removed the `cited_url` field from reference validation results.
- Removed the deprecated `chunk_index` field from issue API responses and the database.


## [v0.5.9] - 2026-02-12

### Added
- Introduced a Microsoft Word add-in for AI Reviewer, including manifests, local development setup, and a new add-in page in the frontend.
- Implemented resumable file uploads using the TUS protocol via `tuspyserver` (backend) and `Uppy` (frontend), enabling progress tracking, retry, and resume for large files (up to 500MB).
- Added thumbs up/down feedback on document issues in the results view, including text feedback when marking an issue as unhelpful.
- Added a `key_sentence` field to claim reference validation results to show the exact sentence from the source text containing the claim.

### Changed
- Improved reference validation by surfacing detailed per-field validation results in document issues and enriching the "Invalid reference" issue with suggested corrections and reasoning.
- Changed reference validation chunk lookup to use reference ID instead of reference text.
- Set `show_invalid_references_as_issues` default to `True` so invalid references appear in the Document Explorer by default.
- Increased the rate limiter from 32 to 64 requests/sec and max bucket size from 100 to 200.
- Updated the "Jump to chunk" button to support issues that only have `chunk_indices` (no single `chunk_index`).
- Updated share/export dialog behavior and messaging for DOCX download paths.
- Regenerated API types to include the new `key_sentence` field and to remove types/functions related to supported agents.

### Fixed
- Fixed paragraph selection on the Word add-in on desktop when selecting a paragraph.
- Fixed a bug where chunk lookup failed for some references.
- Added DOCX generation support for content controls to keep issue/comment placement aligned and reduce paragraph mismatch issues during export.

### Removed
- Removed the unused agent registry system and associated backend and frontend code, including the `/api/supported-agents` endpoint.
- Removed reference extraction/validation state and the `findReferenceForChunk` helper from chunk view, and removed the inline reference validation section from the chunk detail view.
- Deleted the previous single-request upload orchestrator in favor of the Uppy-based TUS upload implementation.
- Removed the separate "URL redirect detected" issue in favor of a single enriched "Invalid reference" issue.
- Removed `onNavigateToReferences` prop threading that was no longer needed.


## [v0.5.8] - 2026-02-06

### Added
- Added support for a `long_description` field and a UUID `id` on document issues, and updated the Document Explorer with a unified issues sidebar while converting missing section warnings into standard issues.
- Added persistence of web search consent per project using localStorage so users aren’t repeatedly prompted.
- Added a contextual banner for project owners when viewing their own shared link, with an “Edit Project” shortcut.
- Added a new RAND user role for QA Screener access and added QA Screener workflow identification/visibility support.
- Added workflow type filtering in the Document Explorer and DOCX exporting, including a `workflow_types` query parameter for DOCX generation.
- Added an “About This (Preface)” validation workflow to the QA Screener suite, along with new/refactored shared UI components for displaying validation results.
- Added internal scrolling support to the reference review list component via an optional prop.
- Added a per-user `show_experimental_features` preference with a UI toggle and supporting API endpoint.

### Changed
- Hid the legacy Inference Validation V1 workflow from the workflow selection UI and renamed Inference Validation V2 to “Inference Validation.”
- Replaced LLM-generated line numbers in the Inference Validation V2 workflow with chunk indices derived from fuzzy matching, and updated related UI and generated API types accordingly.
- Refactored the Reference Validation workflow to use a fan-out pattern with real-time incremental status updates, introduced per-reference status tracking, and renamed the workflow to “Reference Error Checking.”
- Migrated the database layer from synchronous SQLAlchemy to async SQLAlchemy and updated services, routers, workflows, and tests accordingly.
- Centralized QA Screener workflow configuration into a YAML-based configuration file and updated related workflows/agents to load from it.
- Refined claim categorization and standardized how document summary and headings context are formatted and passed to agents, and removed skipping verification for non-central claims.
- Improved project creation and export UX by adding warning dialogs for unmatched references and active severity filters, and updated related tooltip/badge text.
- Allowed users to skip the analysis selection step in the project creation wizard and proceed directly to the project page.

### Fixed
- Fixed incorrect citation-to-reference matching in the citation detector when numbered footnote markers have missing footnote content, and updated UI display and tests for this scenario.
- Fixed an agent registry collision between footnote extraction and reference extraction by giving the footnote extraction node a unique name.
- Added “RAND” as a non-issue abbreviation when there’s no definition of it.

### Removed
- Reverted “Feature/randz-397-include-line-numbers-in-inference-validator-output.”


## [v0.5.7] - 2026-01-30

### Added
- Added workflow run history viewing and selection in the UI.
- Added a new `/api/project/{project_id}/workflow-runs` endpoint for fetching workflow runs by type.
- Added a `workflow_run_id` field to workflow errors to tag errors to a specific run.
- Added a `current_workflow_run_id` context variable to track the active workflow run.
- Added `getDisplayStatus()` and `hasCurrentRunErrors()` utilities.

### Changed
- Updated workflow error handling to tag errors with the originating workflow run ID and filter displayed errors to the current run.
- Refactored multiple workflow nodes to use a centralized `convert_exceptions_to_workflow_errors` function.
- Refactored the analyses tab and related UI to use new hooks and extracted components for workflow selection, sidebar, and results rendering.
- Updated the project card to use the new display status logic.
- Added support for a "failed" display status in the status indicator.
- Regenerated frontend API types for the new endpoint.
- Parallelized workflow run state fetching with `asyncio.gather`.

### Fixed
- Fixed an issue where errors from previous workflow runs were displayed after a new run completed successfully.


## [v0.5.6] - 2026-01-30

### Added
- Added an Abbreviation Scan workflow that detects abbreviations/acronyms missing in-text definitions and surfaces LOW-severity issues in the UI.
- Added severity filtering support to DOCX export so downloads can include only issues matching the currently selected severity filter.
- Added line number tracking to document chunks and enabled multi-chunk selection in the Document Explorer to improve reference-to-chunk matching and navigation.
- Added a new Advocacy & Tone analysis workflow (QA Screener) to detect problematic language such as legal/regulatory terms, advocacy language, and subjective tone.
- Added optional rich console logging with a configurable `LOG_RICH_HANDLER` setting and a new `rich` dependency.

### Changed
- Refactored workflow results UI to reduce duplication by extracting shared components and refactored About Authors rule metadata to be centralized in the backend.
- Added an `always_run` flag for idempotent workflows to bypass “already completed” skip logic when included as dependencies, and simplified related frontend workflow triggering.
- Migrated database queries across service modules from SQLAlchemy 1.x `query()` usage to SQLAlchemy 2.0 `select()` style.
- Removed “Possible invalid reference” issues from the Document Explorer and instead displayed reference validation results as metadata in the References tab, including cross-tab navigation support.
- chore: merge cursorrules to agents.md and improve prompt

### Fixed
- Fixed the Document Explorer severity filter so it applies to both the sidebar list and the main document reconstructor view.
- Improved Document Explorer scroll-to-chunk accuracy with a retry mechanism and removed redundant polling-based scroll logic from hash navigation.
- Added URL redirect detection to the reference validation workflow and generated a MEDIUM-severity issue when a cited URL redirects to a different final URL.

### Removed
- Removed the reference extraction progress bar that showed “Reference X of Y” during extraction.


## [v0.5.5] - 2026-01-28

### Added
- Extracted chunk splitting into a standalone `chunk_splitting` workflow and added `WorkflowRunType.CHUNK_SPLITTING`.
- Added rate limiting and retry logic for Jina API calls in the reference downloader workflow.
- Added an `AGENTS.md` file.
- Extracted document summarization into a separate `document_summarization` workflow and added `DOCUMENT_SUMMARIZATION` to `WorkflowRunType`.
- Added UX improvements for uploading and reference review, including parallel reference fetching and improved loading feedback.
- Added a new agentic reference extractor (v2) using tool-calling, plus new document search and line-range read tools.
- Added automatic batching for parallel workflow node progress tracking.
- Added support for deep-linking to wizard steps via a `?step=` URL parameter and added `initialStep` support in the wizard context.
- Added a human review step in the analysis wizard with a new human approval workflow and an API endpoint for approving workflow runs.
- Added batch upload for supporting documents with incremental processing capabilities.
- Added heading context propagation through chunking and claim extraction, and introduced file artifact caching (markdown/summary).
- Added reference validation results to the reference review card component.
- Added a reference file matching review screen (tab hidden) with supporting API endpoints and UI components.
- Added an admin-only user role management page with endpoints to list users and update roles.
- Added warning callouts when reference extraction completes without finding any references.
- Added a new project-level workflow progress endpoint (`GET /api/projects/{project_id}/workflow-progress`).

### Changed
- Refactored the `document_processing` workflow to remove chunk splitting responsibilities and updated dependent workflows to retrieve chunks via a helper.
- Updated the upload flow and results calculations to use the new chunk splitting workflow state and regenerated API types accordingly.
- Converted reference downloader file download and content reading utilities from sync wrappers to native async and improved error visibility.
- Simplified the analysis wizard UX, improved loading states, and moved supporting document uploads to Step 3 (reference review).
- Split the `reference_extraction` workflow into separate extraction and `reference_file_matching` workflows and updated frontend to compose references from both states.
- Replaced `reference_index` with UUID-based `reference_id` across reference downloader and file matching workflows and updated related frontend usage.
- Implemented a two-step wizard flow that starts document processing immediately after upload and refactored workflow orchestration to prevent race conditions when re-running workflows.
- Removed unneeded context statements from `{domain_context}` and `{audience_context}` inputs and added an `# Agent Inputs` section to the prompt.
- Refactored workflow progress tracking from per-workflow-run polling to a project-level API and updated the frontend progress toast hook accordingly.

### Fixed
- Improved recursion limit error handling for reference downloads by increasing the recursion limit and adding user-friendly frontend error messages.
- Updated claim reference validation and claim categorization to only process and flag central claims, skipping non-central claims.

### Security
- Added admin-only protection for user management endpoints via a `require_admin` dependency and frontend route guarding.

### Removed
- Removed the per-workflow-run progress endpoint (`/api/progress/workflow/{workflow_run_id}`) and the unused frontend `use-workflow-progress.ts` hook.


## [v0.5.3, v0.5.4] - 2026-01-16

### Added

- Added preflight validation to check OpenAI and Azure OpenAI API keys before starting document analysis, including a new `/api/preflight` endpoint and frontend integration to block uploads on invalid keys.
- Added user roles (`USER`, `ADMIN`) with a new `/api/users/me` endpoint and admin-only navigation for Evaluations and Tools.
- Added a new Footnote Extraction workflow and refactored Citation Detection to use extracted footnotes instead of the full document.
- Added real-time workflow progress tracking with database persistence, a new `GET /api/progress/workflow/{workflow_run_id}` endpoint, and a frontend progress toast UI.
- Added configurable display ordering for workflow types and explanatory tooltips for workflow badges.
- Added an environment-variable-controlled feature flag to show or hide experimental features and conditionally display the Document Publication Date field.
- Added parallel fetching with real-time streaming status updates and improved file lifecycle management in the Reference Downloader tool, including a new `SUPPORTING_CANDIDATE` file role.
  
### Changed

- Updated Literature Review and Citation Suggester analysis type descriptions to better clarify their purposes and relationship.
- Marked Citation Suggester and Literature Review workflows as experimental.
- Changed workflow type sorting from alphabetical to order-based and updated which workflows are considered experimental vs stable.
- Simplified DOCX export by removing the `docx_generation` workflow and replacing it with a direct service call, including updates to the DOCX download endpoint and related API types.
- Removed the deprecated `claim_substantiation` workflow and updated eval package generation and related API endpoints to use `project_id`.
- Improved changelog automation prompts to reduce AI hallucinations and added debugging output for collected PR data and prompts.
- Refactored the frontend to extract reusable workflow components from the analysis form.
  
### Fixed

- Fixed Pydantic enum serialization warnings for `WorkflowRunType` by coercing string values to the enum during model instantiation and handling serialization when values remain strings.
- Silenced ffmpeg warnings by installing only required `markitdown` extras instead of `markitdown[all]`, and added a `pyjwt` dependency.
- Prevented an intermittent NLTK startup race condition by pre-downloading `punkt_tab` data during Docker builds and in CI before running pytest.
- Fixed vector store document indexing by removing buggy metadata construction and adding batched embedding for large documents, with improved error handling for supporting document indexing.
- Fixed the Reference Extractor tool UX by removing the supporting documents option, adding an OpenAI API key input, tightening accepted file types, and fixing re-selecting the same file not triggering a change event.
- Made backend tests fail the workflow on failure.
  
### Removed

- Removed the `docx_generation` LangGraph workflow and the `DOCX_GENERATION` workflow type.
- Removed the deprecated `claim_substantiation` workflow and its associated LangGraph configuration.
- Removed audio/video conversion-related optional dependencies from the `markitdown[all]` installation.

## [v0.5.2] - 2026-01-13

### Added

- Introduced `FileArtifactsService` to centralize access to file artifacts across workflows.

### Changed

- Improved file type detection for document conversion using content-based MIME type detection.
- Added support for legacy `.doc` files by converting them to `.docx` before processing.

### Fixed

- Fixed claim detector footnote marker matching to use content instead of index for bibliography entries.

### Removed

- Removed `retrieved_passages` field from `ClaimSubstantiationResult` to reduce state size.

## [v0.5.1] - 2026-01-12

### Added

- Added read-only mode support to analyses tab.

### Changed

- Improved table column widths and text wrapping in references tab.

### Removed

- Removed unused 'type' column from files tab.

## [v0.5.0] - 2026-01-11

### Added

- Added HEAD method support to health check endpoint.

### Changed

- Refactored reference-to-supporting-document matching to use `file_id` instead of `file_name`.
- Optimized backend performance with non-blocking file I/O and configurable uvicorn workers.
- Updated DOCX markdown conversion to use simpler method while maintaining visualization.

## [v0.4.2] - 2026-01-07

### Fixed

- Resolved an issue with Posthog integration in the production environment, ensuring that user names and emails are now correctly captured for all sessions.

## [v0.4.1] - 2026-01-07

### Fixed

- Adjusted auto changelog updates.

## [v0.4.0] - 2026-01-07

### Added

- Introduced a new 'Analyses' page for enhanced document review visualization.
- Added tool runs as projects to maintain a history of tool executions and access results.
- Implemented a severity issues filter in the explorer tab for better issue management.
- Persisted project configuration options for consistent project settings.
- Introduced a new **Results Extraction** workflow for extracting and assessing research document results.
- Added Posthog integration to the front-end.

### Changed

- Refactored workflow architecture to extract citation detection and claim extraction into separate workflows, improving modularity.
- Improved reference extraction and downloader workflows for better performance and reliability.
- Enhanced claim categorizer agent to reduce false positives in the `needs_external_verification` field.
- Improved loading state management between upload completion and analysis start.
- Enabled multi-workflow execution with dependency management for streamlined operations.

### Fixed

- Corrected minor spelling errors in documentation.

### Removed

- Eliminated the unused 're-run analysis' flow from the UI to streamline user experience.

### Deprecated

- Deprecated claim substantiation workflow in favor of more modular, standalone workflows.

## [v0.3.37] - 2025-12-17

### Fixed

- Remove incorrect `package-lock.json` file (project uses `pnpm-lock.yaml`)

## [v0.3.36] - 2025-12-17

### Changed

- Version bump release

## [v0.3.35] - 2025-12-17

### Fixed

- Correctly check share link and ownership when fetching page images

## [v0.3.34] - 2025-12-17

### Fixed

- Update unsafe React and Next.js versions to secure releases

## [v0.3.33] - 2025-12-17

### Added

- Read-only mode to analysis options menu in shared pages

## [v0.3.32] - 2025-12-16

### Added

- Possibility to run workflows that don't require API keys
- Context support for shared workflow views

### Fixed

- Docling images now properly appear in shared context

## [v0.3.31] - 2025-12-15

### Fixed

- Adjust DOCX download behavior for non-public contexts

## [v0.3.30] - 2025-12-15

### Added

- Gzip middleware for improved response compression

## [v0.3.29] - 2025-12-12

### Changed

- Adjust chunk mapping system for Docling document processing

## [v0.3.28] - 2025-12-12

### Added

- Links to DOCX comments for easier navigation
- Summary parameter for `get_workflow_run_state_by_thread_id` endpoint
- DocxGeneration state management

### Changed

- Moved DOCX generation to a new dedicated workflow
