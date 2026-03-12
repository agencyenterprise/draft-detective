"""State definitions for About This (Preface) validation workflow."""

from typing import List, Literal, Optional

from pydantic import BaseModel, Field

from lib.workflows.models import BaseWorkflowConfig, BaseWorkflowState, WorkflowRunType


class RequirementCheckResult(BaseModel):
    """Result for a single requirement check."""

    passed: bool = Field(description="Whether the requirement check passed")
    explanation: str = Field(description="Explanation of the result")
    matched_index: int = Field(
        default=-1,
        description="Index of the sentence/paragraph that satisfied the requirement (-1 if none)",
    )
    matched_text: str = Field(
        default="",
        description="The text that satisfied the requirement (empty if none)",
    )


class AboutThisWorkflowConfig(BaseWorkflowConfig):
    """Configuration for the About This validation workflow."""

    type: Literal[WorkflowRunType.ABOUT_THIS] = Field(WorkflowRunType.ABOUT_THIS)


class AboutThisState(BaseWorkflowState):
    """State for the About This (Preface) validation workflow."""

    type: Literal[WorkflowRunType.ABOUT_THIS] = Field(WorkflowRunType.ABOUT_THIS)
    config: AboutThisWorkflowConfig

    # Section extraction
    found_section: bool = Field(
        default=False, description="Whether a preface section was found"
    )
    section_title: str = Field(
        default="", description="Title of the found section (e.g., 'About This Report')"
    )
    section_text: str = Field(
        default="", description="Full text content of the preface section"
    )

    # Requirement check results
    context: Optional[RequirementCheckResult] = Field(
        default=None, description="Result for: establishes context"
    )
    objectives: Optional[RequirementCheckResult] = Field(
        default=None, description="Result for: explains objectives"
    )
    relationship: Optional[RequirementCheckResult] = Field(
        default=None, description="Result for: explains relationship to RAND work"
    )
    audience: Optional[RequirementCheckResult] = Field(
        default=None, description="Result for: identifies intended audience"
    )
    source_boilerplate: Optional[RequirementCheckResult] = Field(
        default=None, description="Result for: contains CAST boilerplate"
    )
    source_funding: Optional[RequirementCheckResult] = Field(
        default=None, description="Result for: contains funding statement"
    )

    # Overall results
    overall_passed: bool = Field(
        default=False, description="Whether all requirements passed"
    )
    final_summary: str = Field(
        default="", description="Summary of the evaluation (generated if any failed)"
    )

