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
from lib.workflows.reference_validation_v2.state import (
    ReferenceValidationV2State,
    ReferenceValidationV2WorkflowConfig,
)
from lib.workflows.reviewer_2.state import (
    Reviewer2Config,
    Reviewer2State,
)

WorkflowState = (
    AboutThisGerState
    | DocumentProcessingState
    | DocumentSummarizationState
    | ReferenceExtractionState
    | ReferenceFileMatchingState
    | ClaimReferenceValidationV2State
    | AbbreviationScanV2State
    | ReferenceDownloaderState
    | ReferenceValidationV2State
    | Reviewer2State
    | SimpleDeepAgentState
)

WorkflowConfig = (
    AboutThisGerConfig
    | DocumentProcessingWorkflowConfig
    | DocumentSummarizationWorkflowConfig
    | ReferenceExtractionConfig
    | ReferenceFileMatchingConfig
    | ClaimReferenceValidationV2Config
    | AbbreviationScanV2Config
    | ReferenceDownloaderWorkflowConfig
    | ReferenceValidationV2WorkflowConfig
    | Reviewer2Config
    | SimpleDeepAgentConfig
)
