# Skill-declared workflows

Most Draft Detective checks are a single deep-agent pass over the document, driven by
the rules in a skill file. For that kind of check the skill file is the whole
definition: a `SKILL.md` with a `draft_detective` block in its frontmatter becomes a
workflow in the API, the assessment picker, and the results view, with no Python
manifest, registry entry, category entry, or frontend mapping to write.

Workflows with their own graphs (several nodes, custom state, bespoke result views)
still use a hand-written manifest under `lib/workflows/<name>/`. This document covers
the skill-declared kind only.

## Creating a workflow

1. Create `skills/<skill-name>/SKILL.md`. Use a kebab-case name; it doubles as the
   workflow type slug with dashes turned into underscores (`active-voice` becomes
   `active_voice`).
2. Add a `draft_detective` block under `metadata` in the frontmatter. `title` and
   `category` are required; everything else has a default.
3. Write the rules in the body, following the conventions below.
4. Optionally add an eval dataset at `evals_inspectai/e2e/<slug>/dataset.yaml`.

That is all. On the next backend start the workflow is registered and appears in its
category. The unit test suite checks the wiring (`tests/unit/workflows/test_skill_workflows.py`).

### Frontmatter reference

```yaml
---
name: active-voice
description: Use this skill to ...            # what an agent reads when choosing skills
metadata:
  draft_detective:
    title: Active Voice & Clear Actors        # required; name in the assessment picker
    category: language                       # required; a slug from lib/workflows/categories.py
    description: Does your prose ...          # picker text; defaults to the skill description
    type: active_voice                        # WorkflowRunType slug; defaults to name with _ for -
    experimental: true                        # default true; hidden unless the user opts into alpha checks
    icon: pen-line                            # lucide icon name (kebab-case); frontend default if omitted
    view_images: false                        # let the agent look at the document's extracted images
    web_search: false                         # give the agent web search; gates the run on user consent
    reasoning_effort: medium                  # low | medium | high; the agent's default if omitted
    propose_edits: false                      # let issues carry verbatim-quote text replacements
    required_dependencies: [document_processing]
---
```

The block sits under `metadata` because the Agent Skills format reserves that key for
host-specific data. Other runtimes that install the skill as a plugin ignore it, so the
skill stays portable. Unknown keys are rejected, and a malformed block fails at import
naming the skill and the problem, rather than silently leaving the check out of the picker.

`description` deserves a real value. The skill's own description is written for an
agent deciding whether to use the skill ("Use this skill to ..."); the picker text is
read by a person choosing an assessment, and the other checks phrase it as a question
("Does your document ...?").

### Writing the skill body

The body is the agent's user prompt, unchanged. The existing skill-backed checks are
the pattern to follow; `skills/advocacy-tone/SKILL.md` and `skills/active-voice/SKILL.md`
are good models.

- Say what counts and, just as carefully, what does not. False positives are what
  makes a check unusable; write the exclusions as concrete examples.
- Use stable issue titles and fixed severities, and state them in a Reporting section.
  Evals score on title counts, and reviewers learn to scan for them.
- Point at the issues skill for the output contract: "Report issues following the
  conventions defined in the issues skill (`/skills/issues/SKILL.md`)". That skill is
  mounted alongside yours and defines every field, including proposed edits.
- Say how many issues to emit per finding (one per occurrence, one per paragraph, one
  per document) and, for checks that can fire on most paragraphs, add a cap with a
  single summary issue once it is reached.
- Ask for a short report: what was checked, what was found, what was skipped.
- Stay environment-agnostic. Skills ship as a plugin to other runtimes, so never name
  a tool of this repo's agent; write "when you have a way to view images" or "when you
  can attach proposed edits". `tests/unit/test_skills.py` fails on known tool names.
- Sections meant only for an interactive session (asking for web-search consent, say)
  go between `<!-- interactive-only:start -->` and `<!-- interactive-only:end -->`
  markers; the backend strips them.

### Proposed edits

Set `propose_edits: true` when the check can sometimes give a fully mechanical fix.
The agent's issue tool then accepts an `edits` list (verbatim quote, replacement,
rationale), and every quote is located in the document before the issue is stored. The
body must say when an edit is warranted and when it is not; the rule in the issues
skill is that an edit is only proposed when the fix is fully determined by the
document text plus the finding, never when it needs a new fact or new prose.

