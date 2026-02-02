"""Constants for About Authors validation workflow.

Values loaded from workflow_config.yaml.
All keys are required - missing keys will raise KeyError to catch config mistakes early.
"""

from lib.config.workflow_config import get_workflow_config

_config = get_workflow_config("about_authors")
_rules = _config["rules"]

# Abbreviations that should not be treated as sentence endings
ABBREVIATIONS = _config["abbreviations"]

# Sentence patterns to ignore when counting
IGNORE_SENTENCE_PATTERNS = _config["ignore_sentence_patterns"]

# TASP fellowship URL
TASP_URL = _config["tasp_url"]

# Expected sentence count for author bios
EXPECTED_SENTENCE_COUNT = _config["expected_sentence_count"]

# Rule metadata
RULE_METADATA = {
    key: {
        "key": "_".join(
            key.split("_")[:2]
        ),  # e.g., "rule_1_sentence_length" -> "rule_1"
        "name": rule["name"],
        "short_name": rule["short_name"],
        "description": rule["description"],
    }
    for key, rule in _rules.items()
}

# Ordered list of rule field names
RULE_FIELDS = list(_rules.keys())
