"""One issue-inventory eval's dataset and the generic scoring wired to it.

An eval states two things about its workflow: how its reports pair with
expected issues (``pairing``, plus ``pair_on_location`` when titles are
verdicts) and which state fields hold its issues (``results``). Everything
else is derived from the dataset once, here: which generic checks apply, the
decoy reasons, the named titles, the metric descriptions and the viewer
columns. The derived ``ScoringPolicy`` rides on every sample's inventory, so
the generic checks, the judge and the eval's own criteria all read the same
one without being passed flags.

A task then reads::

    suite = InventorySuite.load(DATASET, pairing="one_to_one")
    own = {"tone_checks": OWN_DESCRIPTIONS, "judged_criteria": JUDGE_DESCRIPTIONS}
    Task(
        dataset=suite.dataset(),
        metadata=suite.metadata(GROUND_TRUTH, own),
        solver=...,
        scorer=[*suite.scorers(), tone_checks(), suite.judged(JUDGE_CRITERIA, calls=judge_calls)],
        viewer=suite.viewer(own, SCORE_LABELS),
    )
"""

from pathlib import Path
from typing import Any, Callable, Mapping, Optional, Sequence

from inspect_ai.dataset import MemoryDataset
from inspect_ai.scorer import Scorer
from inspect_ai.viewer import ViewerConfig
from pydantic import BaseModel, ConfigDict

from evals_inspectai.common.issue_checks import (
    DEFAULT_RESULTS,
    decoy_checks,
    decoy_descriptions,
    issue_check_descriptions,
    issue_check_keys,
    issue_checks,
)
from evals_inspectai.common.issue_inventory import (
    Pairing,
    ResolvedInventory,
    ScoringPolicy,
    derive_policy,
    inventory_to_sample,
    load_inventory,
)
from evals_inspectai.common.issue_judge import JudgeCriterion, judged_criteria
from evals_inspectai.common.issue_viewer import decoy_labels, issue_viewer_config

# Per scorer name, what each of its keys checks: the Task metadata's metrics and,
# in the same order, the viewer's columns.
Descriptions = Mapping[str, Mapping[str, str]]


class InventorySuite(BaseModel):
    """An inventory dataset loaded under one ``ScoringPolicy``, with the generic scorers, the
    Task metadata and the viewer columns that policy implies."""

    model_config = ConfigDict(frozen=True)

    path: Path
    name: str
    records: list[ResolvedInventory]
    # Per record, the fields named by ``extra_fields`` at load (see ``load_inventory``).
    extras: list[dict[str, Any]]
    policy: ScoringPolicy
    results: tuple[str, ...] = DEFAULT_RESULTS

    @classmethod
    def load(
        cls,
        path: Path,
        pairing: Pairing = "shared",
        pair_on_location: bool = False,
        extra_fields: Sequence[str] = (),
        results: Sequence[str] = DEFAULT_RESULTS,
        name: Optional[str] = None,
    ) -> "InventorySuite":
        """Load ``path`` under the workflow's pairing. ``results`` names the state fields
        holding its issues (see ``issue_checks.issues_from_state``); ``name`` is the
        dataset name, the file's directory by default."""
        records, extras = load_inventory(path, extra_fields, pairing, pair_on_location)
        policy = records[0].policy if records else derive_policy([], pairing, pair_on_location)
        return cls(
            path=path,
            name=name or path.parent.name,
            records=records,
            extras=extras,
            policy=policy,
            results=tuple(results),
        )

    def dataset(self, metadata: Optional[Callable[[dict[str, Any]], dict[str, Any]]] = None) -> MemoryDataset:
        """One sample per record; ``metadata`` maps a record's extras to sample metadata of its own."""
        samples = []
        for record, extra in zip(self.records, self.extras):
            sample = inventory_to_sample(record)
            if metadata is not None:
                sample.metadata = {**(sample.metadata or {}), **metadata(extra)}
            samples.append(sample)
        return MemoryDataset(samples=samples, name=self.name, location=str(self.path))

    def scorers(self) -> list[Scorer]:
        """``issue_checks``, and ``decoy_checks`` when the dataset has decoys."""
        if not self.policy.decoy_reasons:
            return [issue_checks(self.results)]
        return [issue_checks(self.results), decoy_checks(self.results)]

    def judged(self, criteria: Sequence[JudgeCriterion], calls: int = 1) -> Scorer:
        """``judged_criteria`` reading the suite's state fields."""
        return judged_criteria(criteria, calls=calls, results=self.results)

    def descriptions(self, own: Optional[Descriptions] = None) -> dict[str, dict[str, str]]:
        """The generic scorers' key descriptions, then the eval's ``own``."""
        generic: dict[str, dict[str, str]] = {"issue_checks": issue_check_descriptions(self.policy)}
        if self.policy.decoy_reasons:
            generic["decoy_checks"] = decoy_descriptions(self.policy.decoy_reasons)
        return {**generic, **{name: dict(keys) for name, keys in (own or {}).items()}}

    def metadata(self, ground_truth: str, own: Optional[Descriptions] = None) -> dict[str, Any]:
        """The Task metadata the log viewer's Info tab shows: what the ground truth is, and what each metric checks."""
        return {"ground_truth": ground_truth, "metrics": self.descriptions(own)}

    def viewer(self, own: Optional[Descriptions] = None, labels: Optional[Mapping[str, str]] = None) -> ViewerConfig:
        """A column per generic key, then one per key of ``own`` in order; ``labels`` names the eval's own."""
        generic = [("issue_checks", key) for key in issue_check_keys(self.policy)]
        generic += [("decoy_checks", f"no_fp_{reason}") for reason in self.policy.decoy_reasons]
        columns = [*generic, *((name, key) for name, keys in (own or {}).items() for key in keys)]
        return issue_viewer_config(columns, {**decoy_labels(self.policy.decoy_reasons), **(labels or {})})
