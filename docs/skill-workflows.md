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
4. Optionally add an eval under `evals_inspectai/e2e/<slug>/` (see Evals below).

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
  Evals match a reported issue to an expected one by its title and the sentence it quotes,
  and reviewers learn to scan for the titles.
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
- `lib/agents/chat_agent.py` describes the chat's `/skill` commands with the picker text.
  Hand-written workflows are mapped to their skill by hand there; a skill-declared
  workflow is found through its manifest, so it needs no entry.
- Frontend: the picker draws a declared icon with lucide's `DynamicIcon`, the state
  type map falls back to `SimpleDeepAgentState` for any type it does not list, and the
  results renderer's default branch shows the deep-agent results view. No per-type edit
  is needed.

## Evals

Each workflow gets its own directory, `evals_inspectai/e2e/<slug>/`, holding a
`dataset.yaml`, a task module `<slug>_e2e.py` that defines the workflow's scorers and
returns its `Task`, and a `criteria.py` with what the check is about (copy
`evals_inspectai/e2e/active_voice/` and adapt). The task module composes reusable scorers from
`evals_inspectai/common/` (`issue_checks` and `decoy_checks` in `issue_checks.py`,
`judged_criteria` in `issue_judge.py`, all fed by the issue-inventory loader in
`issue_inventory.py`) and adds only what is specific to the workflow: its own edit checks and
the criteria the judge grades. None of that is tied to skill-declared workflows: any workflow
that reports issues can be evaluated the same way. `evals_inspectai/e2e/concision_precision/` and
`evals_inspectai/e2e/writing_consistency/` are the second and third skill-declared workflows on it, each
with its own `criteria.py` (a deterministic edit check plus judged criteria); `evals_inspectai/e2e/recommendation_check/`
scores a hand-written workflow with free-form titles and no edits on the same loader and scorers
(`expects_edits` and `expects_titles` read off the inventory that no edits and no titles are
expected, and `issue_checks(edits=False, titles=False)` then leaves the edit-hygiene and title keys
out, so the eval emits no key it can never score). Its skill requires one issue per
recommendation occurrence, so it passes `one_to_one=True`: a reported issue covers at most one expected
issue, and a run that merges two restatements loses recall on the second. Active Voice keeps the
default, where one paragraph-level issue may cover several expected sentences.

### Ground truth as an inventory

A record lists the issues a correct run reports (the same issues the workflows emit) and the
sentences it must leave alone, rather than counting issues by title. Each expected issue is
anchored by a verbatim quote, so the scorer knows whether the run found *that* sentence:

```yaml
- input: file://e2e/active_voice/files/report.md     # or inline markdown
  expected_issues:
    - title: Passive Voice                          # the issue title, or a stable part of it, matched
                                                    # as whole words within the reported title. Omit
                                                    # when titles have no stable part: any then matches
      anchor: "Studies were identified through"       # verbatim quote that locates the issue: resolves
                                                    # its line, and detection means the run quoted it
                                                    # or bracketed its line
      id: studies_identified                          # optional label for score explanations
      edit_expected: true                             # true: an edit must be attached; false: none may be
      severity: low                                   # optional
      edit:                                           # phrases a correct edit carries / avoids
        must_include: ["identified studies"]
        must_not_include: ["The authors"]
  decoys:
    - anchor: "The scope is limited to"
      reason: stative                                 # free-form; becomes the metric no_fp_stative
```

`line` is resolved from the anchor at load time and the loader fails on an anchor that is
missing or repeated. A record with `expected_issues: []` is a clean document: anything
reported on it is a false positive. Fixture documents live under
`evals_inspectai/e2e/<slug>/files/` and are referenced with `file://e2e/<slug>/files/...`.

### What gets scored

Up to four scorers, kept separate because their key sets have different owners, and each
metric named so a regression points at itself (see
`evals_inspectai/e2e/active_voice/active_voice_e2e.py`, which uses all four; Recommendation
Check uses the first two plus its image check):

