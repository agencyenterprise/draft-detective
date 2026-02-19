# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).


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
