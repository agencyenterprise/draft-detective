"""Skill-declared workflows: a SKILL.md with a draft_detective block, and nothing else.

Covers the spec reader (`lib/skill_workflow_spec.py`), the manifest builder
(`lib/workflows/skill_workflows.py`), and what the registry and the
workflow-types service do with the result, using `active-voice` as the live
example and temporary skill trees for the failure modes.
"""

from pathlib import Path

import pytest
from pydantic import ValidationError

from lib.services.workflow_types import get_all_workflow_types
from lib.skill_workflow_spec import (
    SkillWorkflowSpec,
    ensure_valid_type_slug,
    read_all_skill_workflow_declarations,
    read_skill_workflow_declaration,
)
from lib.workflows.models import WorkflowRunType
from lib.workflows.registry import get_all_manifests, get_workflow_manifest
from lib.workflows.skill_workflows import (
    SkillWorkflowError,
    SkillWorkflowManifest,
    discover_skill_workflows,
)

_REPO_ROOT = Path(__file__).parents[3]
_SKILLS_DIR = _REPO_ROOT / "skills"


def _write_skill(root: Path, name: str, declaration: str, body: str = "# Rules\n") -> Path:
    """A skill file whose ``metadata.draft_detective`` block is ``declaration``
    (YAML lines indented by four spaces)."""
    skill_dir = root / name
    skill_dir.mkdir(parents=True)
    skill_file = skill_dir / "SKILL.md"
    skill_file.write_text(
        "---\n"
        f"name: {name}\n"
        "description: A test skill.\n"
        "metadata:\n"
        "  draft_detective:\n"
        f"{declaration}"
        "---\n\n" + body
    )
    return skill_file


# --- the live example -------------------------------------------------------


def test_the_enum_grows_a_member_per_declaring_skill():
    """No line in WorkflowRunType: the member comes from the skill's frontmatter."""
    for declaration in read_all_skill_workflow_declarations(_SKILLS_DIR):
        slug = declaration.type_slug
        member = WorkflowRunType(slug)
        assert member.value == slug
        assert member.name == slug.upper()
        assert WorkflowRunType[slug.upper()] is member
        assert getattr(WorkflowRunType, slug.upper()) is member
        assert member in list(WorkflowRunType)
        assert isinstance(member, str) and member == slug


def test_active_voice_is_registered_from_its_skill_alone():
    manifest = get_workflow_manifest(WorkflowRunType("active_voice"))

    assert isinstance(manifest, SkillWorkflowManifest)
    assert manifest.skill == "active-voice"
    assert manifest.name == "Active Voice & Clear Actors"
    assert manifest.category == "language"
    assert manifest.icon == "pen-line"
    assert manifest.is_experimental is True
    assert manifest.required_dependencies == [WorkflowRunType.DOCUMENT_PROCESSING]
    assert manifest.propose_edits is True
    # No hand-written manifest module exists for it.
    assert not (_REPO_ROOT / "lib" / "workflows" / "active_voice").exists()


def test_active_voice_prompt_is_the_skill_body():
    manifest = get_workflow_manifest(WorkflowRunType("active_voice"))
    prompt = manifest.resolve_user_prompt()

    assert prompt.startswith("# Active Voice & Clear Actors")
    assert "metadata:" not in prompt, "frontmatter must be stripped from the prompt"


def test_active_voice_lands_in_its_category_in_the_api():
    response = get_all_workflow_types()

    active_voice = WorkflowRunType("active_voice")
    language = next(c for c in response.categories if c.slug == "language")
    assert active_voice in language.workflows
    # Appended after the hand-written members, not in front of them.
    assert language.workflows.index(WorkflowRunType.ADVOCACY_TONE_V2) < language.workflows.index(
        active_voice
    )

    described = next(w for w in response.workflow_types if w.type == active_voice)
    assert described.category == "language"
    assert described.icon == "pen-line"
    assert described.proposes_edits is True


def test_hand_written_manifests_are_untouched_by_the_new_field():
    """Existing workflows expose no icon, so the frontend keeps its own map for them."""
    response = get_all_workflow_types()
    by_type = {w.type: w for w in response.workflow_types}

    assert by_type[WorkflowRunType.ADVOCACY_TONE_V2].icon is None
    assert by_type[WorkflowRunType.REFERENCE_VALIDATION_V2].icon is None
    assert by_type[WorkflowRunType.ADVOCACY_TONE_V2].proposes_edits is False


def test_every_declaring_skill_on_disk_is_registered():
    """The bridge between skills/ and the registry has no gaps."""
    declared = {d.type_slug for d in read_all_skill_workflow_declarations(_SKILLS_DIR)}
    registered = {
        m.type.value for m in get_all_manifests().values() if isinstance(m, SkillWorkflowManifest)
    }
    assert declared == registered
    assert declared, "expected at least one skill-declared workflow"


# --- the spec ----------------------------------------------------------------


