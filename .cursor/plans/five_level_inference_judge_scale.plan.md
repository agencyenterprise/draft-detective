---
name: Five-level inference judge scale
overview: Replace the three-category performance scale (match / partial / mismatch) in the inference judge with a five-level scale based on set containment between expected and found issues, with emoji labels for the table and output.
todos:
  - id: judge-five-level
    content: Add five performance literals and emoji labels to inference_judge.py
    status: pending
  - id: prompt-five-level
    content: Update _JUDGE_INSTRUCTIONS with five categories and passed rule
    status: pending
isProject: false
---

# Five-Level Inference Judge Scale

## Scope

- **Judge only:** [rand-personal/randz-358-inference-validation/inference_judge.py](rand-personal/randz-358-inference-validation/inference_judge.py). The checker and batch loop in [long_inference_checker.py](rand-personal/randz-358-inference-validation/long_inference_checker.py) already consume `judge_result.performance` and `performance_label(judge_result)`; they require no code changes once the judge returns one of five values and the label helper maps them.

---

## 1. Five levels (semantics and passed rule)


| Level | Literal                  | Set relationship                                                | passed |
| ----- | ------------------------ | --------------------------------------------------------------- | ------ |
| 1     | no_overlap               | Expected and found have no overlap                              | False  |
| 2     | found_subset_of_expected | Found issues are a subset of expected (expected contains found) | False  |
| 3     | overlap_neither          | Overlap exists but neither set contains the other               | False  |
| 4     | expected_subset_of_found | Expected issues are a subset of found (found contains expected) | True   |
| 5     | perfect_match            | Perfect match between expected and found                        | True   |


Set `passed=True` only for level 4 or 5; `passed=False` for levels 1–3.

---

## 2. Emoji mapping for performance_label()

Use this mapping in `performance_label(result)` so the ASCII table and single-doc output show a consistent visual scale (worst to best):


| Literal                  | Display string (with emoji)     |
| ------------------------ | ------------------------------- |
| no_overlap               | "❌ 1 No overlap"                |
| found_subset_of_expected | "🟠 2 Found subset of expected" |
| overlap_neither          | "🟡 3 Overlap neither"          |
| expected_subset_of_found | "🟢 4 Expected subset of found" |
| perfect_match            | "✅ 5 Perfect match"             |


Interpretation: ❌ worst, then 🟠 → 🟡 → 🟢 → ✅ best.

---

## 3. Changes in inference_judge.py

**3.1 JudgeResult (lines 23–33)**

- Change `performance` from `Literal["match", "partial", "mismatch"]` to:
  - `Literal["no_overlap", "found_subset_of_expected", "overlap_neither", "expected_subset_of_found", "perfect_match"]`
- Keep `passed: bool` and `rationale: str`. Update the Field description for `performance` to summarize the five options.

**3.2 performance_label (lines 36–43)**

- Replace the three-entry dict with the five emoji mappings above. Keep `labels.get(result.performance, result.performance)` as fallback.

**3.3 _JUDGE_INSTRUCTIONS (lines 90–99)**

- Replace the three-category bullets with five categories:
  1. **no_overlap**: No overlap between expected and found issues.
  2. **found_subset_of_expected**: The set of expected issues contains the set of found issues (found is a subset of expected).
  3. **overlap_neither**: There is overlap between expected and found, but neither set contains the other.
  4. **expected_subset_of_found**: The set of found issues contains the set of expected issues (expected is a subset of found).
  5. **perfect_match**: Perfect match between found and expected issues.
- State that the judge must choose exactly one performance category.
- Set `passed=True` only for **expected_subset_of_found** or **perfect_match**; `passed=False` otherwise.
- Keep semantic-matching guidance and the instruction to briefly state in rationale which expected problems are covered or missing.

**3.4 Docstring**

- Update the docstring of `evaluate_inference_output` to mention the five-level performance scale.

---

## 4. long_inference_checker.py

No structural changes. It already uses `judge_result.performance` and `performance_label(judge_result)`; the table and JSON will show the new levels once the judge and labels are updated.

---

## 5. File checklist


| Area          | File                      | Changes                                                                              |
| ------------- | ------------------------- | ------------------------------------------------------------------------------------ |
| Judge result  | inference_judge.py        | JudgeResult.performance: Literal of five values; update Field description.           |
| Labels        | inference_judge.py        | performance_label(): map all five literals to emoji display strings (see section 2). |
| Prompt        | inference_judge.py        | _JUDGE_INSTRUCTIONS: five categories; passed=True only for levels 4 and 5.           |
| Docstring     | inference_judge.py        | evaluate_inference_output: mention five-level performance.                           |
| Checker/batch | long_inference_checker.py | None.                                                                                |


