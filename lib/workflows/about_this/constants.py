"""Constants for About This (Preface) validation workflow.

Values loaded from workflow_config.yaml.
"""

from lib.config.workflow_config import get_workflow_config

_config = get_workflow_config("about_this")

# TASP Boilerplate - required exact text for source_tasp check
TASP_BOILERPLATE = _config.get("tasp_boilerplate", "")

# Funding statement variants - any one of these is acceptable
FUNDING_STATEMENT_VARIANTS = _config.get("funding_statement_variants", [])

# Requirement metadata - loaded from YAML
_requirements = _config.get("requirements", {})
REQUIREMENT_METADATA = {
    key: {
        "key": key,
        "name": req.get("name", ""),
        "short_name": req.get("short_name", ""),
        "description": req.get("description", ""),
        "level": req.get("level", "sentence"),
    }
    for key, req in _requirements.items()
}

# Ordered list of requirement field names
REQUIREMENT_FIELDS = list(_requirements.keys())

# Section headers to search for
PREFACE_SECTION_HEADERS = _config.get("section_headers", [])
