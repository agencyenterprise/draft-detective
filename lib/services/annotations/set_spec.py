"""What an annotation set is, and the question every set asks.

A set is defined in code (one module per eval under ``sets/``) and written to
the database by the sync. Each is built from an issue-inventory eval dataset:
every expected issue and every decoy with an anchor becomes one "should this
passage be flagged?" item.
"""

from pathlib import Path

from pydantic import BaseModel, Field

from lib.services.annotations.models import AnnotationOption, AnnotationQuestion

EVALS_ROOT = Path(__file__).resolve().parents[3] / "evals_inspectai" / "e2e"

SHOULD_FLAG = "should_flag"


class AnnotationSetSpec(BaseModel):
    """A set's definition in code; the sync writes it to the database."""

    slug: str
    title: str
    workflow_type: str
    summary: str
    guidance: str
    questions: list[AnnotationQuestion]
    decoy_reasons: dict[str, str] = Field(
        default_factory=dict,
        description="Plain-language reading of each decoy reason, for the admin results view",
    )

    @property
    def dataset_path(self) -> Path:
        return EVALS_ROOT / self.slug / "dataset.yaml"


# One wording for every set: the rules that make it specific sit right below it.
SHOULD_FLAG_PROMPT = (
    "Should Draft Detective flag the highlighted passage according to the rules below?"
)


def should_flag_question() -> AnnotationQuestion:
    return AnnotationQuestion(
        key=SHOULD_FLAG,
        prompt=SHOULD_FLAG_PROMPT,
        options=[
            AnnotationOption(value="yes", label="Yes, flag it", shortcut="1"),
            AnnotationOption(value="no", label="No, leave it", shortcut="2"),
            AnnotationOption(value="unsure", label="Not sure", shortcut="3"),
        ],
        abstain_value="unsure",
    )
