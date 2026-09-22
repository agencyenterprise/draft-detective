"""Workflows declared entirely by a skill file.

A skill whose SKILL.md frontmatter carries a ``metadata.draft_detective``
block (see ``lib/skill_workflow_spec.py``) becomes a ``SimpleDeepAgentManifest``
here, with no ``manifest.py``, registry import, or category entry of its own.
The registry calls ``discover_skill_workflows()`` after registering the
hand-written manifests.

The skill's ``WorkflowRunType`` member is added at import time as well, by
``lib/workflows/models.py`` reading the same declarations, so the enum's
hand-written members stay static while skill-declared ones need no line there.

Only skill-backed single-pass checks go through this path. Workflows with their
own graphs keep their explicit manifests.
"""

from pathlib import Path
from typing import ClassVar, Optional, cast

from pydantic import ValidationError

from lib.skill_workflow_spec import (
    SkillWorkflowDeclaration,
    read_all_skill_workflow_declarations,
)
from lib.workflows.categories import WORKFLOW_DISPLAY_CONFIG
from lib.workflows.models import WorkflowRunType
from lib.workflows.simple_deep_agent.manifest_base import SimpleDeepAgentManifest


class SkillWorkflowError(ValueError):
    """A skill declares a workflow that cannot be wired up."""


class SkillWorkflowManifest(SimpleDeepAgentManifest):
    """Base for manifests built from a skill's frontmatter.

    Adds the display attributes a hand-written manifest gets from
    ``categories.py`` and the frontend's per-type maps: the picker category and
    an icon name. Concrete subclasses are created at discovery time, one per
    declaring skill.
    """

    category: ClassVar[str]
    icon: ClassVar[Optional[str]] = None
    skill_file: ClassVar[Path]


def _workflow_type_for(declaration: SkillWorkflowDeclaration) -> WorkflowRunType:
    slug = declaration.type_slug
    try:
        return WorkflowRunType(slug)
    except ValueError as e:
        raise SkillWorkflowError(
            f"skill '{declaration.skill_name}' declares workflow type '{slug}', "
            "which is not a WorkflowRunType member. Members for skill-declared "
            "workflows are added from skills/*/SKILL.md when lib.workflows.models "
            "is imported, so the skill is outside that directory or was added "
            "after the process started."
        ) from e


def _dependency_type(declaration: SkillWorkflowDeclaration, slug: str) -> WorkflowRunType:
    try:
        return WorkflowRunType(slug)
    except ValueError as e:
        raise SkillWorkflowError(
            f"skill '{declaration.skill_name}' lists unknown dependency '{slug}'"
        ) from e


def _check_category(declaration: SkillWorkflowDeclaration) -> None:
    known = [category.slug for category in WORKFLOW_DISPLAY_CONFIG]
    if declaration.spec.category not in known:
        raise SkillWorkflowError(
            f"skill '{declaration.skill_name}' names category "
            f"'{declaration.spec.category}'; known categories are {known}"
        )


def build_skill_workflow_manifest(
    declaration: SkillWorkflowDeclaration,
) -> SkillWorkflowManifest:
    """A manifest class for one declaring skill, instantiated."""
    _check_category(declaration)
    spec = declaration.spec
    workflow_type = _workflow_type_for(declaration)
    class_name = "".join(part.title() for part in workflow_type.value.split("_"))
    attrs = {
        "__doc__": f"Skill-declared workflow backed by skills/{declaration.skill_name}/SKILL.md.",
        "__module__": __name__,
        "type": workflow_type,
        "name": spec.title,
        "description": declaration.picker_description,
        "skill": declaration.skill_name,
        "skill_file": declaration.skill_file,
        "category": spec.category,
        "icon": spec.icon,
        "is_experimental": spec.experimental,
        "needs_web_search": spec.web_search,
        "view_images": spec.view_images,
        "reasoning_effort": spec.reasoning_effort,
        "propose_edits": spec.propose_edits,
        "required_dependencies": [
            _dependency_type(declaration, slug) for slug in spec.required_dependencies
        ],
    }
    manifest_cls = cast(
        type[SkillWorkflowManifest],
        type(f"{class_name}SkillManifest", (SkillWorkflowManifest,), attrs),
    )
    return manifest_cls()


def discover_skill_workflows(
    skills_dir: Optional[Path] = None,
) -> list[SkillWorkflowManifest]:
    """One manifest per skill that declares a workflow block.

    Malformed declarations raise ``SkillWorkflowError`` naming the skill: a
    check that was meant to exist should fail loudly rather than vanish from
    the picker.
    """
    try:
        declarations = read_all_skill_workflow_declarations(skills_dir)
    except ValidationError as e:
        raise SkillWorkflowError(f"invalid draft_detective block in a skill: {e}") from e
    return [build_skill_workflow_manifest(d) for d in declarations]
