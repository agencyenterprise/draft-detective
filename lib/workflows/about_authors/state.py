"""State definitions for About Authors validation workflow."""

from typing import List, Literal, Optional, Union

from pydantic import BaseModel, Field

from lib.workflows.models import BaseWorkflowConfig, BaseWorkflowState, WorkflowRunType


class RuleCheckResult(BaseModel):
    """Result for a single rule check."""

    passed: bool = Field(description="Whether the rule check passed")
    explanation: str = Field(description="Explanation of the result")
    applicable: bool = Field(default=True, description="Whether this rule applies")


class AuthorValidationResult(BaseModel):
    """Validation result for a single author bio."""

    author_id: str = Field(description="Paragraph ID from document")
    author_text: str = Field(description="Raw author bio text")
    author_name: str = Field(description="Extracted author name")
    author_name_positions: List[int] = Field(
        default_factory=list,
        description="0-indexed token positions for name highlighting",
    )
    chunk_indices: List[int] = Field(
        default_factory=list,
        description="Chunk indices this author bio spans (for Document Explorer)",
    )

    # Rule checks
    rule_1_sentence_length: RuleCheckResult = Field(
        description="Rule 1: Bio must be exactly 3 sentences"
    )
    rule_2_position_affiliation: RuleCheckResult = Field(
        description="Rule 2: Must include position and affiliation"
    )
    rule_3_tasp_statement: RuleCheckResult = Field(
        description="Rule 3: If TASP fellow, must include TASP statement"
    )
    rule_4_research_focus: RuleCheckResult = Field(
        description="Rule 4: Must include research focus"
    )
    rule_5_highest_degree: RuleCheckResult = Field(
        description="Rule 5: Must include highest degree"
    )

    # Final judgment
    overall_passed: bool = Field(description="Whether all applicable rules passed")
    final_comment: str = Field(description="Final pass/fail comment")
    guidance: Optional[str] = Field(
        default=None, description="Guidance for fixing failed rules"
    )


class AboutAuthorsWorkflowConfig(BaseWorkflowConfig):
    """Configuration for the About Authors validation workflow."""

    type: Literal[WorkflowRunType.ABOUT_AUTHORS] = Field(WorkflowRunType.ABOUT_AUTHORS)


class AboutAuthorsState(BaseWorkflowState):
    """State for the About Authors validation workflow."""

    type: Literal[WorkflowRunType.ABOUT_AUTHORS] = Field(WorkflowRunType.ABOUT_AUTHORS)
    config: AboutAuthorsWorkflowConfig
    results: List[AuthorValidationResult] = Field(default_factory=list)
