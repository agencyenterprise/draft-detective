"""Constants for About This (Preface) validation workflow.

Values loaded from workflow_config.yaml.
All keys are required - missing keys will raise KeyError to catch config mistakes early.
"""

from lib.config.workflow_config import get_workflow_config

_config = get_workflow_config("about_this")

# Boilerplate - required exact text for source_boilerplate check
BOILERPLATE = _config["boilerplate"]

# Funding statement variants - any one of these is acceptable
FUNDING_STATEMENT_VARIANTS = _config["funding_statement_variants"]

# Requirement metadata - loaded from YAML
_requirements = _config["requirements"]
REQUIREMENT_METADATA = {
    key: {
        "key": key,
        "name": req["name"],
        "short_name": req["short_name"],
        "description": req["description"],
        "level": req["level"],
    }
    for key, req in _requirements.items()
}

# Ordered list of requirement field names
REQUIREMENT_FIELDS = list(_requirements.keys())

# Section headers to search for
PREFACE_SECTION_HEADERS = _config["section_headers"]
