from lib.workflows.abbreviation_scan_v2.state import (
    AbbreviationScanV2Config,
    AbbreviationScanV2State,
)
from lib.workflows.about_this_ger.state import (
    AboutThisGerConfig,
    AboutThisGerState,
)
from lib.workflows.simple_deep_agent.state import (
    SimpleDeepAgentConfig,
    SimpleDeepAgentState,
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
from lib.workflows.reviewer_2.state import (
    Reviewer2Config,
    Reviewer2State,
)

WorkflowState = (
    AboutThisGerState
    | AdvocacyToneState
    | DocumentProcessingState
    | ChunkSplittingState
    | DocumentSummarizationState
    | ReferenceExtractionState
    | ReferenceFileMatchingState
    | FootnoteExtractionState
    | ClaimExtractionState
    | ClaimReferenceValidationState
    | CitationDetectionState
    | AbbreviationScanV2State
    | MethodologicalAlignmentState
    | ReferenceDownloaderState
    | LiteratureReviewState
    | LiveReportsState
    | ReferenceValidationState
    | CitationSuggesterState
    | ResultsExtractionState
    | InferenceValidationV2State
    | HumanApprovalState
    | Reviewer2State
    | SimpleDeepAgentState
)

WorkflowConfig = (
    AboutThisGerConfig
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
    | AbbreviationScanV2Config
    | MethodologicalAlignmentWorkflowConfig
    | ReferenceDownloaderWorkflowConfig
    | LiteratureReviewWorkflowConfig
    | LiveReportsWorkflowConfig
    | ReferenceValidationWorkflowConfig
    | CitationSuggesterWorkflowConfig
    | ResultsExtractionWorkflowConfig
    | InferenceValidationV2WorkflowConfig
    | HumanApprovalConfig
    | Reviewer2Config
    | SimpleDeepAgentConfig
)
