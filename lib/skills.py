"""Load a skill's markdown body for use as an agent/workflow prompt.

Skills under the repo-root `skills/` directory are the single source of truth
for the prompts and rules used by agents and deep-agent workflows. Code
references a skill by name (e.g. ``"reviewer-2"``) and loads its body here,
rather than duplicating the prompt text in Python.

A skill may carry sections that only make sense when the skill is driven by an
agent talking to a user (e.g. asking for web-search consent). Those are wrapped
in a ``<!-- interactive-only:start -->`` / ``<!-- interactive-only:end -->``
pair and stripped here: on the backend the same gate is already enforced before
the run starts, by the UI or by the MCP consent gate, and there is nobody for
the agent to ask mid-run. Both markers are required — an unclosed section is
left in place, which `tests/unit/test_skills.py` fails on.
"""

import logging
import re
from collections.abc import Collection
from pathlib import Path

import yaml
from pydantic import BaseModel

logger = logging.getLogger(__name__)

# Repo root: lib/skills.py -> parents[1]
_SKILLS_DIR = Path(__file__).parents[1] / "skills"

# Sections addressed to an interactive agent, not to a backend workflow run.
INTERACTIVE_ONLY_START = "<!-- interactive-only:start -->"
INTERACTIVE_ONLY_END = "<!-- interactive-only:end -->"

# Consumes the blank line after the block too, so removing a section that sat
# between two others doesn't leave a gap behind.
_INTERACTIVE_ONLY_RE = re.compile(
    rf"[ \t]*{re.escape(INTERACTIVE_ONLY_START)}.*?{re.escape(INTERACTIVE_ONLY_END)}[ \t]*\n*",
    re.DOTALL,
)

# Just the two marker comments, for the setting where the section itself stays.
_INTERACTIVE_MARKER_RE = re.compile(
    rf"[ \t]*(?:{re.escape(INTERACTIVE_ONLY_START)}|{re.escape(INTERACTIVE_ONLY_END)})[ \t]*\n?"
)


class SkillSummary(BaseModel):
    """What a skill picker needs to show: the frontmatter, not the body."""

    name: str
    description: str


def load_skill_prompt(skill_name: str) -> str:
    """Return the markdown body of ``skills/<skill_name>/SKILL.md``.

    The YAML frontmatter block and any interactive-only sections are stripped;
    the remaining markdown is the prompt/rules used by the caller.
    """
    skill_path = _SKILLS_DIR / skill_name / "SKILL.md"
    if not skill_path.is_file():
        raise FileNotFoundError(f"Skill '{skill_name}' not found at {skill_path}")
    return strip_interactive_only(_strip_frontmatter(skill_path.read_text()))


def strip_interactive_only(content: str) -> str:
    """Remove any interactive-only sections from a skill's markdown.

    Frontmatter (when present) is left in place, so this is also what mounts a
    raw SKILL.md into a deep agent's filesystem for the agent to read itself.
    """
    if INTERACTIVE_ONLY_START not in content:
        return content
    return _INTERACTIVE_ONLY_RE.sub("", content)


def strip_interactive_markers(content: str) -> str:
    """Keep the interactive-only sections, drop the marker comments around them.

    The counterpart of ``strip_interactive_only`` for an agent that does have a
    user to ask, such as the chat page. The sections apply there; only the
    markers, which exist for the backend loader, are noise.
    """
    if INTERACTIVE_ONLY_START not in content and INTERACTIVE_ONLY_END not in content:
        return content
    return _INTERACTIVE_MARKER_RE.sub("", content)


def list_skill_summaries(exclude: Collection[str] = ()) -> list[SkillSummary]:
    """Name and description of every skill on disk, in name order.

    Skills whose SKILL.md has no parseable frontmatter with both fields are
    left out rather than shown with a blank description. A malformed block is
    logged and skipped, so one broken skill cannot take the whole list down.
    """
    summaries: list[SkillSummary] = []
    for skill_dir in sorted(_SKILLS_DIR.iterdir()):
        skill_file = skill_dir / "SKILL.md"
        if skill_dir.name in exclude or not skill_file.is_file():
            continue
        summary = _skill_summary(skill_file)
        if summary is not None:
            summaries.append(summary)
    return summaries


def _skill_summary(skill_file: Path) -> SkillSummary | None:
    frontmatter = _frontmatter_block(skill_file.read_text(encoding="utf-8"))
    if frontmatter is None:
        return None
    try:
        parsed = yaml.safe_load(frontmatter)
    except yaml.YAMLError:
        logger.warning("skipping skill with malformed frontmatter: %s", skill_file)
        return None
    if not isinstance(parsed, dict):
        return None
    name, description = parsed.get("name"), parsed.get("description")
    if not isinstance(name, str) or not isinstance(description, str):
        return None
    return SkillSummary(name=name, description=description.strip())


def _frontmatter_block(content: str) -> str | None:
    """The YAML between the leading ``---`` delimiters, or None when absent."""
    if not content.startswith("---"):
        return None
    lines = content.splitlines()
    for i in range(1, len(lines)):
        if lines[i].strip() == "---":
            return "\n".join(lines[1:i])
    return None


def _strip_frontmatter(content: str) -> str:
    """Remove a leading YAML frontmatter block (``--- ... ---``) if present."""
    if not content.startswith("---"):
        return content

    lines = content.splitlines()
    for i in range(1, len(lines)):
        if lines[i].strip() == "---":
            return "\n".join(lines[i + 1 :]).lstrip("\n")

    # No closing delimiter found — return content unchanged.
    return content
