from lib.workflows.citation_detection.state import (
    CitationDetectionConfig,
    CitationDetectionState,
)
from lib.workflows.citation_suggester.state import (
    CitationSuggesterState,
    CitationSuggesterWorkflowConfig,
)
from lib.workflows.claim_extraction.state import (
    ClaimExtractionState,
    ClaimExtractionWorkflowConfig,
)
from lib.workflows.claim_reference_validation.state import (
    ClaimReferenceValidationState,
    ClaimReferenceValidationWorkflowConfig,
)
from lib.workflows.document_processing.state import (
    DocumentProcessingState,
    DocumentProcessingWorkflowConfig,
)
from lib.workflows.footnote_extraction.state import (
    FootnoteExtractionConfig,
    FootnoteExtractionState,
)
from lib.workflows.inference_validation.state import (
    InferenceValidationState,
    InferenceValidationWorkflowConfig,
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
from lib.workflows.reference_downloader.state import (
    ReferenceDownloaderState,
    ReferenceDownloaderWorkflowConfig,
)
from lib.workflows.reference_extraction.state import (
    ReferenceExtractionConfig,
    ReferenceExtractionState,
)
from lib.workflows.reference_extraction_v2.state import (
    ReferenceExtractionV2Config,
    ReferenceExtractionV2State,
)
from lib.workflows.reference_validation.state import (
    ReferenceValidationState,
    ReferenceValidationWorkflowConfig,
)
from lib.workflows.results_extraction.state import (
    ResultsExtractionState,
    ResultsExtractionWorkflowConfig,
)

WorkflowState = (
    DocumentProcessingState
    | ReferenceExtractionState
    | FootnoteExtractionState
    | ClaimExtractionState
    | ClaimReferenceValidationState
    | CitationDetectionState
    | MethodologicalAlignmentState
    | ReferenceDownloaderState
    | LiteratureReviewState
    | LiveReportsState
    | ReferenceValidationState
    | CitationSuggesterState
    | ResultsExtractionState
    | InferenceValidationState
    | ReferenceExtractionV2State
)

WorkflowConfig = (
    DocumentProcessingWorkflowConfig
    | ReferenceExtractionConfig
    | FootnoteExtractionConfig
    | ClaimExtractionWorkflowConfig
    | CitationDetectionConfig
    | ClaimReferenceValidationWorkflowConfig
    | MethodologicalAlignmentWorkflowConfig
    | ReferenceDownloaderWorkflowConfig
    | LiteratureReviewWorkflowConfig
    | LiveReportsWorkflowConfig
    | ReferenceValidationWorkflowConfig
    | CitationSuggesterWorkflowConfig
    | ResultsExtractionWorkflowConfig
    | InferenceValidationWorkflowConfig
    | ReferenceExtractionV2Config
)
