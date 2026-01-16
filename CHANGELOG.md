# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).


## [v0.5.4] - 2026-01-16

No pull request titles or descriptions were provided, so I can’t generate a changelog entry based on PR data.

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
