---
name: Informal argument inferential errors
overview: Create two wrong versions per category (policy, empirical, conceptual) with three inferential errors each (18 total), including at least one statistical error per document; update the three log JSONs with problem/action entries for each wrong file.
todos: []
isProject: false
---

# Plan: Add Inferential Errors to Informal Argument Test Cases

## Scope

- **Six new documents:** two wrong versions per category: `policy_minor_wrong.md`, `policy_major_wrong.md` (in [informal_argument1](rand-personal/inference_validation/informal_argument1)); `empirical_minor_wrong.md`, `empirical_major_wrong.md` (in [informal_argument2](rand-personal/inference_validation/informal_argument2)); `conceptual_minor_wrong.md`, `conceptual_major_wrong.md` (in [informal_argument3](rand-personal/inference_validation/informal_argument3)).
- **18 inferential errors total:** 3 per document.
- **Constraint:** At least one **statistical** reasoning error per document (6+ statistical errors across the 6 docs).
- **Log updates:** Each of [policy_log.json](rand-personal/inference_validation/informal_argument1/policy_log.json), [empirical_log.json](rand-personal/inference_validation/informal_argument2/empirical_log.json), [conceptual_log.json](rand-personal/inference_validation/informal_argument3/conceptual_log.json) gets two new entries (one per wrong file) with three `inference_problems` each (`problem` + `action`), matching the format in [complex_argument2_log.json](rand-personal/inference_validation/complex_argument2/complex_argument2_log.json).

---

## 1. Policy (informal_argument1)

**Base:** Copy [policy_correct.md](rand-personal/inference_validation/informal_argument1/policy_correct.md) to create the two wrong versions, then introduce the errors below.

### policy_minor_wrong.md (3 errors)


| #   | Error type                                        | Where to introduce                        | Change                                                                                                                                                                                                                                                   |
| --- | ------------------------------------------------- | ----------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| 1   | **Statistical:** Misinterpreting non-significance | Section 2.2 (empirical premise)           | Add or rewrite a sentence so it says that because employment effects were "not statistically significant" in the Finnish trial, UBI "has no effect on employment" or "does not reduce employment." (Correct: non-significance does not imply no effect.) |
| 2   | **Logical:** Overstated conclusion                | Section 2.3 or 3 (inference / conclusion) | Strengthen the conclusion from "a pilot is justified" to "UBI should be adopted" or "governments should implement UBI" without adding argument for that stronger claim.                                                                                  |
| 3   | **Logical:** Dropped normative premise            | Section 2.3 (inference to a pilot)        | Remove or weaken the explicit appeal to the normative premise (2.1); infer "a pilot is justified" mainly from the empirical premise alone (ought-from-is).                                                                                               |


### policy_major_wrong.md (3 errors)


| #   | Error type                                     | Where to introduce              | Change                                                                                                                                                                                                                             |
| --- | ---------------------------------------------- | ------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| 1   | **Statistical:** Selection / survivorship bias | Section 2.2 (empirical premise) | Describe evidence only from completed or "successful" pilots and write as if they represent all UBI evidence; omit or downplay cancelled pilots (e.g. Ontario) or failed trials, so the reader generalises from a selected subset. |
| 2   | **Logical:** Ought from is                     | Section 2.3                     | Infer "we should run a pilot" (or "we should adopt UBI") from "evidence does not show harm" without stating the normative premise that reducing hardship is a legitimate aim.                                                      |
| 3   | **Logical:** Slippery slope                    | Section 2.4 (objections) or 3   | Add a sentence that if we pilot UBI we will be forced to adopt it permanently (or that it will bankrupt the state) without arguing each step.                                                                                      |


---

## 2. Empirical (informal_argument2)

**Base:** Copy [empirical_correct.md](rand-personal/inference_validation/informal_argument2/empirical_correct.md) to create the two wrong versions.

### empirical_minor_wrong.md (3 errors)


| #   | Error type                                | Where to introduce | Change                                                                                                                                                        |
| --- | ----------------------------------------- | ------------------ | ------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| 1   | **Statistical:** Correlation vs causation | Section 2.3 or 3   | Replace "associated with" by "causes" (e.g. "remote work causes lower carbon emissions from commuting") without adding causal design or confound discussion.  |
| 2   | **Logical:** Scope creep                  | Section 2.3 or 3   | Generalise from "in the contexts studied" / "high-income urban contexts" to "everywhere" or "in all contexts" or "for all remote work" without justification. |
| 3   | **Logical:** Overstated strength          | Section 2.2 or 2.3 | Use "proves," "shows that," or "demonstrates" where the correct version uses "suggests," "is consistent with," or "associated with."                          |


### empirical_major_wrong.md (3 errors)


| #   | Error type                            | Where to introduce     | Change                                                                                                                                                                                                                                                      |
| --- | ------------------------------------- | ---------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| 1   | **Statistical:** Ecological fallacy   | Section 2.2 or 2.3     | Add or rewrite so that a region-level or aggregate finding (e.g. "regions with more remote work have lower emissions") is used to infer an individual-level conclusion (e.g. "each remote worker reduces emissions") without noting the ecological fallacy. |
| 2   | **Statistical:** Ignoring confounding | Section 2.2 (evidence) | Present the association as if it were causal without mentioning confounders (e.g. who chooses WFH, income, location, car ownership) or self-selection.                                                                                                      |
| 3   | **Logical:** Hasty generalization     | Section 2.3 or 3       | Generalise from "studies in the US and Europe" to "all countries" or "all workers" without scope restriction.                                                                                                                                               |


