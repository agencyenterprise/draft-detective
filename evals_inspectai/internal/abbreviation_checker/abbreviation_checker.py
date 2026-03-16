from inspect_ai import task, task_with

from evals_inspectai.e2e.abbreviation_checker.abbreviation_checker_e2e import (
    abbreviation_checker_e2e,
)
from evals_inspectai.internal.common.config import get_model_or_agent_default
from evals_inspectai.internal.common.lc_agent_solver import langchain_agent
from lib.agents.abbreviation_checker import AbbreviationCheckerAgent


@task
def abbreviation_checker():
    base_task = abbreviation_checker_e2e()
    return task_with(
        base_task,
        model=get_model_or_agent_default(AbbreviationCheckerAgent),
        solver=langchain_agent(AbbreviationCheckerAgent),
    )
