# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).


## [v0.4.3] - 2026-01-07

### Added
- Introduced AI-driven suggestion feature to enhance document review accuracy and efficiency.
- Added support for importing documents directly from cloud storage services.

### Changed
- Improved user interface for document annotation, providing a more intuitive experience.
- Enhanced performance of document loading times, reducing wait periods significantly.

### Fixed
- Resolved issue where certain document formats were not displaying correctly.
- Fixed bug causing occasional crashes during batch processing of documents.

### Security
- Implemented enhanced encryption protocols for document storage, ensuring greater data protection.

### Deprecated
- Deprecated support for legacy document formats; users are encouraged to convert to supported formats for continued compatibility.


## [v0.4.2] - 2026-01-07

### Added
- Introduced a new AI model for document classification, improving accuracy and speed.
- Added support for batch processing of documents, allowing users to review multiple files simultaneously.
- Implemented a user-friendly dashboard for monitoring document review progress and statistics.

### Changed
- Enhanced the user interface for better accessibility and navigation.
- Updated the document annotation tool to support more file formats.

### Fixed
- Resolved an issue where the system would occasionally crash during large document uploads.
- Fixed a bug causing incorrect tagging of certain document types.
- Addressed a problem with the search functionality not returning all relevant results.

### Security
- Improved encryption protocols for data in transit, enhancing overall system security.
- Patched a vulnerability related to user authentication, ensuring safer access controls.


## [v0.4.1] - 2026-01-07

### Added
- Introduced a new AI model for document classification, improving accuracy and processing speed.
- Added support for importing and exporting documents in XML format.

### Changed
- Enhanced the user interface for better navigation and accessibility.
- Updated the document comparison tool to provide more detailed change logs.

### Fixed
- Resolved an issue where the system would occasionally crash during large document uploads.
- Fixed a bug that caused incorrect highlighting of changes in certain document formats.

### Security
- Implemented additional encryption for data at rest to enhance security compliance.
- Updated authentication protocols to support multi-factor authentication.

### Deprecated
- Marked the legacy PDF parser as deprecated; it will be removed in a future release.

### Removed
- Removed the outdated tutorial videos from the help section, replaced with updated guides.


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
