"""Runtime config keys for the About This (GER) workflow.

These keys are used to look up admin-overridable prompts via the
AppConfig table.  The defaults list is seeded on app startup by
ensure_defaults().
"""

from lib.agents.authors_validator import (
    _SYSTEM_PROMPT as AUTHORS_DEFAULT_PROMPT,
)
from lib.agents.preface_validator import (
    _SYSTEM_PROMPT as PREFACE_DEFAULT_PROMPT,
)
from lib.services.app_configs import DefaultConfig

PREFACE_PROMPT_KEY = "about_this_ger.preface_validator.system_prompt"
AUTHORS_PROMPT_KEY = "about_this_ger.authors_validator.system_prompt"

ABOUT_THIS_GER_DEFAULTS = [
    DefaultConfig(
        key=PREFACE_PROMPT_KEY,
        default_value=PREFACE_DEFAULT_PROMPT,
        description=(
            "System prompt for the Preface Validator agent in the "
            "About This (GER) workflow. The agent uses this prompt to "
            "evaluate the preface / introduction section of a document "
            "against publication rules."
        ),
    ),
    DefaultConfig(
        key=AUTHORS_PROMPT_KEY,
        default_value=AUTHORS_DEFAULT_PROMPT,
        description=(
            "System prompt for the Authors Validator agent in the "
            "About This (GER) workflow. The agent uses this prompt to "
            "evaluate each author biography against publication rules."
        ),
    ),
]
