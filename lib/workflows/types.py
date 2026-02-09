from lib.workflows.about_authors.state import (
    AboutAuthorsState,
    AboutAuthorsWorkflowConfig,
)
from lib.workflows.about_this.state import (
    AboutThisState,
    AboutThisWorkflowConfig,
)
from lib.workflows.advocacy_tone.state import (
    AdvocacyToneState,
    AdvocacyToneWorkflowConfig,
)
from lib.workflows.chunk_splitting.state import (
    ChunkSplittingState,
    ChunkSplittingWorkflowConfig,
)
from lib.workflows.citation_detection.state import (
    CitationDetectionConfig,
    CitationDetectionState,
)
from lib.workflows.abbreviation_scan.state import (
    AbbreviationScanState,
    AbbreviationScanWorkflowConfig,
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
from lib.workflows.claim_reference_validation_v2.state import (
    ClaimReferenceValidationV2Config,
    ClaimReferenceValidationV2State,
)
from lib.workflows.document_processing.state import (
    DocumentProcessingState,
    DocumentProcessingWorkflowConfig,
)
from lib.workflows.document_summarization.state import (
    DocumentSummarizationState,
    DocumentSummarizationWorkflowConfig,
)
from lib.workflows.footnote_extraction.state import (
    FootnoteExtractionConfig,
    FootnoteExtractionState,
)
from lib.workflows.human_approval.state import (
    HumanApprovalConfig,
    HumanApprovalState,
)
from lib.workflows.inference_validation.state import (
    InferenceValidationState,
    InferenceValidationWorkflowConfig,
)
from lib.workflows.inference_validation_v2.state import (
    InferenceValidationV2State,
    InferenceValidationV2WorkflowConfig,
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
from lib.workflows.reference_file_matching.state import (
    ReferenceFileMatchingConfig,
    ReferenceFileMatchingState,
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
    AboutAuthorsState
    | AboutThisState
    | AdvocacyToneState
    | DocumentProcessingState
    | ChunkSplittingState
    | DocumentSummarizationState
    | ReferenceExtractionState
    | ReferenceFileMatchingState
    | FootnoteExtractionState
    | ClaimExtractionState
    | ClaimReferenceValidationState
    | ClaimReferenceValidationV2State
    | CitationDetectionState
    | AbbreviationScanState
    | MethodologicalAlignmentState
    | ReferenceDownloaderState
    | LiteratureReviewState
    | LiveReportsState
    | ReferenceValidationState
    | CitationSuggesterState
    | ResultsExtractionState
    | InferenceValidationState
    | InferenceValidationV2State
    | HumanApprovalState
)

WorkflowConfig = (
    AboutAuthorsWorkflowConfig
    | AboutThisWorkflowConfig
    | AdvocacyToneWorkflowConfig
    | DocumentProcessingWorkflowConfig
    | ChunkSplittingWorkflowConfig
    | DocumentSummarizationWorkflowConfig
    | ReferenceExtractionConfig
    | ReferenceFileMatchingConfig
    | FootnoteExtractionConfig
    | ClaimExtractionWorkflowConfig
    | CitationDetectionConfig
    | ClaimReferenceValidationWorkflowConfig
    | ClaimReferenceValidationV2Config
    | AbbreviationScanWorkflowConfig
    | MethodologicalAlignmentWorkflowConfig
    | ReferenceDownloaderWorkflowConfig
    | LiteratureReviewWorkflowConfig
    | LiveReportsWorkflowConfig
    | ReferenceValidationWorkflowConfig
    | CitationSuggesterWorkflowConfig
    | ResultsExtractionWorkflowConfig
    | InferenceValidationWorkflowConfig
    | InferenceValidationV2WorkflowConfig
    | HumanApprovalConfig
)
