from lib.workflows.citation_suggester.state import (
    CitationSuggesterState,
    CitationSuggesterWorkflowConfig,
)
from lib.workflows.claim_substantiation.state import (
    ClaimSubstantiatorState,
    SubstantiationWorkflowConfig,
)
from lib.workflows.document_processing.state import (
    DocumentProcessingState,
    DocumentProcessingWorkflowConfig,
)
from lib.workflows.docx_generation.state import (
    DocxGenerationState,
    DocxGenerationWorkflowConfig,
)
from lib.workflows.literature_review.state import (
    LiteratureReviewState,
    LiteratureReviewWorkflowConfig,
)
from lib.workflows.live_reports.state import LiveReportsState, LiveReportsWorkflowConfig
from lib.workflows.methodological_alignment.state import (
    MethodologicalAlignmentState,
    MethodologicalAlignmentWorkflowConfig,
)
from lib.workflows.results_extraction.state import (
    ResultsExtractionState,
    ResultsExtractionWorkflowConfig,
)
from lib.workflows.reference_downloader.state import (
    ReferenceDownloaderState,
    ReferenceDownloaderWorkflowConfig,
)
from lib.workflows.reference_validation.state import (
    ReferenceValidationState,
    ReferenceValidationWorkflowConfig,
)

WorkflowState = (
    DocumentProcessingState
    | ClaimSubstantiatorState
    | MethodologicalAlignmentState
    | ReferenceDownloaderState
    | DocxGenerationState
    | LiteratureReviewState
    | LiveReportsState
    | ReferenceValidationState
    | CitationSuggesterState
    | ResultsExtractionState
)

WorkflowConfig = (
    DocumentProcessingWorkflowConfig
    | SubstantiationWorkflowConfig
    | MethodologicalAlignmentWorkflowConfig
    | ReferenceDownloaderWorkflowConfig
    | LiteratureReviewWorkflowConfig
    | LiveReportsWorkflowConfig
    | ReferenceValidationWorkflowConfig
    | CitationSuggesterWorkflowConfig
    | ResultsExtractionWorkflowConfig
)