---

## 3. Conceptual (informal_argument3)

**Base:** Copy [conceptual_correct.md](rand-personal/inference_validation/informal_argument3/conceptual_correct.md) to create the two wrong versions.

### conceptual_minor_wrong.md (3 errors)


| #   | Error type                                                     | Where to introduce           | Change                                                                                                                                                                                                                                                                                                          |
| --- | -------------------------------------------------------------- | ---------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| 1   | **Statistical:** Base-rate neglect or survey misinterpretation | New sentence in 2.2 or 2.3   | Add a claim such as "Surveys show that 60% of respondents prefer equal opportunity; therefore fairness in hiring is best understood as equal opportunity." (Error: inferring a conceptual conclusion from a single survey proportion; optionally add base-rate neglect by ignoring how the sample was defined.) |
| 2   | **Logical:** Equivocation                                      | Section 2.2 or 2.3           | Use "fairness" once as equal opportunity and elsewhere as equal outcomes (or "fair outcomes") without marking the shift, so the argument appears to support one definition by the other.                                                                                                                        |
| 3   | **Logical:** Straw man                                         | Section 2.3 (equal outcomes) | Misstate the equal-outcomes view (e.g. "equal outcomes means no standards at all" or "selecting at random") then refute that; keep the rest of the structure similar.                                                                                                                                           |


### conceptual_major_wrong.md (3 errors)


| #   | Error type                                     | Where to introduce               | Change                                                                                                                                                                                                                                                |
| --- | ---------------------------------------------- | -------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| 1   | **Statistical:** Cherry-picking / small sample | Section 2.2                      | Add a sentence that "One study found that employers and applicants prefer equal opportunity; therefore fairness is best understood as equal opportunity." (Error: generalising a conceptual claim from one study / small or unrepresentative sample.) |
| 2   | **Logical:** Begging the question              | Section 2.1 (definitions) or 2.2 | Define "fairness" in hiring as equal opportunity (or build it into the definition), then "conclude" that fairness is equal opportunity.                                                                                                               |
| 3   | **Logical:** Smuggled empirical claim          | Section 2.2 or 2.3               | Insert an empirical claim presented as part of the conceptual analysis (e.g. "Algorithms always discriminate against protected groups, so fairness must mean equal opportunity to correct this") without evidence or without marking it as empirical. |


---

## 4. Log JSON updates

For each category, add **two** entries to the existing log file (after the existing `*_correct.md` entry), with **three** `inference_problems` per wrong file.

**Structure per entry (same as complex_argument2_log.json):**

```json
{
  "file_name": "policy_minor_wrong.md",
  "inference_problems": [
    { "problem": "...", "action": "..." },
    { "problem": "...", "action": "..." },
    { "problem": "...", "action": "..." }
  ]
}
```

- **policy_log.json:** Add entries for `policy_minor_wrong.md` and `policy_major_wrong.md`; each with three `problem`/`action` items matching the three errors in the table above (statistical + logical descriptions).
- **empirical_log.json:** Add entries for `empirical_minor_wrong.md` and `empirical_major_wrong.md`; each with three items.
- **conceptual_log.json:** Add entries for `conceptual_minor_wrong.md` and `conceptual_major_wrong.md`; each with three items.

Each `problem` should briefly state what inferential or statistical error was introduced; each `action` should state how to fix it (e.g. "Restore cautious language: use 'associated with' and restrict scope to studied contexts.").

---

## 5. Implementation order

1. Create `policy_minor_wrong.md` and `policy_major_wrong.md` by copying `policy_correct.md` and applying the edits in section 1.
2. Update `policy_log.json` with two new entries and 3 inference_problems each.
3. Create `empirical_minor_wrong.md` and `empirical_major_wrong.md` by copying `empirical_correct.md` and applying the edits in section 2.
4. Update `empirical_log.json` with two new entries and 3 inference_problems each.
5. Create `conceptual_minor_wrong.md` and `conceptual_major_wrong.md` by copying `conceptual_correct.md` and applying the edits in section 3.
6. Update `conceptual_log.json` with two new entries and 3 inference_problems each.

---

## 6. Summary


| Category   | Minor wrong file          | Major wrong file          | Errors per file | Statistical per doc |
| ---------- | ------------------------- | ------------------------- | --------------- | ------------------- |
| Policy     | policy_minor_wrong.md     | policy_major_wrong.md     | 3               | ≥1                  |
| Empirical  | empirical_minor_wrong.md  | empirical_major_wrong.md  | 3               | ≥1                  |
| Conceptual | conceptual_minor_wrong.md | conceptual_major_wrong.md | 3               | ≥1                  |


**Total:** 6 new documents, 18 inferential errors, 6+ statistical errors. Logs updated so each wrong file has a corresponding entry with three `problem`/`action` pairs for use by the long inference checker and evaluation scripts.