1. **`issue_checks`, deterministic, the same keys for every sample of an eval.** Keys the
   inventory can never score (edit hygiene when no edits are expected, the title check when
   no titles are named) are left out rather than reported as NaN throughout. An
   expected issue is detected when a reported issue with its title quotes its anchor or
   brackets its line; several expected issues may map to one paragraph-level reported
   issue. Detection metrics: `recall` over required expected issues, `precision` over
   reported issues, `f0_5` (precision weighted twice, as in grammatical-error detection),
   `clean_document_untouched` for clean samples, `title_correct`, `severity_correct`,
   `anchor_in_range`. Edit hygiene metrics, for detected expected issues: an edit is
   present or absent as `edit_expected` says; the quote is verbatim on the line; the
   replacement carries the `must_include` phrases and none of `must_not_include`;
   numbers, footnote markers and citations survive; no stranded punctuation.
2. **`decoy_checks`, deterministic, keys follow the dataset.** One `no_fp_<reason>` per
   decoy reason the dataset uses: 1 when no decoy of that reason was flagged in the sample,
   0 when one was. This catches a sentence wrongly listed inside an otherwise correct
   paragraph issue, which precision cannot see, and names the exclusion rule that misfired.
3. **The workflow's own deterministic checks.** Active Voice adds
   `active_voice_edit_checks` with `edit_removes_passive`.
4. **`judged_criteria`, one focused grader call per item.** The workflow declares criteria as plain
   statements (Active Voice: meaning preserved while naming the supported actor; reads at
   least as well in place; for passive issues with no edit expected, the suggested action
   asks rather than guesses). Each is graded on Inspect's own model-grading protocol, the
   same template shape, instructions and C / P / I grade pattern as `model_graded_fact`,
   mapped to 1, 0.5 and 0. A detected issue that offers no suggested action scores 0 on an
   action criterion, not NaN. Inspect's built-in scorers grade one answer per sample, which is
   why the loop over edits is ours and the protocol is theirs. Pass `judge_calls=3` to take
   the median on a noisy criterion.

Each task passes a one-line description of every metric as `Task(metadata=...)`, which the
log viewer shows once in its Info tab; per-sample `explanation` text says what happened on
that sample, not what the metric means. A metric is `NaN` when a sample gives it nothing to
judge; Inspect leaves it out of the mean and counts the sample as unscored. Metrics are declared with Inspect's glob keys (`"*"`), so
every key a sample score carries gets a mean and standard error. There
is no whole-run grade: what a person would judge holistically is split into the criteria
above so each can be watched on its own.

### Composition and calibration

Mix short snippets that each pin one rule and should sit near 100 percent, clean
documents that measure false positives, and documents of section length that exercise
recall and edit quality at scale. Include negatives for every exclusion the skill states; they are where a check
earns trust.

Before trusting a judged criterion, run it against human-labelled pairs. The calibration
is itself an Inspect task: each pair is a sample, the solver passes the edit through, and
the scorers report agreement plus the true-positive and true-negative rates separately
(raw agreement hides a judge that always passes). Disagreements are readable in
`inspect view`.

```bash
uv run inspect eval evals_inspectai/e2e/active_voice/active_voice_judge_calibration.py -T calls=3
```

The grader is Inspect's `grader` model role: pass `--model-role grader=<provider/model>` to
try another judge without touching code; it defaults to the repo's grader model.

```bash
uv run dev.py                                  # the backend must be running
uv run inspect eval evals_inspectai/e2e/active_voice/active_voice_e2e.py
uv run inspect eval evals_inspectai/e2e/active_voice/active_voice_e2e.py --epochs 3 --epochs-reducer at_least_3
```

Use Inspect's epoch reducers for consistency questions: `--epochs 3 --epochs-reducer at_least_3`
asks whether a sample passes in every trial (pass^k), `pass_at_1` averages, and the default
`mean` reports the average across epochs.

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
