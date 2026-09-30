"""What Reference Validation is scored on.

Deterministic, per record: the final result, every field's problem type (overall,
and broken out by field so a regression names the field), the fields a correct run
flags and the ones it must leave alone, the corrections it must carry, and the
skill's own contract: the final result follows mechanically from the fields
(Step 6), a found work with an incorrect field gets an updated reference while a
correct or fabricated one gets none, and a URL is given for a found work.

Judged, per record with a labeller's rationale: whether the run's reasoning
reaches the labeller's account of the reference.
"""

import math
from typing import Optional, Sequence

from pydantic import BaseModel, Field

from evals_inspectai.common.issue_inventory import normalize
from evals_inspectai.common.issue_judge import REFERENCE_LABEL, issue_prompt_from
from evals_inspectai.e2e.reference_validation_v2.records import FIELDS, ReferenceRecord


class FieldValidation(BaseModel):
    """Local mirror of BibliographyFieldValidationV2."""

    category: str = ""
    problem_type: str = ""
    current_value: Optional[str] = None
    suggested_value: Optional[str] = None


class ValidationResult(BaseModel):
    """Local mirror of BibliographyItemValidationV2."""

    final_result: str = ""
    original_reference: str = ""
    suggested_action: str = ""
    url: str = ""
    reasoning: str = ""
    updated_reference: Optional[str] = None
    bibliography_field_validations: list[FieldValidation] = Field(default_factory=list)

    def problem(self, field: str) -> Optional[str]:
        """The problem type reported for ``field``, or None when the run gave it no entry."""
        return next((f.problem_type.lower() for f in self.bibliography_field_validations if f.category.lower() == field), None)

    def suggested(self, field: str) -> str:
        return " ".join(f.suggested_value or "" for f in self.bibliography_field_validations if f.category.lower() == field)


class ReferenceValidationItem(BaseModel):
    reference_id: str = ""
    input_reference: str = ""
    status: str = ""
    validation_result: Optional[ValidationResult] = None
    error: Optional[str] = None


class ReferenceValidationOutput(BaseModel):
    """Local mirror of the reference_validation_v2 workflow state."""

    reference_validations: list[ReferenceValidationItem] = Field(default_factory=list)


FIELD_KEYS = tuple(f"field_{f}" for f in FIELDS)
KEYS = (
    "result_correct",
    "field_accuracy",
    *FIELD_KEYS,
    "flags_found",
    "no_false_flags",
    "correction_given",
    "result_follows_fields",
    "updated_reference_as_specified",
    "all_fields_reported",
    "url_when_found",
)


def mechanical_result(result: ValidationResult) -> str:
    """The final result the skill's Step 6 derives from the reported fields: any incorrect
    (or unverifiable) field makes it incorrect_fields, else any missing one missing_fields."""
    problems = {result.problem(f) or "correct" for f in FIELDS}
    if problems & {"incorrect", "other"}:
        return "incorrect_fields"
    return "missing_fields" if "missing" in problems else "correct"


def _share(values: Sequence[bool]) -> float:
    return sum(values) / len(values) if values else math.nan


def _updated_reference_expected(record: ReferenceRecord) -> Optional[bool]:
    """True when the skill requires an updated reference (an incorrect found work, or a bare
    URL, which Step 1 says to reconstruct), False when it forbids one (a correct or fabricated
    reference), None when it leaves it open (another missing field, or a record that accepts
    several results)."""
    if record.not_found or record.result == ["correct"]:
        return False
    if record.result == ["incorrect_fields"] or record.is_bare_url:
        return True
    return None


