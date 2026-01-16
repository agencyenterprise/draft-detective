# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).


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