## How it is wired

- `lib/skill_workflow_spec.py` reads and validates the block (`SkillWorkflowSpec`) and
  derives the type slug. It imports nothing heavy, so evals and tests can use it.
- `lib/workflows/models.py` extends `WorkflowRunType` at import time with one member
  per declared slug, using `aenum.extend_enum`, before any model that validates against
  the enum is built. Hand-written members stay static because code refers to them by
  name; skill-declared members are only ever reached through their slug. A slug that
  collides with an existing value or name raises.
- `lib/workflows/skill_workflows.py` builds a `SimpleDeepAgentManifest` subclass per
  declaring skill. `lib/workflows/registry.py` registers them after the hand-written
  manifests and refuses a skill that names an existing workflow type.
- `lib/services/workflow_types.py` appends each skill-declared workflow to its
  category and returns its `icon` in the workflow-types API.
- Frontend: the picker draws a declared icon with lucide's `DynamicIcon`, the state
  type map falls back to `SimpleDeepAgentState` for any type it does not list, and the
  results renderer's default branch shows the deep-agent results view. No per-type edit
  is needed.

## Evals

Add `evals_inspectai/e2e/<slug>/dataset.yaml` and the task exists as
`evals_inspectai/e2e/skill_workflows_e2e.py@<slug>_e2e`; that module discovers every
declared workflow with a dataset and registers a task for it. The file is a YAML list;
documents are block scalars so a record reads as one unit in a diff:

```yaml
- input: |
    # Report ...
  target_title_counts:
    Passive Voice: 1
    Ambiguous Actor: 0
  target_answer: What a correct result looks like, for the model grader.
```

`input` may also be `file://` followed by a path relative to the repo root. Two scorers
run: per-title issue counts against `target_title_counts` (only the titles listed are
compared, so a sample can express don't-care, and a clean sample lists its titles set
to 0), and a model grade against `target_answer`. Include negatives that exercise the
skill's exclusions; they are where a check earns trust.

```bash
uv run dev.py                                  # the backend must be running
uv run inspect eval evals_inspectai/e2e/skill_workflows_e2e.py@active_voice_e2e
```

## Managing existing workflows

- **Changing the rules**: edit the skill body. Nothing else needs to change; the
  prompt is read from the file on each run. Re-run the eval to see the effect.
- **Renaming the picker title, moving category, changing the icon**: edit the
  frontmatter. Regenerate the frontend API types only if the set of workflow types
  changed (`cd frontend && pnpm run openapi-generate` with the backend running).
- **Renaming the skill or its type slug**: the slug is persisted on every past run and
  issue (`workflow_runs.type`, `issues.workflow_type`), and a slug with no manifest
  behind it is treated as retired, so its old runs stop rendering. Keep the slug stable
  by setting `type:` explicitly when renaming the skill directory, or accept that history
  for the old slug is retired.
- **Promoting from experimental**: set `experimental: false` once the eval is stable.
  To pre-select it in the new-project wizard, add its type to
  `DEFAULT_SELECTED_WORKFLOW_TYPES` in `frontend/components/workflows/utils.ts`.
- **Adding a new category**: categories are still declared in
  `lib/workflows/categories.py`; add the slug and label there, and skills can then name it.
- **Retiring a workflow**: delete the skill directory. Its type leaves the enum and the
  registry, and past runs of it are hidden as retired, the same as for any removed workflow.
- **Turning a skill-declared workflow into a custom graph**: give it a hand-written
  manifest under `lib/workflows/<name>/` with the same `type` value, register it in
  `registry.py`, and remove the `draft_detective` block from the skill, since the registry
  refuses a skill that duplicates a hand-written type. Runs and issues keep working because
  the slug is unchanged.

## Failure modes and what they mean

| Symptom | Cause |
|---|---|
| Import error naming a skill and "not a WorkflowRunType member" | The skill is outside `skills/` or was added after the process started |
| Import error about a slug the enum "already has" | The slug or its upper-cased name collides with a hand-written member or another skill |
| Import error listing known categories | `category` is not a slug in `lib/workflows/categories.py` |
| Validation error on `draft_detective` | An unknown key or a wrong value type in the block |
| Picker shows the default document icon | `icon` is not a valid lucide name |