def validation_scores(result: ValidationResult, record: ReferenceRecord) -> tuple[dict[str, float], str]:
    """Every key in ``KEYS`` for one reference (see the module docstring)."""
    reported = {f: result.problem(f) or "correct" for f in FIELDS}
    right = {f: reported[f] in record.accepted(f) for f in FIELDS}
    to_flag = [f for f in FIELDS if "correct" not in record.accepted(f)]
    to_leave = [f for f in FIELDS if record.accepted(f) == ["correct"]]
    carried = {
        f: any(normalize(p) in normalize(f"{result.suggested(f)} {result.updated_reference or ''}") for p in phrases)
        for f, phrases in record.corrections.items()
    }
    expected_update = _updated_reference_expected(record)
    has_update = bool((result.updated_reference or "").strip())
    values = {
        "result_correct": float(result.final_result in record.result),
        "field_accuracy": _share(list(right.values())),
        **{f"field_{f}": float(right[f]) for f in FIELDS},
        "flags_found": _share([right[f] for f in to_flag]),
        "no_false_flags": _share([right[f] for f in to_leave]),
        "correction_given": _share(list(carried.values())),
        "result_follows_fields": float(result.final_result == mechanical_result(result)),
        "updated_reference_as_specified": math.nan if expected_update is None else float(has_update == expected_update),
        "all_fields_reported": _share([result.problem(f) is not None for f in FIELDS]),
        "url_when_found": math.nan if record.not_found else float(bool(result.url.strip())),
    }
    notes = [f"result {result.final_result}, expected {'/'.join(record.result)}"] if not values["result_correct"] else []
    notes += [f"{f}: reported {reported[f]}, expected {'/'.join(record.accepted(f))}" for f in FIELDS if not right[f]]
    notes += [f"{f} correction lacks {' or '.join(repr(p) for p in record.corrections[f])}" for f, ok in carried.items() if not ok]
    notes += [f"final result {result.final_result} does not follow from the fields ({mechanical_result(result)})"] if not values["result_follows_fields"] else []
    unreported = [f for f in FIELDS if result.problem(f) is None]
    notes += [f"no entry for {', '.join(unreported)}"] if unreported else []
    notes += ["no URL for a work that exists"] if values["url_when_found"] == 0.0 else []
    if expected_update is not None and has_update != expected_update:
        notes.append("updated reference given where none belongs" if has_update else "no updated reference where the skill requires one")
    return values, " | ".join(notes) if notes else "every field as labelled"


REASONING_CRITERION = (
    "A citation validator checked a bibliographic reference against sources it found on the web, and the "
    "labeller has described what is actually right or wrong with the reference. Grade whether the validator's "
    "reasoning and suggested action reach the labeller's account: the same verdict on the same fields for the "
    "same reason (a misspelled surname, a venue that is really an arXiv preprint, a fabricated work, a year "
    "within the one-year tolerance), in any words. It is correct if it matches the account, even with extra "
    "sound detail. It is partially correct if it reaches the right verdict for a different or vaguer reason, or "
    "matches on some fields but misreads another. It is incorrect if it reaches a different verdict, validates a "
    "fabricated reference, or treats a different work as the cited one."
)


def reasoning_prompt(record: ReferenceRecord, result: ValidationResult) -> str:
    fields = "\n".join(
        f"- {f.category}: {f.problem_type} (cited {f.current_value!r}, suggested {f.suggested_value!r})"
        for f in result.bibliography_field_validations
    )
    return issue_prompt_from(
        REASONING_CRITERION,
        [
            ("Reference", record.reference),
            (REFERENCE_LABEL, record.rationale or ""),
            ("Validator's final result", result.final_result),
            ("Validator's field validations", fields or "(none)"),
            ("Validator's reasoning", result.reasoning or "(none)"),
            ("Validator's suggested action", result.suggested_action or "(none)"),
        ],
    )


DESCRIPTIONS = {
    "result_correct": "1 if the final result is one the record accepts (correct, missing_fields or incorrect_fields).",
    "field_accuracy": "Share of the five fields (author, title, publisher, year, identifier) given a problem type the record accepts; a field the run leaves out counts as correct.",
    **{f"field_{f}": f"1 if {f} gets a problem type the record accepts." for f in FIELDS},
    "flags_found": "Of the fields the record says must be flagged (missing or incorrect), share flagged as labelled. NaN when none must be.",
    "no_false_flags": "Of the fields the record says are correct, share left correct. NaN when none is.",
    "correction_given": "Share of the record's corrections found, in any of their accepted forms, in the field's suggested value or the updated reference. NaN when the record has none.",
    "result_follows_fields": "1 if the final result is the one the skill's Step 6 derives from the reported fields.",
    "updated_reference_as_specified": "1 if an updated reference is given exactly when the skill requires one: for an incorrect found work or a bare URL, and never for a correct or fabricated reference. NaN when the skill leaves it open.",
    "all_fields_reported": "Share of the five fields the run reports an entry for.",
    "url_when_found": "1 if a URL is given for a reference that exists. NaN for a fabricated one.",
}
JUDGE_DESCRIPTIONS = {
    "reasoning_matches": "Graded per record with a labeller's rationale: the reasoning and suggested action reach the labeller's account of the reference (C=1, P=0.5, I=0).",
}
