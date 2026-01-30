"""Constants for About Authors validation workflow.

Values loaded from workflow_config.yaml.
"""

from lib.config.workflow_config import get_workflow_config

_config = get_workflow_config("about_authors")
_rules = _config.get("rules", {})

# Abbreviations that should not be treated as sentence endings
ABBREVIATIONS = _config.get("abbreviations", [])

# Sentence patterns to ignore when counting
IGNORE_SENTENCE_PATTERNS = _config.get("ignore_sentence_patterns", [])

# TASP fellowship URL
TASP_URL = _config.get("tasp_url", "")

# Expected sentence count for author bios
EXPECTED_SENTENCE_COUNT = _config.get("expected_sentence_count", 3)

# Rule metadata
RULE_METADATA = {
    key: {
        "key": "_".join(key.split("_")[:2]),  # e.g., "rule_1_sentence_length" -> "rule_1"
        "name": rule.get("name", ""),
        "short_name": rule.get("short_name", ""),
        "description": rule.get("description", ""),
    }
    for key, rule in _rules.items()
}

# Ordered list of rule field names
RULE_FIELDS = list(_rules.keys())