def test_spec_rejects_unknown_keys():
    with pytest.raises(ValidationError):
        SkillWorkflowSpec.model_validate(
            {"title": "X", "category": "language", "colour": "blue"}
        )


def test_spec_requires_title_and_category():
    with pytest.raises(ValidationError):
        SkillWorkflowSpec.model_validate({"title": "X"})


def test_skill_without_a_declaration_is_not_a_workflow(tmp_path: Path):
    skill_dir = tmp_path / "plain"
    skill_dir.mkdir()
    skill_file = skill_dir / "SKILL.md"
    skill_file.write_text("---\nname: plain\ndescription: d\n---\n# Body\n")

    assert read_skill_workflow_declaration(skill_file) is None
    assert discover_skill_workflows(tmp_path) == []


def test_metadata_that_is_not_a_mapping_declares_no_workflow(tmp_path: Path):
    skill_dir = tmp_path / "noted"
    skill_dir.mkdir()
    skill_file = skill_dir / "SKILL.md"
    skill_file.write_text("---\nname: noted\ndescription: A skill.\nmetadata: just a note\n---\n\n# Rules\n")

    assert read_skill_workflow_declaration(skill_file) is None
    assert discover_skill_workflows(tmp_path) == []


def test_type_slug_defaults_to_the_skill_name(tmp_path: Path):
    skill_file = _write_skill(tmp_path, "active-voice", "    title: T\n    category: language\n")
    declaration = read_skill_workflow_declaration(skill_file)

    assert declaration is not None
    assert declaration.type_slug == "active_voice"
    assert declaration.picker_description == "A test skill."


def test_proposed_edits_are_off_unless_declared(tmp_path: Path):
    _write_skill(tmp_path, "active-voice", "    title: T\n    category: language\n")
    (manifest,) = discover_skill_workflows(tmp_path)

    assert manifest.propose_edits is False


def test_explicit_type_and_description_win(tmp_path: Path):
    skill_file = _write_skill(
        tmp_path,
        "whatever",
        "    title: T\n    category: language\n    type: active_voice\n    description: Picker text.\n",
    )
    declaration = read_skill_workflow_declaration(skill_file)

    assert declaration is not None
    assert declaration.type_slug == "active_voice"
    assert declaration.picker_description == "Picker text."


# --- failure modes name the skill and the fix ------------------------------


def test_skill_outside_the_skills_directory_has_no_member(tmp_path: Path):
    """The enum is extended from skills/ at import; a skill elsewhere is not in it."""
    _write_skill(tmp_path, "brand-new-check", "    title: T\n    category: language\n")

    with pytest.raises(SkillWorkflowError, match="not a WorkflowRunType member"):
        discover_skill_workflows(tmp_path)


@pytest.mark.parametrize("slug", ["active_voice", "x", "a1_b2"])
def test_valid_type_slugs_pass(slug: str):
    assert ensure_valid_type_slug(slug, "s") == slug


@pytest.mark.parametrize("slug", ["Active_Voice", "active-voice", "_x", "x__y", "x_", "1x", ""])
def test_invalid_type_slugs_are_rejected(slug: str):
    with pytest.raises(ValueError, match="type slug"):
        ensure_valid_type_slug(slug, "s")


def test_unknown_category_fails_loudly(tmp_path: Path):
    _write_skill(tmp_path, "active-voice", "    title: T\n    category: nonsense\n")

    with pytest.raises(SkillWorkflowError, match="nonsense"):
        discover_skill_workflows(tmp_path)


def test_unknown_dependency_fails_loudly(tmp_path: Path):
    _write_skill(
        tmp_path,
        "active-voice",
        "    title: T\n    category: language\n    required_dependencies: [no_such_workflow]\n",
    )

    with pytest.raises(SkillWorkflowError, match="no_such_workflow"):
        discover_skill_workflows(tmp_path)


def test_malformed_block_fails_loudly(tmp_path: Path):
    _write_skill(tmp_path, "active-voice", "    title: T\n    category: language\n    bogus: 1\n")

    with pytest.raises(SkillWorkflowError, match="bogus"):
        discover_skill_workflows(tmp_path)


def test_built_manifest_carries_every_declared_option(tmp_path: Path):
    _write_skill(
        tmp_path,
        "active-voice",
        "    title: T\n"
        "    category: language\n"
        "    experimental: false\n"
        "    icon: scan-text\n"
        "    view_images: true\n"
        "    web_search: true\n"
        "    reasoning_effort: high\n"
        "    propose_edits: true\n",
    )
    (manifest,) = discover_skill_workflows(tmp_path)

    assert manifest.type == WorkflowRunType("active_voice")
    assert manifest.is_experimental is False
    assert manifest.icon == "scan-text"
    assert manifest.view_images is True
    assert manifest.needs_web_search is True
    assert manifest.reasoning_effort == "high"
    assert manifest.propose_edits is True
    assert manifest.skill_file == tmp_path / "active-voice" / "SKILL.md"
