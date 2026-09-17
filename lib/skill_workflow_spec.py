"""The workflow declaration a skill may carry in its SKILL.md frontmatter.

A skill under ``skills/`` can become a Draft Detective assessment on its own by
carrying a ``metadata.draft_detective`` block in its YAML frontmatter. This
module owns that block: the schema, how it is read from a skill file, and how
the workflow slug is derived. It deliberately imports nothing from the
workflow machinery so that lightweight callers (the eval task discovery, tests)
can read specs without pulling in LangGraph.

Frontmatter shape, with every accepted field (only ``title`` and ``category``
are required; the values shown for the others are their defaults unless the
comment says otherwise)::

    ---
    name: active-voice
    description: Use this skill to ...        # what the agent reads when picking skills
    metadata:
      draft_detective:
        title: Active Voice & Clear Actors    # required; name in the assessment picker
        category: language                   # required; a slug from lib/workflows/categories.py
        description: Does your prose ...      # picker text; defaults to the skill description
        type: active_voice                    # WorkflowRunType slug; defaults to name with _ for -
        experimental: true                    # hidden unless the user opts into alpha checks
        icon: pen-line                        # lucide icon name; defaults to the frontend's fallback
        view_images: false                    # let the agent look at the document's images
        web_search: false                     # give the agent web search (gates on user consent)
        reasoning_effort: medium              # low | medium | high; defaults to the agent's default
        propose_edits: false                  # let issues carry verbatim-quote text replacements
        required_dependencies: [document_processing]
    ---

The block lives under ``metadata`` because the Agent Skills format reserves
that key for host-specific data: other runtimes that install the skill ignore
it, so the skill stays portable.
"""

import re
from pathlib import Path
from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field

from lib.skills import iter_skill_files, read_skill_frontmatter

# A workflow type slug: lowercase words joined by single underscores, the same
# shape as every hand-written WorkflowRunType value.
WORKFLOW_TYPE_SLUG_RE = re.compile(r"^[a-z][a-z0-9]*(?:_[a-z0-9]+)*$")


def ensure_valid_type_slug(slug: str, skill_name: str) -> str:
    """Return ``slug`` if it can be a WorkflowRunType value, else raise ValueError."""
    if not WORKFLOW_TYPE_SLUG_RE.match(slug):
        raise ValueError(
            f"skill '{skill_name}' would declare workflow type '{slug}'; a type slug "
            "must be lowercase words joined by single underscores (set `type:` "
            "explicitly if the skill name does not convert cleanly)"
        )
    return slug


class SkillWorkflowSpec(BaseModel):
    """What a skill declares to run as a workflow. Unknown keys are rejected."""

    model_config = ConfigDict(extra="forbid")

    title: str = Field(description="Display name in the assessment picker")
    description: Optional[str] = Field(
        default=None,
        description=(
            "Picker description. Falls back to the skill's own description, "
            "which is usually phrased for an agent rather than a person, so "
            "set this."
        ),
    )
    category: str = Field(
        description="Slug of a category in lib/workflows/categories.py"
    )
    type: Optional[str] = Field(
        default=None,
        description=(
            "WorkflowRunType slug. Defaults to the skill name with dashes "
            "replaced by underscores."
        ),
    )
    experimental: bool = Field(
        default=True, description="Hidden unless the user opts into alpha checks"
    )
    icon: Optional[str] = Field(
        default=None, description="lucide icon name in kebab-case, e.g. pen-line"
    )
    view_images: bool = Field(
        default=False,
        description=(
            "Let the agent look at the document's extracted images. Only for checks "
            "whose judgment can hinge on what a figure shows."
        ),
    )
    web_search: bool = Field(
        default=False,
        description=(
            "Give the agent the web search tool. This also gates the run on the "
            "user's web-search consent, so the skill body must work without it."
        ),
    )
    reasoning_effort: Optional[Literal["low", "medium", "high"]] = Field(
        default=None,
        description="LLM reasoning effort for the run; None keeps the agent's default.",
    )
    propose_edits: bool = Field(
        default=False,
        description=(
            "Let the agent attach proposed edits (verbatim quote plus replacement) "
            "to its issues; the skill body must say when an edit is warranted."
        ),
    )
    required_dependencies: list[str] = Field(default_factory=lambda: ["document_processing"])


class SkillWorkflowDeclaration(BaseModel):
    """A parsed declaration together with the skill it came from."""

    skill_name: str
    skill_description: str
    skill_file: Path
    spec: SkillWorkflowSpec

    @property
    def type_slug(self) -> str:
        slug = self.spec.type or self.skill_name.replace("-", "_")
        return ensure_valid_type_slug(slug, self.skill_name)

    @property
    def picker_description(self) -> str:
        return self.spec.description or self.skill_description


def read_skill_workflow_declaration(
    skill_file: Path,
) -> Optional[SkillWorkflowDeclaration]:
    """The workflow declaration of one skill file, or None when it has none.

    Raises ``pydantic.ValidationError`` when the block is present but malformed,
    so a typo in a skill fails loudly instead of silently dropping the check.
    """
    frontmatter = read_skill_frontmatter(skill_file)
    if frontmatter is None:
        return None
    metadata = frontmatter.get("metadata")
    if not isinstance(metadata, dict):
        # No metadata, or metadata that is not a mapping (a bare string, say):
        # either way the skill declares no workflow.
        return None
    block = metadata.get("draft_detective")
    if block is None:
        return None
    return SkillWorkflowDeclaration(
        skill_name=str(frontmatter.get("name") or skill_file.parent.name),
        skill_description=str(frontmatter.get("description") or "").strip(),
        skill_file=skill_file,
        spec=SkillWorkflowSpec.model_validate(block),
    )


def read_all_skill_workflow_declarations(
    skills_dir: Optional[Path] = None,
) -> list[SkillWorkflowDeclaration]:
    """Every skill on disk that declares a workflow, in skill-name order."""
    declarations = []
    for skill_file in iter_skill_files(skills_dir):
        declaration = read_skill_workflow_declaration(skill_file)
        if declaration is not None:
            declarations.append(declaration)
    return declarations
