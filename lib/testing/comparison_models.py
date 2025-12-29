"""Pydantic models for field comparison results."""

from pydantic import BaseModel, Field


class ComparisonExample(BaseModel):
    """Example of a specific mismatch for debugging.

    Attributes:
        instance_identifier: Unique identifier for the instance (e.g., "claim_text=...")
        expected_value: Serialized expected value as string
        actual_value: Serialized actual value as string
        matched: Whether the values matched
        note: Optional note explaining the mismatch context
    """

    instance_identifier: str
    expected_value: str | None = None
    actual_value: str | None = None
    matched: bool
    note: str | None = None


class FieldComparison(BaseModel):
    """Single field comparison result with full diagnostic info.

    Attributes:
        field_path: Dot-separated path to the field (e.g., "claims.text")
        comparison_type: Type of comparison performed
        total_instances: Total number of instances compared
        passed_instances: Number of instances that passed
        failed_instances: Number of instances that failed
        passed: Overall pass/fail status
        rationale: Human-readable explanation
        examples: List of mismatch examples for debugging
        matching_strategy: Strategy used for array matching (if applicable)
    """

    field_path: str
    comparison_type: str  # "strict" | "llm"
    total_instances: int
    passed_instances: int
    failed_instances: int
    passed: bool
    rationale: str
    examples: list[ComparisonExample] = Field(default_factory=list)
    matching_strategy: str | None = None
