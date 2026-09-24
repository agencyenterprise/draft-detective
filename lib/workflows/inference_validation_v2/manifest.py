"""Manifest for the Internal Inference Validation workflow.

Flags inferences in the document that are logically invalid: conclusions drawn
but not supported by their premises, or reasoning that relies on a logical
fallacy.

The analysis lives in the `inference-validation` skill
(`skills/inference-validation/SKILL.md`), which is the single source of truth:
it fans out to three independent detection sub-agents, merges their candidates,
and has a separate adjudicator sub-agent decide which survive. The skill is
environment-neutral, so the system prompt below supplies what is specific to
running it here: where the document lives, that sub-agents must be pointed at it
and kept away from the reporting tool, and how the deliverables are delivered.
"""

from lib.workflows.models import WorkflowRunType
from lib.workflows.simple_deep_agent.manifest_base import SimpleDeepAgentManifest

_SYSTEM_PROMPT = """\
You are a specialist document reviewer running the inference-validation skill. \
The user message carries the skill: follow its three-stage procedure exactly.

## Sub-agents

Spawn the skill's detection passes and its adjudicator with the `task` tool, \
using the `general-purpose` sub-agent type.

## Document

The document under review is available at `/main.md`. Every mention of "the \
document under review" in the skill refers to that file. The sub-agents you \
spawn share this filesystem but not your context, so each sub-agent prompt must \
name `/main.md` explicitly — the detection passes and the adjudicator all read \
it themselves. They also have the same tools you do, `view_image` included: \
when a pass needs to see a figure to judge an inference drawn from it, say so \
in its prompt.

## Line ranges

Issue line numbers are 1-indexed against `/main.md`. Before reporting a \
finding, search `/main.md` for its quoted sentence and report the line range \
you find there rather than an estimate.

## Reporting Issues

Call `report_issue` once for each finding that survives adjudication, mapping \
the finding onto the issue fields as the skill's Reporting section specifies \
and following the conventions in the issues skill \
(`/skills/issues/SKILL.md`). You are the only one who calls it: instruct every \
sub-agent you spawn to return its findings as text and never to call \
`report_issue`, since the detection passes deliberately over-flag and their \
candidates are not results. Make no `report_issue` calls for a document whose \
reasoning holds up, and none with severity `none`.

## Report

Write the report described by the skill to `/report.md` using `write_file`. \
This file is the report deliverable: the workflow reads it from the filesystem \
when you finish, and nothing in your final message is used in its place. Write \
the whole report, and if you revise it, write it again in full.\
"""


class InferenceValidationV2Manifest(SimpleDeepAgentManifest):
    """Detects logically invalid inferences in the document."""

    type = WorkflowRunType.INFERENCE_VALIDATION_V2
    name = "Internal Inference Validation"
    description = "Does your reasoning hold up? Flags logical leaps, unsupported conclusions, and arguments where the evidence doesn't support the claim."
    required_dependencies = [WorkflowRunType.DOCUMENT_PROCESSING]
    is_experimental = False

    skill = "inference-validation"
    system_prompt = _SYSTEM_PROMPT

    # A conclusion drawn from a figure can only be checked against the figure.
    view_images = True
