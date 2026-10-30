"""The checks the Word add-in's chat offers to run, by name, from a list.

The same skills the /chat page offers as slash commands (``chat_skill_catalogue``),
narrowed to what the pane's agent can actually do. A check is listed only when it is the
chat form of a workflow, so the list reads like the web app's workflow picker, and only
when it can run without the internet, which the pane's agent does not have:

- a workflow that needs web search is left out;
- an internal workflow (a step other workflows use) is left out;
- citation support is left out too: it judges claims against the cited sources, and
  without the internet there is no way to fetch them.

Experimental workflows are kept, and marked, because the add-in has no user settings to
hide them by.
"""

from pydantic import BaseModel

from lib.agents.chat_agent import EXCLUDED_CHAT_SKILLS, manifest_for_skill
from lib.skills import list_skill_summaries
from lib.workflows.registry import get_all_manifests

NEEDS_SOURCES = frozenset({"citation-support"})


class PaneCheck(BaseModel):
    skill: str
    name: str
    description: str
    experimental: bool = False


def pane_checks() -> list[PaneCheck]:
    """The checks to list in the pane, by name."""

    manifests = get_all_manifests()
    checks: list[PaneCheck] = []
    for skill in list_skill_summaries(exclude=EXCLUDED_CHAT_SKILLS | NEEDS_SOURCES):
        manifest = manifest_for_skill(skill.name, manifests)
        if manifest is None or manifest.needs_web_search or manifest.is_internal:
            continue
        checks.append(
            PaneCheck(
                skill=skill.name,
                name=manifest.name,
                description=manifest.description,
                experimental=manifest.is_experimental,
            )
        )
    return sorted(checks, key=lambda check: (check.experimental, check.name))
