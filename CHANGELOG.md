# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).


## [v0.4.0] - 2026-01-07

### Added
- Introduced a new 'Analyses' page for enhanced document review visualization.
- Added tool runs as projects to maintain a history of tool executions and access results.
- Implemented a severity issues filter in the explorer tab for better issue management.
- Persisted project configuration options for consistent project settings.
- Introduced a new **Results Extraction** workflow for extracting and assessing research document results.

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
